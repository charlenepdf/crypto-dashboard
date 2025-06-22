import requests
import pandas as pd

def fetch_top_coins(limit=10, currency="usd"):
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": currency,
        "order": "market_cap_desc",
        "per_page": limit,
        "page": 1,
        "sparkline": False
    }

    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame(data)[[
            'id', 'symbol', 'name', 'current_price',
            'market_cap', 'price_change_percentage_24h',
            'total_volume', 'last_updated'
        ]]
        return df
    else:
        print("Error fetching data:", response.status_code)
        return pd.DataFrame()
    
# Test when run directly
if __name__ == "__main__":
    df = fetch_top_coins()
    print(df.head())