import streamlit as st
import MetaTrader5 as mt5
import pandas as pd
import plotly.graph_objects as go
import feedparser
import urllib.parse
import time
from datetime import datetime

# ==============================
# PAGE CONFIG
# ==============================
st.set_page_config(layout="wide")
st.title("⚡ Live AI Stock Dashboard (Phase 1)")

# ==============================
# MT5 INIT
# ==============================
if not mt5.initialize():
    st.error("MT5 failed to initialize")
    st.stop()

# ==============================
# UI TOP BAR
# ==============================
col1, col2, col3 = st.columns([2,2,1])

with col1:
    ticker = st.text_input("Ticker", "TSLA")

with col2:
    timeframe = st.selectbox("Timeframe", ["1m","5m","15m","1h","1d"])

with col3:
    live = st.toggle("Live", True)

# ==============================
# TIMEFRAME MAP
# ==============================
TIMEFRAME_MAP = {
    "1m": mt5.TIMEFRAME_M1,
    "5m": mt5.TIMEFRAME_M5,
    "15m": mt5.TIMEFRAME_M15,
    "1h": mt5.TIMEFRAME_H1,
    "1d": mt5.TIMEFRAME_D1
}

# ==============================
# NEWS FUNCTION
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
# GET MT5 DATA
# ==============================
def get_data(symbol, timeframe):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 500)

    if rates is None:
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

# ==============================
# FILTER NEWS BY TIME
# ==============================
def filter_news(news, start, end):
    filtered = []
    for art in news:
        if start <= art["published"] <= end:
            filtered.append(art)
    return filtered[:30]

# ==============================
# BUILD CHART
# ==============================
def build_chart(df, news):
    fig = go.Figure()

    # PRICE
    fig.add_trace(go.Scatter(
        x=df['time'],
        y=df['close'],
        mode='lines',
        name='Price'
    ))

    # NEWS
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
# MAIN LAYOUT
# ==============================
left, right = st.columns([3,1])

chart_placeholder = left.empty()
news_placeholder = right.empty()

# ==============================
# LIVE LOOP
# ==============================
while True:

    df = get_data(ticker, TIMEFRAME_MAP[timeframe])

    if df is None or df.empty:
        chart_placeholder.warning("No data - check symbol name (e.g. TSLA.US)")
        time.sleep(2)
        continue

    start = df['time'].min()
    end = df['time'].max()

    news = get_news(f"{ticker} stock")
    news = filter_news(news, start, end)

    fig = build_chart(df, news)

    # UPDATE CHART
    with chart_placeholder:
        st.plotly_chart(fig, use_container_width=True)

    # UPDATE NEWS PANEL
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

    if not live:
        break

    time.sleep(2)
