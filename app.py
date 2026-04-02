import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import feedparser
import urllib.parse
import time
from datetime import datetime

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# ==============================
# CONFIG
# ==============================
API_KEY = "PKNNUMQRVO2V5Q7HUKC46GFKVR"
SECRET_KEY = "CyYqXHDoq2tkrmQDG5Gs1SjdrqJFbAYJ7FUq5gnRTVcM"

client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

import time

if "last_update" not in st.session_state:
    st.session_state.last_update = time.time()

REFRESH_RATE = 2  # seconds

# ==============================
# PAGE CONFIG
# ==============================
st.set_page_config(layout="wide")
st.title("⚡ Live AI Stock Dashboard (Alpaca)")

# ==============================
# UI
# ==============================
col1, col2, col3 = st.columns([2,2,1])

with col1:
    ticker = st.text_input("Ticker", "TSLA")

with col2:
    timeframe = st.selectbox("Timeframe", ["1Min","5Min","15Min","1Hour","1Day"])

with col3:
    live = st.toggle("Live", True)

# ==============================
# TIMEFRAME MAP
# ==============================
TIMEFRAME_MAP = {
    "1Min": TimeFrame.Minute,
    "5Min": TimeFrame.Minute,
    "15Min": TimeFrame.Minute,
    "1Hour": TimeFrame.Hour,
    "1Day": TimeFrame.Day
}

# ==============================
# NEWS
# ==============================
def get_news(query):
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}"
    feed = feedparser.parse(url)

    articles = []

    for entry in feed.entries:
        try:
            published = datetime.strptime(
                entry.published, "%a, %d %b %Y %H:%M:%S %Z"
            )
            articles.append({
                "title": entry.title,
                "link": entry.link,
                "published": published
            })
        except:
            continue

    return articles

# ==============================
# GET DATA (ALPACA)
# ==============================
def get_data(symbol, timeframe):
    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=timeframe,
        limit=500
    )

    bars = client.get_stock_bars(request).df

    if bars.empty:
        return None

    bars = bars.reset_index()
    bars.rename(columns={"timestamp": "time"}, inplace=True)

    bars['time'] = pd.to_datetime(bars['time']).dt.tz_localize(None)

    return bars

# ==============================
# FILTER NEWS
# ==============================
def filter_news(news, start, end):
    # Convert dataframe times to timezone-naive
    start = pd.to_datetime(start).tz_localize(None)
    end = pd.to_datetime(end).tz_localize(None)

    filtered = []

    for art in news:
        try:
            t = pd.to_datetime(art["published"]).tz_localize(None)

            if start <= t <= end:
                filtered.append(art)

        except:
            continue

    return filtered[:30]

# ==============================
# CHART
# ==============================
def build_chart(df, news):
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['time'],
        y=df['close'],
        mode='lines',
        name='Price'
    ))

    nx, ny, nt = [], [], []

    for art in news:
        t = art["published"]

        closest = df.iloc[(df['time'] - t).abs().argsort()[:1]]

        nx.append(closest['time'].values[0])
        ny.append(closest['close'].values[0])
        nt.append(art["title"])

    fig.add_trace(go.Scatter(
        x=nx,
        y=ny,
        mode='markers',
        marker=dict(size=10, color='red'),
        name='News',
        text=nt,
        hovertemplate="<b>%{text}</b><extra></extra>"
    ))

    fig.update_layout(
        height=600,
        margin=dict(l=10, r=10, t=40, b=10)
    )

    return fig

# ==============================
# LAYOUT
# ==============================
left, right = st.columns([3,1])

chart_placeholder = left.empty()
news_placeholder = right.empty()

# ==============================
# SINGLE RUN (NO LOOP)
# ==============================

df = get_data(ticker, TIMEFRAME_MAP[timeframe])

if df is None or df.empty:
    chart_placeholder.warning("No data - check ticker")
else:
    start = df['time'].min()
    end = df['time'].max()

    news = get_news(f"{ticker} stock")
    news = filter_news(news, start, end)

    fig = build_chart(df, news)

    with chart_placeholder:
        st.plotly_chart(fig, use_container_width=True)

    with news_placeholder:
        st.subheader("📰 News in Timeframe")

        if news:
            for art in news[:10]:
                st.markdown(f"**{art['title']}**")
                st.caption(art["published"])
                st.markdown(f"[Read]({art['link']})")
                st.divider()
        else:
            st.write("No news in this timeframe")

# ==============================
# AUTO REFRESH
# ==============================
if live and (time.time() - st.session_state.last_update > REFRESH_RATE):
    st.session_state.last_update = time.time()
    st.rerun()
