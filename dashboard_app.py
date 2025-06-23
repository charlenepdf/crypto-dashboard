import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import requests
import re
from difflib import get_close_matches
from datetime import datetime
from scripts.fetch_crypto import fetch_top_coins
import google.generativeai as genai

# Page / App Config

st.set_page_config(page_title="Crypto Dashboard", layout="wide")

st.title("Live Crypto Dashboard")
st.markdown("Displays top cryptocurrencies by market cap using CoinGecko API.")

# 1 ▸ Build & cache FULL CoinGecko mapping  (id / symbol / name → id)

@st.cache_data(show_spinner=False)
def get_coin_mapping():
    url = "https://api.coingecko.com/api/v3/coins/list"
    try:
        coins = requests.get(url, timeout=15).json()
    except Exception:
        return {}

    mapping = {}
    for coin in coins:
        mapping[coin["id"].lower()] = coin["id"]
        mapping[coin["symbol"].lower()] = coin["id"]
        mapping[coin["name"].lower()] = coin["id"]
    return mapping

coin_map = get_coin_mapping()

# 2 ▸ Sidebar controls + top‑N dataframe

currency = st.selectbox("Select currency", ["USD", "EUR", "SGD"])
limit    = st.slider("Select number of coins to display", 5, 50, 10)

if st.button("Refresh Data"):
    df = fetch_top_coins(limit=limit, currency=currency)
else:
    df = fetch_top_coins(limit=limit, currency=currency)

if df.empty:
    st.error("Failed to load data from CoinGecko API.")
    st.stop()

# 3 ▸ Table search / filter (uses contains + fuzzy suggestions)

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

# 4 ▸ Key metrics (based on full df)

top_coin = df.iloc[0]
st.subheader(f"📊 Key Metrics for Top Coin: {top_coin['name']}")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Price",      f"${top_coin['current_price']:,.2f}", f"{top_coin['price_change_percentage_24h']:.2f}%")
with col2:
    st.metric("Market Cap", f"${top_coin['market_cap']:,.0f}")
with col3:
    st.metric("24h Volume", f"${top_coin['total_volume']:,.0f}")

st.caption(f"⏱ Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 5 ▸ Filtered data table

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

# 6 ▸ Market overview charts (full df)

st.subheader("Market Cap of Top Cryptos")
st.bar_chart(df.set_index("name")["market_cap"])

st.subheader("📈 24h Price Change (%)")
st.bar_chart(df.set_index("name")["price_change_percentage_24h"])

# Pie chart (Top 5 + Others)
df_sorted  = df.sort_values(by="market_cap", ascending=False)
main_df    = df_sorted.head(5)
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

# 7 ▸ Gemini Chatbot (trend + chart)

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# helper → extract coin id from arbitrary prompt
def extract_coin_from_prompt(prompt:str):
    words = re.findall(r"\w+", prompt.lower())
    for w in words:
        if w in coin_map:
            return coin_map[w]
    # fuzzy fallback
    matches = get_close_matches(" ".join(words), coin_map.keys(), n=1, cutoff=0.6)
    if matches:
        return coin_map[matches[0]]
    return None

# helper → 3‑day hourly price history
def fetch_price_history(coin_id:str):
    url    = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": currency.lower(), "days": 3, "interval": "hourly"}
    r = requests.get(url, params=params, timeout=10)
    if r.status_code == 200:
        data = r.json()["prices"]
        return pd.DataFrame(data, columns=["ts", "price"]).assign(ts=lambda d: pd.to_datetime(d.ts, unit="ms"))
    return None

st.subheader("💬 Ask CryptoBot")
user_prompt = st.text_input("Ask something like 'Show me 3‑day trend of Bitcoin'")

if user_prompt:
    with st.spinner("Thinking..."):
        try:
            # Optional: get Gemini text answer (comment out if not needed)
            # answer = genai.GenerativeModel("gemini-1.5-flash").generate_content(user_prompt)
            # st.success(answer.text)

            coin_id = extract_coin_from_prompt(user_prompt)
            if coin_id:
                trend_df = fetch_price_history(coin_id)
                if trend_df is not None:
                    st.line_chart(trend_df.set_index("ts")["price"])
                else:
                    st.warning("Failed to retrieve price data from CoinGecko.")
            else:
                st.info("Could not detect a valid coin in your question.")
        except Exception as e:
            st.error(f"Gemini error: {e}")

