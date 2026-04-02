import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import feedparser
import urllib.parse
import time
from datetime import datetime, timedelta

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from sentence_transformers import SentenceTransformer, util

# ==============================
# CONFIG
# ==============================
API_KEY = "PKNNUMQRVO2V5Q7HUKC46GFKVR"
SECRET_KEY = "CyYqXHDoq2tkrmQDG5Gs1SjdrqJFbAYJ7FUq5gnRTVcM"

client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

@st.cache_resource
def load_model():
    return SentenceTransformer('all-MiniLM-L6-v2')

model = load_model()

# ==============================
# PROFILES (AI)
# ==============================
stock_profile = """
earnings revenue growth production deliveries demand profit outlook upgrade downgrade
"""

macro_profile = """
inflation interest rates federal reserve economy recession oil war geopolitics
"""

profiles = {
    "STOCK": model.encode(stock_profile, convert_to_tensor=True),
    "MACRO": model.encode(macro_profile, convert_to_tensor=True),
}

# ==============================
# PAGE
# ==============================
st.set_page_config(layout="wide")
st.title("⚡ AI Stock News Impact Dashboard (Phase 2)")

# ==============================
# UI
# ==============================
col1, col2, col3, col4 = st.columns([2,2,2,1])

with col1:
    ticker = st.text_input("Ticker", "TSLA")

with col2:
    timeframe = st.selectbox("Timeframe", ["1Min","5Min","15Min","1Hour","1Day"])

with col3:
    lookback = st.selectbox("Lookback", ["1 Day","5 Days","1 Week","2 Weeks","1 Month","6 Month"], index=1)

with col4:
    live = st.toggle("Live", True)

impact_window = st.selectbox("Impact Window", ["30m","1h","4h","1d"], index=1)

# ==============================
# MAPS
# ==============================
TIMEFRAME_MAP = {
    "1Min": TimeFrame(1, TimeFrameUnit.Minute),
    "5Min": TimeFrame(5, TimeFrameUnit.Minute),
    "15Min": TimeFrame(15, TimeFrameUnit.Minute),
    "1Hour": TimeFrame(1, TimeFrameUnit.Hour),
    "1Day": TimeFrame(1, TimeFrameUnit.Day),
}

LOOKBACK_MAP = {
    "1 Day": timedelta(days=1),
    "5 Days": timedelta(days=5),
    "1 Week": timedelta(days=7),
    "2 Weeks": timedelta(days=14),
    "1 Month": timedelta(days=30),
    "6 Month": timedelta(days=180),
}

IMPACT_MAP = {
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
}

interval_choice = st.selectbox(
    "Analysis Interval",
    ["10m", "30m"],
    index=0
)

INTERVAL_MAP = {
    "10m": timedelta(minutes=10),
    "30m": timedelta(minutes=30)
}

# ==============================
# SIGNAL BUILDER
# ==============================
def build_signals(df, news):
    signals = []

    for art in news:
        t = pd.to_datetime(art["published"])

        impact = calculate_impact(df, t, IMPACT_MAP[impact_window])
        stock_sim, macro_sim = score_news(art["title"])

        score = stock_sim - macro_sim

        if impact is None:
            continue

        strength = score * impact

        signals.append({
            "title": art["title"],
            "time": t,
            "impact": impact,
            "score": score,
            "strength": strength,
            "link": art["link"]
        })

    return sorted(signals, key=lambda x: x["strength"], reverse=True)

# ==============================
# PRICE EVOLUTION
# ==============================
def build_price_evolution(df, news_time, interval, steps=6):
    times = []
    prices = []

    base_price = get_price_at_time(df, news_time)

    if base_price is None:
        return None

    for i in range(steps):
        t = news_time + i * interval
        price = get_price_at_time(df, t)

        if price is None:
            continue

        times.append(t)
        prices.append(price)

    return times, prices, base_price


# ==============================
# DATA
# ==============================
def get_data(symbol, timeframe, lookback_delta):

    end = datetime.utcnow()

    # 🔥 LIMIT DATA BASED ON TIMEFRAME
    if timeframe == TimeFrame.Minute:
        start = end - timedelta(days=5)
    elif timeframe == TimeFrame.Hour:
        start = end - timedelta(days=30)
    else:
        start = end - lookback_delta

    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        feed="iex",
        limit=1000  # 🔥 important safety
    )

    try:
        bars = client.get_stock_bars(request).df
    except Exception as e:
        st.error(f"Alpaca error: {e}")
        return None

    if bars.empty:
        return None

    bars = bars.reset_index()
    bars.rename(columns={"timestamp": "time"}, inplace=True)
    bars['time'] = pd.to_datetime(bars['time']).dt.tz_localize(None)

    return bars

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

def filter_news(news, start, end):
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
# IMPACT
# ==============================
def get_price_at_time(df, target_time):
    future = df[df['time'] >= target_time]
    if future.empty:
        return None
    return future.iloc[0]['close']

def calculate_impact(df, news_time, delta):
    base = get_price_at_time(df, news_time)
    if base is None:
        return None

    future = get_price_at_time(df, news_time + delta)
    if future is None:
        return None

    return (future - base) / base * 100

# ==============================
# AI SCORING
# ==============================
def score_news(title):
    emb = model.encode(title, convert_to_tensor=True)

    stock_sim = util.cos_sim(profiles["STOCK"], emb).item()
    macro_sim = util.cos_sim(profiles["MACRO"], emb).item()

    return stock_sim, macro_sim

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

    nx, ny, nt, colors = [], [], [], []

    sentiment_total = 0
    count = 0

    for art in news:
        t = pd.to_datetime(art["published"])

        closest = df.iloc[(df['time'] - t).abs().argsort()[:1]]

        impact = calculate_impact(df, t, IMPACT_MAP[impact_window])
        stock_sim, macro_sim = score_news(art["title"])

        # AI sentiment score
        score = stock_sim - macro_sim
        sentiment_total += score
        count += 1

        if score > 0:
            color = "green"
        else:
            color = "red"

        if impact is not None:
            text = f"{art['title']}<br>Impact: {impact:.2f}%<br>Score: {score:.2f}"
        else:
            text = f"{art['title']}<br>Impact: N/A<br>Score: {score:.2f}"

        nx.append(closest['time'].values[0])
        ny.append(closest['close'].values[0])
        nt.append(text)
        colors.append(color)

    fig.add_trace(go.Scatter(
        x=nx,
        y=ny,
        mode='markers',
        marker=dict(size=10, color=colors),
        text=nt,
        hovertemplate="<b>%{text}</b><extra></extra>"
    ))

    fig.update_layout(height=600)

    avg_sentiment = sentiment_total / count if count > 0 else 0

    return fig, avg_sentiment

# ==============================
# LAYOUT
# ==============================
left, right = st.columns([3,1])

chart_placeholder = left.empty()
side_placeholder = right.empty()

# ==============================
# RUN
# ==============================
df = get_data(ticker, TIMEFRAME_MAP[timeframe], LOOKBACK_MAP[lookback])

if df is None:
    st.warning("No data")
else:
    start = df['time'].min()
    end = df['time'].max()

    news = get_news(f"{ticker} stock")
    news = filter_news(news, start, end)

    fig, sentiment = build_chart(df, news)
    signals = build_signals(df, news)

    with chart_placeholder:
        st.plotly_chart(fig, use_container_width=True)

    selected_signal = None  # 🔥 IMPORTANT FIX (used later)

with side_placeholder:
    st.subheader("📊 Ranked Signals")

    if signals:
        selected_title = st.selectbox(
            "Select News Signal",
            [s["title"] for s in signals]
        )

        selected_signal = next(
            s for s in signals if s["title"] == selected_title
        )

        # ==============================
        # 📌 SELECTED NEWS DISPLAY
        # ==============================
        st.write("### 📌 Selected News")
        st.write(selected_signal["title"])
        st.caption(selected_signal["time"])

        # ==============================
        # 🎨 COLOUR + METRICS
        # ==============================
        if selected_signal["impact"] > 0:
            impact_color = "green"
            sentiment_label = "Bullish"
        else:
            impact_color = "red"
            sentiment_label = "Bearish"

        st.metric("Impact (%)", f"{selected_signal['impact']:.2f}%")
        st.metric("AI Score", f"{selected_signal['score']:.2f}")
        st.metric("Signal Strength", f"{selected_signal['strength']:.2f}")

        st.markdown(f"**Sentiment:** :{impact_color}[{sentiment_label}]")

        st.markdown(f"[Read Article]({selected_signal['link']})")

# ==============================
# SECOND GRAPH
# ==============================
st.subheader("📈 News Impact Breakdown ($)")

if df is not None and signals:

    news_time = selected_signal["time"]

    result = build_price_evolution(
        df,
        news_time,
        INTERVAL_MAP[interval_choice]
    )

    if result:
        times, prices, base_price = result

        # ✅ THIS IS YOUR $ CHANGE
        changes = [(p - base_price) for p in prices]

        # ==============================
        # GRAPH
        # ==============================
        fig2 = go.Figure()

        fig2.add_trace(go.Scatter(
            x=times,
            y=changes,
            mode='lines+markers',
            name='Price Change ($)'
        ))

        fig2.update_layout(
            height=400,
            title="Price Movement After Selected News",
            yaxis_title="Change ($)"
        )

        st.plotly_chart(fig2, use_container_width=True)

        # ==============================
        # TABLE (VERY IMPORTANT)
        # ==============================
        st.subheader("💰 Price Change Breakdown")

        df_changes = pd.DataFrame({
            "Time": times,
            "Price ($)": prices,
            "Change ($)": changes
        })

        st.dataframe(df_changes)
# ==============================
# REFRESH
# ==============================
if "last_update" not in st.session_state:
    st.session_state.last_update = time.time()

if live and (time.time() - st.session_state.last_update > 3):
    st.session_state.last_update = time.time()
    st.rerun()
