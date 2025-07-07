import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import requests
import re
import json
from difflib import get_close_matches
from datetime import datetime
from dotenv import load_dotenv
import os
import google.generativeai as genai

# Local modules
from scripts.fetch_crypto import fetch_top_coins
from apis.coingecko import get_coin_mapping, fetch_price_history, search_coin_in_df

def resolve_coin_id(name_or_symbol: str, name_map: dict, id_map: dict, symbol_map: dict):
    """Resolves a coin input to the most likely CoinGecko ID using name, ID, or symbol."""

    if not name_or_symbol:
        print("❌ Empty input.")
        return None

    if not isinstance(name_or_symbol, str):
        print("❌ Invalid input: expected a string.")
        return None
    query = name_or_symbol.strip().lower()
    
    if query == "none":
        return None

    print(f"Resolving: {query}")

    # 1. Exact match in name map
    if query in name_map:
        print("✅ Found in name_map")
        return name_map[query]

    # 2. Exact match in ID map (already valid CoinGecko ID)
    if query in id_map:
        print("✅ Found in id_map")
        return id_map[query]

    # 3. Symbol match (may return multiple IDs)
    if query in symbol_map:
        candidates = symbol_map[query]
        if len(candidates) == 1:
            print("✅ Found one match in symbol_map:", candidates[0])
            return candidates[0]
        else:
            # Optional: Rank or filter — here, just pick first for simplicity
            print(f"⚠️ Multiple matches for symbol '{query}': {candidates}")
            return candidates[0]  # You could add logic here to prefer e.g., 'binancecoin'

    # 4. Fuzzy match across all names
    all_names = list(name_map.keys())
    fuzzy_matches = get_close_matches(query, all_names, n=1, cutoff=0.8)
    if fuzzy_matches:
        match = fuzzy_matches[0]
        print(f"🔍 Fuzzy matched '{query}' to '{match}'")
        return name_map[match]

    print("❌ No match found.")
    return None


# Helper to resolve coin name/symbol to valid CoinGecko ID
# def resolve_coin_id(name_or_symbol: str, coin_map: dict):
#     """Resolves user coin input to valid CoinGecko ID using exact or fuzzy match."""
#     if not name_or_symbol: 
#         print('Did not find a mapping in the coin map')
#         return None
#     name_or_symbol = name_or_symbol.strip().lower()
#     if name_or_symbol in coin_map:
#         print('Found a mapping in the coin map')
#         return coin_map[name_or_symbol]
#     matches = get_close_matches(name_or_symbol, list(coin_map.keys()), n=1, cutoff=0.8)
#     if matches:
#         st.write(f"Fuzzy match for '{name_or_symbol}':", matches[0])
#         return coin_map[matches[0]]
#     return None

# Page / App Config
st.set_page_config(page_title="Crypto Dashboard", layout="wide")
st.title("Live Crypto Dashboard")
st.markdown("Displays top cryptocurrencies by market cap using CoinGecko API.")

# Get coin mapping (cached in coingecko.py)
#coin_map = get_coin_mapping()
name_map, id_map, symbol_map = get_coin_mapping()


# 1) Sidebar controls + top‑N dataframe

currency = st.selectbox("Select currency", ["USD", "EUR", "SGD"])
limit = st.slider("Select number of coins to display", 5, 50, 10)

if st.button("Refresh Data"):
    df = fetch_top_coins(limit=limit, currency=currency)
else:
    df = fetch_top_coins(limit=limit, currency=currency)

if df.empty:
    st.error("Failed to load data from CoinGecko API.")
    st.stop()

# 2) Table search / filter (uses contains + fuzzy suggestions)
user_query = st.text_input("Search for a coin (name / symbol)")

if user_query:
    filtered_df, suggestions = search_coin_in_df(df, coin_map, user_query)
    if filtered_df.empty:
        if suggestions:
            st.info("Did you mean: " + ", ".join(suggestions))
        else:
            st.warning("No matching coins found.")
else:
    filtered_df = df


if not df.empty:
    top_coin = df.iloc[0]
    st.subheader(f"📊 Key Metrics for Top Coin: {top_coin['name']}")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Price", f"${top_coin['current_price']:,.2f}", f"{top_coin['price_change_percentage_24h']:.2f}%")
    with col2:
        st.metric("Market Cap", f"${top_coin['market_cap']:,.0f}")
    with col3:
        st.metric("24h Volume", f"${top_coin['total_volume']:,.0f}")
    st.caption(f"\u23F1 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 4) Filtered data table
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

# 5) Market overview charts (full df)
st.subheader("Market Cap of Top Cryptos")
st.bar_chart(df.set_index("name")["market_cap"])

st.subheader("📈 24h Price Change (%)")
st.bar_chart(df.set_index("name")["price_change_percentage_24h"])

# 6) Pie chart (Top 5 + Others)
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

# 7) Gemini Chatbot (trend + chart)

# For production
#genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# For local
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Cache Gemini model instance
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

# Gemini Prompt
def extract_intent_from_prompt_llm(prompt: str):
    system_prompt = """
    You are an assistant that classifies crypto-related user queries as either chart-related or general information.

    Respond with a valid JSON object like:
    {
      "type": "chart" | "info",
      "coin_id": ["<coin name or symbol>", ...],       // Only for chart
      "chart": "line" | "bar" | "pie",          // Only for chart
      "days": <number of days as an integer>,    // Only for chart
      "metric": "price" | "volume",
      "scope": "trend" | "current"
    }

    If it's a general information request (like 'what is bitcoin?'), set "type" to "info" and ignore other fields.

    If 'days' is not mentioned, default to 7. If coin is unknown, use "none" for coin.
    """
    
    # Handle exceptions
    try:
        response = gemini_model.generate_content(f"{system_prompt}\n\nQuery: {prompt}")
    except Exception as e:
        st.error("⚠️ Gemini API error: Resource exhausted or quota exceeded.")
        st.session_state.messages.append({
            "role": "assistant", "type": "text", "content": "I'm currently unable to respond due to resource limits. Please try again later."
        })
        return "info", prompt, None, None  # fallback

    #response = gemini_model.generate_content(f"{system_prompt}\n\nQuery: {prompt}")
    
    raw = response.text.strip()

    #st.code(raw, language="json")  # Debug Gemini's response

    clean = re.sub(r"```(?:json)?", "", raw).strip()

    try:
        parsed = json.loads(clean)
        #st.write("Parsed Gemini JSON:", parsed)

        # if parsed.get("type") == "chart":
        #     coin = parsed.get("coin_id")
        #     chart_type = parsed.get("chart", "line")
        #     days = int(parsed.get("days", 7))
        #     metric = parsed.get("metric", "price")
        #     scope = parsed.get("scope", "trend")
        #     return "chart", coin, chart_type, days, metric, scope
        
        if parsed.get("type") == "chart":
            coin = parsed.get("coin_id", [])
            if isinstance(coin, str):
                coin = [coin]
            chart_type = parsed.get("chart", "line")
            days = int(parsed.get("days", 7))
            metric = parsed.get("metric", "price")
            scope = parsed.get("scope", "trend")
            return "chart", coin, chart_type, days, metric, scope

        else:
            return "info", prompt, None, None, None, None
    except Exception as e:
        st.warning(f"Intent extraction failed: {e}")
        return "info", prompt, None, None


st.subheader("💬 Ask CryptoBot")

# Initialise chat history on first run
if "messages" not in st.session_state:
    st.session_state.messages = []

# Handle user input and generate response
user_prompt = st.chat_input("Ask CryptoBot…")
if user_prompt and user_prompt.strip(): # Ignores empty or whitespace-only input
    # Add user's message to history
    st.session_state.messages.append({
        "role": "user", "type": "text", "content": user_prompt
    })

    # Process input and update history (but don't display yet)
    with st.spinner("Thinking…"):
        #intent_type, value1, value2, value3 = extract_intent_from_prompt_llm(user_prompt)
        intent_type, coin_input, chart_type, days, metric, scope = extract_intent_from_prompt_llm(user_prompt)
        chart_type = chart_type or "line"
        metric = metric or "price"
        scope = scope or "trend"

        if intent_type == "chart":
            #coin_input, chart_type, days = value1, value2, value3
            #coin_id = resolve_coin_id(coin_input, coin_map)
            #coin_id = resolve_coin_id(coin_input, name_map, id_map, symbol_map)
            if isinstance(coin_input, str):
                coin_input = [coin_input]

            resolved_ids = []
            for coin in coin_input:
                if coin == "none":
                    continue
                resolved = resolve_coin_id(coin, name_map, id_map, symbol_map)
                if resolved:
                    resolved_ids.append(resolved)
            if not resolved_ids:
                msg = f"⚠️ I couldn't resolve any of these coins: {', '.join(coin_input)}"
                st.session_state.messages.append({
                    "role": "assistant", "type": "text", "content": msg
                })
            else:
                if scope == "trend":
                    trend_df = fetch_price_history(resolved_ids[0], currency.lower(), days)
                else:
                    trend_df = None

                st.session_state.messages.append({
                    "role": "assistant",
                    "type": "chart",
                    "chart": chart_type,
                    "df": trend_df.to_dict("records") if trend_df is not None else [],
                    "coin_id": resolved_ids,
                    "metric": metric,
                    "scope": scope
                })        
                    
        elif intent_type == "info":
            try:
                info_response = gemini_model.generate_content(user_prompt).text
            except Exception as e:
                st.error("⚠️ Gemini API error: Resource exhausted or quota exceeded.")
                info_response = "I'm currently unable to respond due to resource limits. Please try again later."

            st.session_state.messages.append({
                "role": "assistant",
                "type": "text",
                "content": info_response
            })
    # Trim to last 30 messages
    if len(st.session_state.messages) > 30:
        st.session_state.messages = st.session_state.messages[-30:]

# Render all messages from history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["type"] == "text":
            st.markdown(msg["content"])
        elif msg["type"] == "chart":
            try:
                coin_ids = msg.get("coin_id", [])
                chart_type = msg.get("chart", "line")
                currency_label = currency.upper()
                metric = msg.get("metric", "price")
                scope = msg.get("scope", "trend")

                # Normalize to list
                if isinstance(coin_ids, str):
                    coin_ids = [coin_ids]
                if chart_type == "bar":
                    if scope == "current" and metric == "price":
                        # Bar chart comparing prices of multiple coins
                        df_filtered = df[df["id"].isin(coin_ids)]
                        if not df_filtered.empty:
                            st.markdown(f"**Current Prices ({currency_label})**")
                            st.bar_chart(df_filtered.set_index("name")["current_price"])
                        else:
                            st.warning("No matching coins found for bar chart.")
                    elif scope == "trend":
                        # Bar chart of single coin's trend
                        df_ = pd.DataFrame(msg["df"]).set_index("ts")["price"]
                        df_.index = pd.to_datetime(df_.index)
                        st.markdown(f"**{coin_ids[0].title()} Price Trend ({currency_label})**")
                        st.bar_chart(df_)
                
                elif chart_type == "pie":
                    if scope == "current" and metric == "volume":
                        # Pie chart of volume share
                        df_filtered = df[df["id"].isin(coin_ids)]
                        fig, ax = plt.subplots()
                        ax.pie(
                            df_filtered["total_volume"],
                            labels=df_filtered["name"],
                            autopct="%1.1f%%",
                            startangle=90,
                            textprops={"fontsize": 8}
                        )
                        ax.axis("equal")
                        st.markdown("**Trading Volume Share**")
                        st.pyplot(fig)
                    else:
                        # Single coin: pie chart of daily prices
                        df_ = pd.DataFrame(msg["df"]).set_index("ts")["price"]
                        df_.index = pd.to_datetime(df_.index)
                        fig, ax = plt.subplots()
                        ax.pie(
                            df_.values,
                            labels=df_.index.strftime("%d-%b"),
                            autopct="%1.1f%%",
                            startangle=90,
                            textprops={"fontsize": 8}
                        )
                        ax.axis("equal")
                        st.markdown(f"**{coin_ids[0].title()} Price Distribution ({currency_label})**")
                        st.pyplot(fig)
                        
                else:
                    df_ = pd.DataFrame(msg["df"]).set_index("ts")["price"]
                    df_.index = pd.to_datetime(df_.index)
                    fig, ax = plt.subplots()
                    ax.plot(df_.index, df_.values, marker="o")
                    ax.set_title(f"{coin_ids[0].title()} Price Trend ({currency_label})")
                    ax.set_ylabel(f"Price ({currency_label})")
                    ax.set_xlabel("Date")
                    ax.tick_params(axis="x", rotation=45)
                    ax.grid(True, linestyle="--", alpha=0.5)
                    st.pyplot(fig)

            except Exception as e:
                st.warning(f"⚠️ Chart could not be rendered: {e}")

# Render all messages from history
# for msg in st.session_state.messages:
#     with st.chat_message(msg["role"]):
#         if msg["type"] == "text":
#             st.markdown(msg["content"])
#         elif msg["type"] == "chart":
#             try:
#                 df_ = pd.DataFrame(msg["df"]).set_index("ts")["price"]
#                 df_.index = pd.to_datetime(df_.index)
#                 coin = msg.get("coin_id", "").upper()
#                 chart_type = msg["chart"]
#                 currency_label = currency.upper()

#                 if chart_type == "bar":
#                     st.markdown(f"**{coin.title()} Price Trend ({currency_label})**")
#                     st.bar_chart(df_)
#                 elif chart_type == "pie":
#                     fig, ax = plt.subplots()
#                     ax.pie(
#                         df_.values,
#                         labels=df_.index.strftime("%d-%b"),
#                         autopct="%1.1f%%",
#                         startangle=90,
#                         textprops={"fontsize": 8}
#                     )
#                     ax.axis("equal")
#                     st.pyplot(fig)
#                 else:
#                     #st.line_chart(df_)
#                     fig, ax = plt.subplots()
#                     ax.plot(df_.index, df_.values, marker="o")
#                     ax.set_title(f"{coin.title()} Price Trend ({currency_label})")
#                     ax.set_ylabel(f"Price ({currency_label})")
#                     ax.set_xlabel("Date")
#                     ax.tick_params(axis="x", rotation=45)
#                     ax.grid(True, linestyle="--", alpha=0.5)
#                     st.pyplot(fig)

#             except Exception as e:
#                 st.warning(f"⚠️ Chart could not be rendered: {e}")
