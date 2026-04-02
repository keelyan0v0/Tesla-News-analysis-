# -*- coding: utf-8 -*-
"""
Created on Thu Apr  2 16:31:04 2026

@author: killi
"""

import streamlit as st
import yfinance as yf

st.title("📈 Stock News Impact Analyzer")

ticker = st.text_input("Enter Stock", "TSLA")

if st.button("Load Data"):

    data = yf.download(ticker, period="5d", interval="15m")

    st.subheader("Price Chart")
    st.line_chart(data["Close"])