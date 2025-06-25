# Crypto Dashboard

An interactive real-time crypto dashboard powered by the CoinGecko API, Streamlit, and Gemini (LLM). Users can search, analyze, and visualize crypto trends with natural language — like "Show me a 7-day bar chart of Bitcoin."

## Features

- Currency selector (USD, EUR, SGD)
- Coin count selector (Top 5 to Top 50)
- Manual refresh button
- Key metrics (Price, Market Cap, 24h Volume)
- Interactive charts (Bar chart, Line chart, Pie chart)
- Natural language chatbot (Gemini-powered):
  - Ask for coin trends via text (e.g., “Give me a 3-day trend of Dogecoin”)
  - Specify chart types via prompt (bar/line)
- Search filter by coin name or symbol
- Fuzzy matching & suggestions
- Last updated timestamp
- Modular structure with clean API separation

## Tech Stack

| Layer              | Tool / Library |
|--------------------|----------------|
| API Integration    | CoinGecko REST • Google Gemini API|
| ETL / Data Handling| Python • pandas |
| LLM Query Parsing  | Gemini 1.5 Flash (google.generativeai) |
| Dashboard UI       | Streamlit • matplotlib |
| NLP Support        | regex • difflib (fuzzy matching) |
| Modularization     | Custom apis/ + scripts/ folders |
| Deployment         | Streamlit Community Cloud* |

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

# 4 · Set up secrets (Gemini API key)
mkdir .streamlit
echo '[secrets]\nGEMINI_API_KEY = "your-api-key"' > .streamlit/secrets.toml

# 5 · Launch app
streamlit run dashboard_app.py
```

# File Structure
crypto-dashboard/
├── apis/                     # Modular API integrations
│   └── coingecko.py          # CoinGecko helpers (fetch, search, map)
├── scripts/
│   └── fetch_crypto.py       # Top coin fetch logic
├── data/                     # Optional: storage or cache
├── dashboard_app.py          # Main Streamlit app
├── requirements.txt
└── README.md

## Live App: 
https://crypto-dashboard-tjneft4b3mxq7kg7usxe8d.streamlit.app/#live-crypto-dashboard
