"""The app's pages. Defined once so any page can link or switch to another."""

import streamlit as st

from . import analysis_page, portfolio_page

ANALYSIS = st.Page(analysis_page.render, title="Stock analysis", url_path="analysis", default=True)
PORTFOLIO = st.Page(portfolio_page.render, title="My portfolio", url_path="portfolio")
