import streamlit as st
import yfinance as yf
import pandas as pd
import feedparser
import urllib.parse
import plotly.graph_objects as go
from datetime import datetime
import time

# ==============================
# PAGE CONFIG
# ==============================
st.set_page_config(layout="wide")
st.title("📈 Stock News Impact Analyzer")

# ==============================
# SIDEBAR CONTROLS
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

    articles = []

    for entry in feed.entries:
        articles.append({
            "title": entry.title,
            "link": entry.link,
            "published": entry.published
        })

    return articles


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
# LOAD DATA
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
# ADD NEWS MARKERS
# ==============================
news_x = []
news_y = []
news_text = []

for art in articles[:50]:  # limit for performance
    try:
        if isinstance(art["published"], str):
            news_time = parse_time(art["published"])
        else:
            news_time = art["published"]

        news_time = pd.to_datetime(news_time).tz_localize(None)

        # Skip out-of-range news
        if news_time < data[time_col].min() or news_time > data[time_col].max():
            continue

        # Find closest price
        closest = data.iloc[(data[time_col] - news_time).abs().argsort()[:1]]

        news_x.append(closest[time_col].values[0])
        news_y.append(closest["Close"].values[0])
        news_text.append(art["title"])

    except:
        continue

# ADD MARKERS
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
    selected_title = st.selectbox(
        "Choose article from chart",
        news_text
    )

    selected_article = next(
        (art for art in articles if art["title"] == selected_title),
        None
    )

    if selected_article:
        st.subheader("🧠 Article Details")
        st.write("**Title:**", selected_article["title"])
        st.write(f"🔗 [Read full article]({selected_article['link']})")
else:
    st.write("No news in selected timeframe")
