import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import requests
import re
import json
from difflib import get_close_matches
from datetime import datetime
from dotenv import load_dotenv
import os
import google.generativeai as genai

# Local modules
from scripts.fetch_crypto import fetch_top_coins
from apis.coingecko import get_coin_mapping, fetch_price_history, search_coin_in_df

# Helper to resolve coin name/symbol to valid CoinGecko ID
def resolve_coin_id(name_or_symbol: str, coin_map: dict):
    """Resolves user coin input to valid CoinGecko ID using exact or fuzzy match."""
    if not name_or_symbol: 
        print('Did not find a mapping in the coin map')
        return None
    name_or_symbol = name_or_symbol.strip().lower()
    if name_or_symbol in coin_map:
        print('Found a mapping in the coin map')
        return coin_map[name_or_symbol]
    matches = get_close_matches(name_or_symbol, list(coin_map.keys()), n=1, cutoff=0.8)
    if matches:
        st.write(f"Fuzzy match for '{name_or_symbol}':", matches[0])
        return coin_map[matches[0]]
    return None

# Page / App Config
st.set_page_config(page_title="Crypto Dashboard", layout="wide")
st.title("Live Crypto Dashboard")
st.markdown("Displays top cryptocurrencies by market cap using CoinGecko API.")

# Get coin mapping (cached in coingecko.py)
coin_map = get_coin_mapping()

# 1) Sidebar controls + top‑N dataframe

currency = st.selectbox("Select currency", ["USD", "EUR", "SGD"])
limit = st.slider("Select number of coins to display", 5, 50, 10)

if st.button("Refresh Data"):
    df = fetch_top_coins(limit=limit, currency=currency)
else:
    df = fetch_top_coins(limit=limit, currency=currency)

if df.empty:
    st.error("Failed to load data from CoinGecko API.")
    st.stop()

# 2) Table search / filter (uses contains + fuzzy suggestions)
user_query = st.text_input("Search for a coin (name / symbol)")

if user_query:
    filtered_df, suggestions = search_coin_in_df(df, coin_map, user_query)
    if filtered_df.empty:
        if suggestions:
            st.info("Did you mean: " + ", ".join(suggestions))
        else:
            st.warning("No matching coins found.")
else:
    filtered_df = df


if not df.empty:
    top_coin = df.iloc[0]
    st.subheader(f"📊 Key Metrics for Top Coin: {top_coin['name']}")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Price", f"${top_coin['current_price']:,.2f}", f"{top_coin['price_change_percentage_24h']:.2f}%")
    with col2:
        st.metric("Market Cap", f"${top_coin['market_cap']:,.0f}")
    with col3:
        st.metric("24h Volume", f"${top_coin['total_volume']:,.0f}")
    st.caption(f"\u23F1 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 4) Filtered data table
if filtered_df.empty:
    st.warning("No matching coins found.")
else:
    st.dataframe(
        filtered_df.style.format({
            "current_price": "${:,.2f}",
            "market_cap":    "${:,.0f}",
            "price_change_percentage_24h": "{:+.2f}%",
            "total_volume":  "${:,.0f}"
        }),
        use_container_width=True
    )

# 5) Market overview charts (full df)
st.subheader("Market Cap of Top Cryptos")
st.bar_chart(df.set_index("name")["market_cap"])

st.subheader("📈 24h Price Change (%)")
st.bar_chart(df.set_index("name")["price_change_percentage_24h"])

# 6) Pie chart (Top 5 + Others)
df_sorted = df.sort_values(by="market_cap", ascending=False)
main_df = df_sorted.head(5)
others_cap = df_sorted["market_cap"].iloc[5:].sum()

pie_df = pd.concat([
    main_df[["name", "market_cap"]],
    pd.DataFrame([{"name": "Others", "market_cap": others_cap}])
])

fig, ax = plt.subplots()
ax.pie(
    pie_df["market_cap"],
    labels=pie_df["name"],
    autopct="%1.1f%%",
    startangle=90,
    pctdistance=0.85,
    labeldistance=1.05,
    textprops={"fontsize": 8}
)
ax.axis("equal")
st.subheader("Market Cap Distribution (Top 5 + Others)")
st.pyplot(fig)

# 7) Gemini Chatbot (trend + chart)

# For production
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# For local
# genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Gemini Prompt
def extract_intent_from_prompt_llm(prompt: str):
    system_prompt = """
    You are an assistant that classifies crypto-related user queries as either chart-related or general information.

    Respond with a valid JSON object like:
    {
      "type": "chart" | "info",
      "coin_id": "<coin name or symbol>",       // Only for chart
      "chart": "line" | "bar" | "pie",          // Only for chart
      "days": <number of days as an integer>    // Only for chart
    }

    If it's a general information request (like 'what is bitcoin?'), set "type" to "info" and ignore other fields.

    If 'days' is not mentioned, default to 7. If coin is unknown, use "none" for coin.
    """

    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(f"{system_prompt}\n\nQuery: {prompt}")
    raw = response.text.strip()

    #st.code(raw, language="json")  # Debug Gemini's response

    clean = re.sub(r"```(?:json)?", "", raw).strip()

    try:
        parsed = json.loads(clean)
        #st.write("Parsed Gemini JSON:", parsed)

        if parsed.get("type") == "chart":
            coin = parsed.get("coin_id")
            chart_type = parsed.get("chart", "line")
            days = int(parsed.get("days", 7))
            return "chart", coin, chart_type, days
        else:
            return "info", prompt, None, None
    except Exception as e:
        st.warning(f"Intent extraction failed: {e}")
        return "info", prompt, None, None


st.subheader("💬 Ask CryptoBot")

# Initialise chat history on first run
if "messages" not in st.session_state:
    st.session_state.messages = []

# Handle user input and generate response
user_prompt = st.chat_input("Ask CryptoBot…")
if user_prompt:
    # Add user's message to history
    st.session_state.messages.append({
        "role": "user", "type": "text", "content": user_prompt
    })

    # Process input and update history (but don't display yet)
    with st.spinner("Thinking…"):
        intent_type, value1, value2, value3 = extract_intent_from_prompt_llm(user_prompt)

        if intent_type == "chart":
            coin_input, chart_type, days = value1, value2, value3
            coin_id = resolve_coin_id(coin_input, coin_map)

            if not coin_id:
                fallback = genai.GenerativeModel("gemini-1.5-flash").generate_content(user_prompt).text
                st.session_state.messages.append({
                    "role": "assistant", "type": "text", "content": fallback
                })
            else:
                trend_df = fetch_price_history(coin_id, currency.lower(), days)
                if trend_df is not None and not trend_df.empty:
                    st.session_state.messages.append({
                        "role": "assistant",
                        "type": "chart",
                        "chart": chart_type,
                        "df": trend_df.to_dict("records"),
                        "coin_id": coin_id
                    })
                else:
                    msg = f"⚠️ Failed to retrieve {days}-day data for **{coin_id}**."
                    st.session_state.messages.append({
                        "role": "assistant", "type": "text", "content": msg
                    })

        elif intent_type == "info":
            info_response = genai.GenerativeModel("gemini-1.5-flash").generate_content(user_prompt).text
            st.session_state.messages.append({
                "role": "assistant", "type": "text", "content": info_response
            })

        else:
            fallback = "⚠️ I couldn't understand your request. Try asking about a crypto trend or general info."
            st.session_state.messages.append({
                "role": "assistant", "type": "text", "content": fallback
            })

    # Trim to last 30 messages
    if len(st.session_state.messages) > 30:
        st.session_state.messages = st.session_state.messages[-30:]

# Render all messages from history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["type"] == "text":
            st.markdown(msg["content"])
        elif msg["type"] == "chart":
            try:
                df_ = pd.DataFrame(msg["df"]).set_index("ts")["price"]
                df_.index = pd.to_datetime(df_.index)

                if msg["chart"] == "bar":
                    st.bar_chart(df_)
                elif msg["chart"] == "pie":
                    fig, ax = plt.subplots()
                    ax.pie(
                        df_.values,
                        labels=df_.index.strftime("%d-%b"),
                        autopct="%1.1f%%",
                        startangle=90,
                        textprops={"fontsize": 8}
                    )
                    ax.axis("equal")
                    st.pyplot(fig)
                else:
                    st.line_chart(df_)
            except Exception as e:
                st.warning(f"⚠️ Chart could not be rendered: {e}")
