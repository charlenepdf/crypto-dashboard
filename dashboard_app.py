import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from difflib import get_close_matches
from datetime import datetime
from scripts.fetch_crypto import fetch_top_coins

st.set_page_config(page_title="Crypto Dashboard", layout="wide")

st.title("Live Crypto Dashboard")
st.markdown("Displays top 10 cryptocurrencies by market cap using CoinGecko API.")

# 1) Utility: build & cache CoinGecko name↔symbol↔id mapping
@st.cache_data(show_spinner=False)
def get_coin_mapping():
    """Return dict mapping lower‑cased id / symbol / name → id."""
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

# 2) Sidebar controls
currency = st.selectbox("Select currency", ["USD", "EUR", "SGD"])
limit = st.slider("Select number of coins to display", 5, 50, 10)

# Add refresh button to fetch latest data with selected currency
if st.button("Refresh Data"):
    df = fetch_top_coins(limit=limit, currency=currency)
else:
    df = fetch_top_coins(limit=limit, currency=currency)

if df.empty:
    st.warning("Failed to load data from CoinGecko API.")
    st.stop()

user_query = st.text_input("Search for a coin (name / symbol)").strip().lower()

if user_query:
    # Resolve using mapping first
    resolved_id = coin_map.get(user_query)

    if resolved_id:
        filtered_df = df[df["id"] == resolved_id]
    else:
        # fallback contains‑based filter
        filtered_df = df[
            df["name"].str.contains(user_query, case=False) |
            df["symbol"].str.contains(user_query, case=False)
        ]
        if filtered_df.empty:
            suggestions = get_close_matches(user_query, list(coin_map.keys()), n=3, cutoff=0.6)
            if suggestions:
                st.info("Did you mean: " + ", ".join(suggestions))
else:
    filtered_df = df  # no filter

# 4) Key metrics (always based on full df => market overview)
top_coin = df.iloc[0]
st.subheader(f"📊 Key Metrics for Top Coin: {top_coin['name']}")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Price", f"${top_coin['current_price']:,.2f}", f"{top_coin['price_change_percentage_24h']:.2f}%")
with col2:
    st.metric("Market Cap", f"${top_coin['market_cap']:,.0f}")
with col3:
    st.metric("24h Volume", f"${top_coin['total_volume']:,.0f}")

st.caption(f"⏱ Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 5) Data table (filtered)
if filtered_df.empty:
    st.warning("No matching coins found.")
else:
    st.dataframe(
        filtered_df.style.format({
            "current_price": "${:,.2f}",
            "market_cap": "${:,.0f}",
            "price_change_percentage_24h": "{:+.2f}%",
            "total_volume": "${:,.0f}"
        }),
        use_container_width=True
    )
    
# 6) Charts (always full df for market overview)
st.subheader("Market Cap of Top Cryptos")
st.bar_chart(df.set_index("name")["market_cap"])

st.subheader("📈 24h Price Change (%)")
st.bar_chart(df.set_index("name")["price_change_percentage_24h"])

# Pie chart (Top 5 + Others)
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