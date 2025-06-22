# Crypto Dashboard

A real-time dashboard that fetches the latest prices of top cryptocurrencies using the CoinGecko API. Built with Python, Streamlit, and Google Analytics for tracking user interaction.

## Features

- Fetches live crypto price data from CoinGecko
- Displays top 10 cryptocurrencies by market cap
- Clean ETL pipeline with pandas
- Streamlit dashboard with interactive UI
- Google Analytics integration for basic user tracking

## Tech Stack

- Python
- CoinGecko API
- pandas
- Streamlit
- Google Analytics (via gtag.js)

## Getting Started

1. Clone this repo:
git clone https://github.com/charlenepdf/crypto-dashboard.git
2. Install dependencies:
pip install -r requirements.txt
3. Run the app:
streamlit run dashboard_app.py

# File Structure
crypto-dashboard/
├── scripts/
│ ├── fetch_crypto.py # Pulls crypto price data
│ ├── fetch_news.py # (optional) Gets crypto-related news
│ └── etl_pipeline.py # Cleans and processes data
├── dashboard_app.py # Streamlit dashboard
├── requirements.txt
└── README.md

## To-Do
- [x] Setup GitHub + folder structure
- [ ] Build `fetch_crypto.py` script
- [ ] Add dashboard UI
- [ ] Deploy with Streamlit Cloud
