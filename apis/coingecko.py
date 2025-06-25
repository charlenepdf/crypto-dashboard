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
        mapping[coin["id"].lower()] = coin["id"]
        mapping[coin["symbol"].lower()] = coin["id"]
        mapping[coin["name"].lower()] = coin["id"]
    return mapping

# helper → 3‑day hourly price history
def fetch_price_history(coin_id, currency="usd"):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": currency.lower(), "days": 3, "interval": "hourly"}
    r = requests.get(url, headers=headers, params=params, timeout=10)

    st.write("CoinGecko response:", r.status_code, r.url)
    
    if r.status_code == 200:
        data = r.json()["prices"]
        return pd.DataFrame(data, columns=["ts", "price"]).assign(
            ts=lambda d: pd.to_datetime(d.ts, unit="ms")
        )
    return None
