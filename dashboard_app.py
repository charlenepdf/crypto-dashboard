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
from apis.coingecko import get_coin_mapping, fetch_price_history


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
user_query = st.text_input("Search for a coin (name / symbol)").strip().lower()

if user_query:
    resolved_id = coin_map.get(user_query)
    if resolved_id:
        filtered_df = df[df["id"] == resolved_id]
    else:
        filtered_df = df[
            df["name"].str.contains(user_query, case=False) |
            df["symbol"].str.contains(user_query, case=False)
        ]
        if filtered_df.empty:
            suggestions = get_close_matches(user_query, list(coin_map.keys()), n=3, cutoff=0.6)
            if suggestions:
                st.info("Did you mean: " + ", ".join(suggestions))
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
user_prompt = st.text_input("Ask something like 'Give me a 7-day trend of Bitcoin'")

if user_prompt:
    with st.spinner("Thinking..."):
        try:
            # Optional Gemini LLM response
            # answer = genai.GenerativeModel("gemini-1.5-flash").generate_content(user_prompt)
            # st.success(answer.text)

            # Try Gemini first, fallback to local fuzzy
            coin_id, chart_type = extract_intent_from_prompt_llm(user_prompt)
            #st.write(f"Resolved Coin ID: {coin_id}") # debug

            if coin_id:
                trend_df = fetch_price_history(coin_id, currency.lower())
                if trend_df is not None:
                    # Chart title
                    st.subheader(f"{chart_type.title()} Chart for {coin_id.capitalize()} (7 Days)")
                    
                    if chart_type == "bar":
                        st.bar_chart(trend_df.set_index("ts")["price"])
                    elif chart_type == "pie":
                        fig, ax = plt.subplots()
                        ax.pie(
                            trend_df["price"],
                            labels=trend_df["ts"].dt.strftime("%a %H:%M"),
                            autopct="%1.1f%%",
                            startangle=90,
                            textprops={"fontsize": 7}
                        )
                        ax.axis("equal")
                        st.pyplot(fig)
                    else:
                        st.line_chart(trend_df.set_index("ts")["price"])
                else:
                    st.warning("Failed to retrieve price data from CoinGecko.")
            else:
                st.info("Could not detect a valid coin in your question.")
        except Exception as e:
            st.error(f"Gemini error: {e}")


