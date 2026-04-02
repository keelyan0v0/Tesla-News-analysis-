import streamlit as st
import yfinance as yf
import pandas as pd
import feedparser
import urllib.parse
import plotly.graph_objects as go
from datetime import datetime

# ==============================
# PAGE CONFIG
# ==============================
st.set_page_config(layout="wide")
st.title("📈 Stock News Impact Analyzer")

# ==============================
# INPUT
# ==============================
ticker = st.text_input("Enter Stock Ticker", "TSLA")

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


# ==============================
# LOAD DATA BUTTON
# ==============================
if st.button("Load Data"):

    # ==============================
    # PRICE DATA
    # ==============================
    data = yf.download(ticker, period="5d", interval="15m")

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [col[0] for col in data.columns]

    data = data.reset_index()

    # ==============================
    # LAYOUT
    # ==============================
    col1, col2 = st.columns([2, 1])

    # ==============================
    # CHART (LEFT)
    # ==============================
    with col1:
        st.subheader("📊 Price Chart")

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=data["Datetime"] if "Datetime" in data.columns else data["Date"],
            y=data["Close"],
            mode='lines',
            name='Price'
        ))

        fig.update_layout(
            height=500,
            margin=dict(l=10, r=10, t=30, b=10)
        )

        st.plotly_chart(fig, use_container_width=True)

    # ==============================
    # NEWS (RIGHT)
    # ==============================
    with col2:
        st.subheader("📰 News")

        rss_articles = get_news_rss(f"{ticker} OR stock market OR economy")
        yahoo_articles = get_yahoo_news(ticker)

        articles = rss_articles + yahoo_articles

        if len(articles) == 0:
            st.write("No news found")
        else:
            for i, art in enumerate(articles[:20]):
                if st.button(art["title"], key=i):
                    st.session_state["selected_article"] = art

    # ==============================
    # ARTICLE DETAILS (BOTTOM)
    # ==============================
    if "selected_article" in st.session_state:
        st.divider()
        st.subheader("🧠 Article Details")

        art = st.session_state["selected_article"]

        st.write("**Title:**", art["title"])
        st.write("**Published:**", art["published"])
        st.write("🔗 [Read full article](" + art["link"] + ")")
