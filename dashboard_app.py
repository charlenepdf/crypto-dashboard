import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from scripts.fetch_crypto import fetch_top_coins

st.set_page_config(page_title="Crypto Dashboard", layout="wide")

st.title("Live Crypto Dashboard")
st.markdown("Displays top 10 cryptocurrencies by market cap using CoinGecko API.")

# Currency dropdown
currency = st.selectbox("Select currency", ["USD", "EUR", "SGD"])

# Add interactive input: choose how many coins to display
limit = st.slider("Select number of coins to display", 5, 50, 10)

# Add refresh button to fetch latest data with selected currency
if st.button("Refresh Data"):
    df = fetch_top_coins(limit=limit, currency=currency)
else:
    df = fetch_top_coins(limit=limit, currency=currency)

if df.empty:
    st.warning("Failed to load data from CoinGecko API.")
else:
    # Add Search Filter (Table only)
    search_term = st.text_input("Search for a coin")
    filtered_df = df[
        df["name"].str.contains(search_term, case=False) |
        df["symbol"].str.contains(search_term, case=False)
    ] if search_term else df
    
    # Show key metrics for the top coin (from full df)
    top_coin = df.iloc[0]
    st.subheader(f"📊 Key Metrics for Top Coin: {top_coin['name']}")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Price", f"${top_coin['current_price']:,.2f}", f"{top_coin['price_change_percentage_24h']:.2f}%")

    with col2:
        st.metric("Market Cap", f"${top_coin['market_cap']:,.0f}")

    with col3:
        st.metric("24h Volume", f"${top_coin['total_volume']:,.0f}")
    
    # Show last updated timestamp
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Show filtered results or warning
    if filtered_df.empty:
        st.warning("No matching coins found.")
    else:
        st.dataframe(filtered_df.style.format({
            "current_price": "${:,.2f}",
            "market_cap": "${:,.0f}",
            "price_change_percentage_24h": "{:+.2f}%",
            "total_volume": "${:,.0f}"
        }))
    
    # Add a bar chart for market cap
    st.subheader("Market Cap of Top Cryptos")
    st.bar_chart(df.set_index("name")["market_cap"])
    
    # Add 24h price change chart
    st.subheader("📈 24h Price Change (%)")
    st.bar_chart(df.set_index("name")["price_change_percentage_24h"])
    
    # Add pie chart for market cap distribution (Top 5 + Others from full df)
    df_sorted = df.sort_values(by="market_cap", ascending=False)
    top_df = df_sorted.head(5)
    others = pd.DataFrame([{
        "name": "Others",
        "market_cap": df_sorted["market_cap"].iloc[5:].sum()
    }])
    
    pie_df = pd.concat([top_df[["name", "market_cap"]], others], ignore_index=True)
    pie_sizes = pie_df["market_cap"].tolist()
    pie_names = pie_df["name"].tolist()
    
    # Plot
    fig, ax = plt.subplots()
    ax.pie(
        pie_sizes,
        labels=pie_names,
        autopct="%1.1f%%",
        startangle=90,
        pctdistance=0.85,  # Move percentage labels outward
        labeldistance=1.05,  # Move labels outward
        textprops={'fontsize': 8}  # Smaller font
    )
    ax.axis("equal")
    st.subheader("Market Cap Distribution (Top 5 + Others)")
    st.pyplot(fig)