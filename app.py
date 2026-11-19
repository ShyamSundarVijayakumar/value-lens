"""Value Lens: run with  streamlit run app.py"""

import streamlit as st
from dotenv import load_dotenv

from value_lens import config
from value_lens.ui import components as ui
from value_lens.ui.pages import ANALYSIS, PORTFOLIO

load_dotenv()
st.set_page_config(page_title="Value Lens", page_icon=str(config.PROJECT_ROOT / "static" / "favicon.png"),
                   layout="wide", initial_sidebar_state="auto")
st.html(ui.CSS)

page = st.navigation({"Value Lens": [ANALYSIS, PORTFOLIO]}, position="sidebar")
page.run()
