# apis/coingecko.py

import requests
import pandas as pd
import streamlit as st

# Build & cache FULL CoinGecko mapping  (id / symbol / name → id)
@st.cache_data(show_spinner=False)

def get_coin_mapping():
    url = "https://api.coingecko.com/api/v3/coins/list"
    response = requests.get(url)
    if response.status_code != 200:
        raise ValueError("Failed to fetch coin list from CoinGecko")

    data = response.json()

    # Structure: {lowercase name or id: coin_id}
    name_map = {}
    id_map = {}
    symbol_map = {}

    for coin in data:
        coin_id = coin.get("id")
        name = coin.get("name", "").strip().lower()
        symbol = coin.get("symbol", "").strip().lower()

        if name:
            name_map[name] = coin_id
        if coin_id:
            id_map[coin_id] = coin_id
        if symbol and symbol not in symbol_map:
            symbol_map[symbol] = []
        if symbol:
            symbol_map[symbol].append(coin_id)
    
    print("DEBUG: name_map['bitcoin'] =", name_map.get("bitcoin"))
    print("DEBUG: id_map['binancecoin'] =", id_map.get("binancecoin"))
    print("DEBUG: symbol_map['bnb'] =", symbol_map.get("bnb"))

    return name_map, id_map, symbol_map



# def get_coin_mapping():
#     url = "https://api.coingecko.com/api/v3/coins/list"
#     response = requests.get(url)

#     if response.status_code != 200:
#         raise ValueError("Failed to fetch coin list from CoinGecko")

#     data = response.json()

#     # Map from symbol and name → id, but only keep first match to avoid conflicts
#     coin_map = {}
#     seen_keys = set()

#     for coin in data:
#         if isinstance(coin, dict):
#             coin_id = coin.get("id")
#             name = coin.get("name", "").strip().lower()
#             symbol = coin.get("symbol", "").strip().lower()

#             # Only map if key hasn't been used yet (avoid overwriting)
#             if name and name not in seen_keys:
#                 coin_map[name] = coin_id
#                 seen_keys.add(name)
#             if symbol and symbol not in seen_keys:
#                 coin_map[symbol] = coin_id
#                 seen_keys.add(symbol)

#     # Debug samples
#     print("DEBUG: coin_map['bitcoin'] =", coin_map.get("bitcoin"))  # name
#     print("DEBUG: coin_map['btc'] =", coin_map.get("btc"))          # symbol

#     return coin_map


# helper → 3‑day hourly price history
def fetch_price_history(coin_id, currency="usd", days=7):
    print("Inside fetch_price_history, coin_id:", coin_id)
    print("Inside fetch_price_history, currency:", currency)
    print("Inside fetch_price_history, days:", days)
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": currency.lower(), "days": days, "interval": "daily"}
    
    r = requests.get(url, params=params, timeout=10)
    #st.write("CoinGecko response:", r.status_code, r.url) # debug
    
    print("Status code:", r.status_code)
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
