# Crypto Dashboard

A dynamic dashboard displaying real-time cryptocurrency data using the CoinGecko API. Built with Streamlit.

## Features

- Currency selector (USD, EUR, SGD)
- Coin count selector (top 5–50)
- Manual refresh button
- Key metrics (price, market cap, 24h volume)
- Interactive charts (bar, pie)
- Search filter by name/symbol
- Timestamp for last update

## Tech Stack

| Layer              | Tool / Library |
|--------------------|----------------|
| API Integration    | CoinGecko REST |
| ETL / Data Handling| Python • pandas |
| Dashboard UI       | Streamlit • matplotlib |
| Deployment         | Streamlit Community Cloud* |
\* Deployment link provided below once live.

## Getting Started Locally

```bash
# 1 · Clone repo
git clone https://github.com/charlenepdf/crypto-dashboard.git
cd crypto-dashboard

# 2 · Create & activate virtual env (optional but recommended)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3 · Install dependencies
pip install -r requirements.txt

# 4 · Launch app
streamlit run dashboard_app.py
```

# File Structure
crypto-dashboard/
├── scripts/
│   └── fetch_crypto.py        # Fetches and returns live crypto data
├── dashboard_app.py           # Main Streamlit app
├── requirements.txt
└── README.md

