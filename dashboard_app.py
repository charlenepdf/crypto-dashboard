import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import requests
import re
import json
from difflib import get_close_matches
from datetime import datetime

import google.generativeai as genai

# Local modules
from scripts.fetch_crypto import fetch_top_coins
from apis.coingecko import get_coin_mapping, fetch_price_history, search_coin_in_df

# Helper to resolve coin name/symbol to valid CoinGecko ID
def resolve_coin_id(name_or_symbol: str, coin_map: dict):
    """Resolves user coin input to valid CoinGecko ID using exact or fuzzy match."""
    name_or_symbol = name_or_symbol.strip().lower()
    if name_or_symbol in coin_map:
        return coin_map[name_or_symbol]
    else:
        matches = get_close_matches(name_or_symbol, list(coin_map.keys()), n=1, cutoff=0.6)
        if matches:
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

# 3) Key metrics (based on full df)

#top_coin = df.iloc[0]
#st.subheader(f"📊 Key Metrics for Top Coin: {top_coin['name']}")
#col1, col2, col3 = st.columns(3)

#with col1:
    #st.metric("Price",      f"${top_coin['current_price']:,.2f}", f"{top_coin['price_change_percentage_24h']:.2f}%")
#with col2:
    #st.metric("Market Cap", f"${top_coin['market_cap']:,.0f}")
#with col3:
    #st.metric("24h Volume", f"${top_coin['total_volume']:,.0f}")

#st.caption(f"⏱ Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

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

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# helper → extract coin id from arbitrary prompt
#def extract_coin_from_prompt_fuzzy(prompt: str):
    #words = re.findall(r"\w+", prompt.lower())
    #for w in words:
        #if w in coin_map:
            #return coin_map[w]
    # fuzzy fallback
    #matches = get_close_matches(" ".join(words), coin_map.keys(), n=1, cutoff=0.6)
    #if matches:
        #return coin_map[matches[0]]
    #return None


def extract_intent_from_prompt_llm(prompt: str):
    system_prompt = """
    You are an assistant that extracts intent from user queries about cryptocurrencies.

    Respond with a valid JSON in this format:
    {
      "coin_id": "<coin name or symbol>",
      "chart": "line" | "bar" | "pie",
      "days": <number of days as an integer>
    }

    If 'days' is not mentioned, default to 7.
    If coin is unknown, use "none" for coin.
    """

    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(f"{system_prompt}\n\nQuery: {prompt}")
    raw = response.text.strip()
    
    st.code(raw, language="json")  # Debug: Show raw Gemini response

    clean = re.sub(r"```(?:json)?", "", raw).strip()

    try:
        parsed = json.loads(clean)
        coin = parsed.get("coin")
        #coin_id = parsed.get("coin_id", "").strip()
        #coin_name_or_symbol = parsed.get("coin", "").strip()
        chart_type = parsed.get("chart", "line")
        days = int(parsed.get("days", 7))
        return coin, chart_type, days
        #return coin_name_or_symbol, chart_type, days
    except Exception as e:
        st.warning(f"Intent extraction failed: {e}")
        return None, "line", 7


#def extract_intent_from_prompt_llm(prompt: str):
    system_prompt = """
    You are an assistant that extracts coin and chart intent from user queries.

    Respond in valid JSON only:
    {
      "coin_id": "<CoinGecko ID>",
      "chart": "line", "bar", or "pie"
    }

    Return {"coin_id": "none", "chart": "line"} if unsure.
    """
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(f"{system_prompt}\n\nQuery: {prompt}")

    raw = response.text.strip()
    #st.write("Gemini raw response:", raw) # debug
    clean = re.sub(r"```(?:json)?", "", raw).strip()

    try:
        parsed = json.loads(clean)
        coin_id = parsed.get("coin_id")
        chart_type = parsed.get("chart", "line")
        return (coin_id if coin_id in coin_map else None), chart_type
    except Exception as e:
        st.warning(f"Intent extraction failed: {e}")
        return None, "line"



#def extract_chart_type(prompt: str):
    prompt = prompt.lower()
    if "bar" in prompt:
        return "bar"
    elif "line" in prompt:
        return "line"
    return "line"  # default fallback

st.subheader("💬 Ask CryptoBot")

# Initialise chat history on first run
if "messages" not in st.session_state:
    st.session_state.messages = []

# Render previous messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["type"] == "chart":
            # Ensure safe reloading of DataFrame
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
        else:
            st.markdown(msg["content"])

# Input box (appears below history)
if user_prompt := st.chat_input("Ask CryptoBot…"):
    st.session_state.messages.append({
        "role": "user", "type": "text", "content": user_prompt
    })

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            #coin_id, chart_type, days = extract_intent_from_prompt_llm(user_prompt)
            coin_name_or_symbol, chart_type, days = extract_intent_from_prompt_llm(user_prompt)
            st.caption(f"🧠 Gemini guessed coin: {coin_name_or_symbol}")
            
            # Validate coin using coin_map
            coin_id = resolve_coin_id(coin_name_or_symbol, coin_map)
            if not coin_id:
                st.warning(f"⚠️ '{coin_id}' could not be resolved to a valid coin.")
                # Fallback LLM response
                fallback = genai.GenerativeModel("gemini-1.5-flash").generate_content(user_prompt).text
                st.markdown(fallback)
                st.session_state.messages.append({
                    "role": "assistant", "type": "text", "content": fallback
                })
            else:
                trend_df = fetch_price_history(coin_id, currency.lower(), days)
                if trend_df is not None and not trend_df.empty:
                    # Store as dict for session serialization
                    st.session_state.messages.append({
                        "role": "assistant",
                        "type": "chart",
                        "chart": chart_type,
                        "df": trend_df.to_dict("records"),  # safer than just .to_dict()
                        "coin_id": coin_id
                    })

                    if chart_type == "bar":
                        st.bar_chart(trend_df.set_index("ts")["price"])
                    elif chart_type == "pie":
                        fig, ax = plt.subplots()
                        ax.pie(
                            trend_df["price"],
                            labels=trend_df["ts"].dt.strftime("%d-%b"),
                            autopct="%1.1f%%",
                            startangle=90,
                            textprops={"fontsize": 7}
                        )
                        ax.axis("equal")
                        st.pyplot(fig)
                    else:
                        st.line_chart(trend_df.set_index("ts")["price"])
                else:
                    msg = f"⚠️ Failed to retrieve {days}-day data for **{coin_id}**."
                    st.markdown(msg)
                    st.session_state.messages.append({
                        "role": "assistant", "type": "text", "content": msg
                    })
            # else:
            #     # fallback LLM response
            #     answer = genai.GenerativeModel("gemini-1.5-flash").generate_content(user_prompt).text
            #     st.markdown(answer)
            #     st.session_state.messages.append({
            #         "role": "assistant", "type": "text", "content": answer
            #     })



#user_prompt = st.text_input("Ask something like 'Give me a 7-day trend of Bitcoin'")

#if user_prompt:
    #with st.spinner("Thinking..."):
        #try:
            # Optional Gemini LLM response
            # answer = genai.GenerativeModel("gemini-1.5-flash").generate_content(user_prompt)
            # st.success(answer.text)

            # Try Gemini first, fallback to local fuzzy
            #coin_id, chart_typ, days = extract_intent_from_prompt_llm(user_prompt)
            #st.write(f"Resolved Coin ID: {coin_id}") # debug

            #if coin_id:
                #trend_df = fetch_price_history(coin_id, currency.lower(), days)
                #if trend_df is not None:
                    # Chart title
                    #st.subheader(f"{chart_type.title()} Chart for {coin_id.capitalize()} (7 Days)")
                    
                    #if chart_type == "bar":
                        #st.bar_chart(trend_df.set_index("ts")["price"])
                    #elif chart_type == "pie":
                        #fig, ax = plt.subplots()
                        #ax.pie(
                            #trend_df["price"],
                            #labels=trend_df["ts"].dt.strftime("%a %H:%M"),
                            #autopct="%1.1f%%",
                            #startangle=90,
                            #textprops={"fontsize": 7}
                        #)
                        #ax.axis("equal")
                        #st.pyplot(fig)
                    #else:
                        #st.line_chart(trend_df.set_index("ts")["price"])
                #else:
                    #st.warning("Failed to retrieve price data from CoinGecko.")
            #else:
                #st.info("Could not detect a valid coin in your question.")
        #except Exception as e:
            #st.error(f"Gemini error: {e}")


