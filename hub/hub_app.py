import sys
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Toronto City Tools", page_icon="🏙️", layout="wide")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from common.auth import check_password  # noqa: E402
from common.app_loader import load_app_page  # noqa: E402
from landing import render_landing  # noqa: E402

if not check_password("Toronto City Tools"):
    st.stop()

area_page = st.Page(
    load_app_page("area-scorecard"),
    title="Should I Live Here?",
    icon="🏘️",
    url_path="area-scorecard",
)
city_page = st.Page(
    load_app_page("city-scorecard"),
    title="City Scorecard",
    icon="🏙️",
    url_path="city-scorecard",
)
ev_page = st.Page(
    load_app_page("ev-scorecard"),
    title="Should I Own an EV?",
    icon="🔌",
    url_path="ev-scorecard",
)
tool_pages = [city_page, ev_page, area_page]

landing_page = st.Page(
    lambda: render_landing(tool_pages),
    title="Home",
    icon="🏠",
    url_path="home",
    default=True,
)

nav = st.navigation([landing_page] + tool_pages)
nav.run()
