import streamlit as st
import yfinance as yf
import pandas as pd
import feedparser
import urllib.parse
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

from sentence_transformers import SentenceTransformer, util

# ==============================
# LOAD MODEL (CACHED)
# ==============================
@st.cache_resource
def load_model():
    return SentenceTransformer('all-MiniLM-L6-v2')

model = load_model()

# ==============================
# PROFILES
# ==============================
tesla_profile = """
Tesla electric vehicles EV battery production deliveries earnings revenue Elon Musk
autonomous driving FSD robotaxi competition EV demand pricing
"""

macro_profile = """
global economy inflation interest rates federal reserve oil prices war geopolitics recession
economic slowdown macroeconomic environment risk sentiment
"""

market_profile = """
stock market S&P 500 Nasdaq rally selloff volatility risk-on risk-off investor sentiment
equity markets tech stocks movement
"""

profiles = {
    "TESLA": model.encode(tesla_profile, convert_to_tensor=True),
    "MACRO": model.encode(macro_profile, convert_to_tensor=True),
    "MARKET": model.encode(market_profile, convert_to_tensor=True)
}

# ==============================
# IMPACT WINDOWS
# ==============================
IMPACT_WINDOWS = {
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1)
}

# ==============================
# PAGE CONFIG
# ==============================
st.set_page_config(layout="wide")
st.title("📈 Stock News Impact Analyzer")

# ==============================
# SIDEBAR
# ==============================
ticker = st.sidebar.text_input("Ticker", "TSLA")

period = st.sidebar.selectbox(
    "Timeframe",
    ["1d", "5d", "1mo", "3mo", "6mo", "1y"],
    index=1
)

interval = st.sidebar.selectbox(
    "Interval",
    ["1m", "5m", "15m", "1h", "1d"],
    index=2
)

refresh_rate = st.sidebar.slider("Auto Refresh (seconds)", 5, 60, 15)

# ==============================
# AUTO REFRESH
# ==============================
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

if time.time() - st.session_state.last_refresh > refresh_rate:
    st.session_state.last_refresh = time.time()
    st.rerun()

# ==============================
# NEWS FUNCTIONS
# ==============================
def get_news_rss(query):
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}"
    feed = feedparser.parse(url)

    return [{
        "title": entry.title,
        "link": entry.link,
        "published": entry.published
    } for entry in feed.entries]


def get_yahoo_news(ticker):
    stock = yf.Ticker(ticker)
    news = stock.news or []

    articles = []

    for item in news:
        try:
            dt = datetime.utcfromtimestamp(item["providerPublishTime"])
            articles.append({
                "title": item["title"],
                "link": item["link"],
                "published": dt
            })
        except:
            continue

    return articles


def parse_time(time_str):
    return datetime.strptime(time_str, "%a, %d %b %Y %H:%M:%S %Z")

# ==============================
# PRICE FUNCTIONS
# ==============================
def get_price_after_time(data, time_col, target_time):
    future_data = data[data[time_col] >= target_time]

    if future_data.empty:
        return None

    return future_data.iloc[0]["Close"]


def calculate_impact(data, time_col, news_time):
    base_price = get_price_after_time(data, time_col, news_time)

    if base_price is None:
        return None

    impacts = {}

    for label, delta in IMPACT_WINDOWS.items():
        future_time = news_time + delta
        future_price = get_price_after_time(data, time_col, future_time)

        if future_price is None:
            impacts[label] = None
        else:
            impacts[label] = (future_price - base_price) / base_price * 100

    return impacts

# ==============================
# LOAD PRICE DATA
# ==============================
data = yf.download(ticker, period=period, interval=interval)

if isinstance(data.columns, pd.MultiIndex):
    data.columns = [col[0] for col in data.columns]

data = data.reset_index()

time_col = "Datetime" if "Datetime" in data.columns else "Date"
data[time_col] = pd.to_datetime(data[time_col]).dt.tz_localize(None)

# ==============================
# GET NEWS
# ==============================
rss_articles = get_news_rss(f"{ticker} OR stock market OR economy")
yahoo_articles = get_yahoo_news(ticker)

articles = rss_articles + yahoo_articles

# ==============================
# BUILD CHART
# ==============================
fig = go.Figure()

# PRICE LINE
fig.add_trace(go.Scatter(
    x=data[time_col],
    y=data["Close"],
    mode='lines',
    name='Price'
))

# ==============================
# NEWS MARKERS
# ==============================
news_x = []
news_y = []
news_text = []

for art in articles[:50]:
    try:
        if isinstance(art["published"], str):
            news_time = parse_time(art["published"])
        else:
            news_time = art["published"]

        news_time = pd.to_datetime(news_time).tz_localize(None)

        if news_time < data[time_col].min() or news_time > data[time_col].max():
            continue

        closest = data.iloc[(data[time_col] - news_time).abs().argsort()[:1]]

        news_x.append(closest[time_col].values[0])
        news_y.append(closest["Close"].values[0])
        news_text.append(art["title"])

    except:
        continue

fig.add_trace(go.Scatter(
    x=news_x,
    y=news_y,
    mode='markers',
    marker=dict(size=10, color='red'),
    name='News',
    text=news_text,
    hovertemplate="<b>%{text}</b><extra></extra>"
))

fig.update_layout(height=600)

st.plotly_chart(fig, use_container_width=True)

# ==============================
# ARTICLE SELECTOR
# ==============================
st.subheader("📰 Select Article")

if news_text:
    selected_title = st.selectbox("Choose article", news_text)

    selected_article = next(
        (art for art in articles if art["title"] == selected_title),
        None
    )

    if selected_article:
        st.subheader("🧠 Article Analysis")

        st.write("**Title:**", selected_article["title"])
        st.write(f"🔗 [Read full article]({selected_article['link']})")

        # TIME
        try:
            if isinstance(selected_article["published"], str):
                news_time = parse_time(selected_article["published"])
            else:
                news_time = selected_article["published"]

            news_time = pd.to_datetime(news_time).tz_localize(None)
        except:
            st.write("Time parsing failed")
            news_time = None

        # AI CLASSIFICATION
        if news_time is not None:
            embedding = model.encode(selected_article["title"], convert_to_tensor=True)

            scores = {}
            for key, emb in profiles.items():
                scores[key] = util.cos_sim(emb, embedding).item()

            best_category = max(scores, key=scores.get)
            best_score = scores[best_category]

            st.write(f"**Category:** {best_category} ({round(best_score,2)})")

            # IMPACT
            impact = calculate_impact(data, time_col, news_time)

            st.write("### 📊 Impact")

            if impact:
                for k, v in impact.items():
                    if v is not None:
                        st.write(f"{k}: {v:.3f}%")
                    else:
                        st.write(f"{k}: No data")
            else:
                st.write("No price data available")
else:
    st.write("No news found")
