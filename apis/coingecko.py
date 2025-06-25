# apis/coingecko.py

import requests
import pandas as pd
import streamlit as st

# Build & cache FULL CoinGecko mapping  (id / symbol / name → id)
@st.cache_data(show_spinner=False)
def get_coin_mapping():
    url = "https://api.coingecko.com/api/v3/coins/list"
    try:
        coins = requests.get(url, timeout=15).json()
    except Exception:
        return {}

    mapping = {}
    for coin in coins:
        coin_id = coin.get("id")
        symbol = coin.get("symbol")
        name = coin.get("name")
        if coin_id and symbol and name:
            mapping[coin_id.lower()] = coin_id
            mapping[symbol.lower()] = coin_id
            mapping[name.lower()] = coin_id
    return mapping

# helper → 3‑day hourly price history
def fetch_price_history(coin_id, currency="usd", days=7):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": currency.lower(), "days": days, "interval": "hourly" if days <= 90 else "daily"}
    
    r = requests.get(url, params=params, timeout=10)
    #st.write("CoinGecko response:", r.status_code, r.url) # debug
    
    if r.status_code == 200:
        data = r.json()["prices"]
        return pd.DataFrame(data, columns=["ts", "price"]).assign(
            ts=lambda d: pd.to_datetime(d.ts, unit="ms")
        )
    return None

def search_coin_in_df(df, coin_map, user_query):
    user_query = user_query.strip().lower()
    resolved_id = coin_map.get(user_query)

    # First, match resolved ID to the top coins df
    if resolved_id:
        filtered = df[df["id"] == resolved_id]
        if not filtered.empty:
            return filtered, None
        
    # Fallback to partial name or symbol match
    filtered = df[
        df["name"].str.contains(user_query, case=False, na=False) |
        df["symbol"].str.contains(user_query, case=False, na=False)
    ]
        
    if not filtered.empty:
        return filtered, None
    
    # Suggestions if nothing matches
    from difflib import get_close_matches
    suggestions = get_close_matches(user_query, list(coin_map.keys()), n=3, cutoff=0.6)
    return pd.DataFrame(), suggestions
