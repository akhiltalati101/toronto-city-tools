"""Landing/picker page shown when the hub loads. Blurbs are copied verbatim
from PROJECTS.md's per-tool intro paragraphs.
"""

from __future__ import annotations

from typing import Sequence

import streamlit as st

TOOLS = [
    {
        "title": "City Scorecard",
        "blurb": (
            "Score any address in Toronto on how well it meets the 15-minute city "
            "standard — groceries, healthcare, parks, schools, transit, and fitness "
            "all within a short trip."
        ),
    },
    {
        "title": "Should I Own an EV?",
        "blurb": (
            "Check any Toronto address for whether it's realistic to own an EV "
            "there. First question: can you charge at home? If not, the app scores "
            "public charging access instead."
        ),
    },
    {
        "title": "Should I Live Here?",
        "blurb": (
            "Check any Toronto address for what's changing nearby, how it compares "
            "on safety, and — if it's a rental apartment — its official maintenance "
            "record."
        ),
    },
]


_CARD_CSS = """
<style>
[class*="st-key-card-"] button {
    min-height: 220px;
    padding: 20px;
    border-radius: 12px;
    border: 1px solid transparent;
    background: #f5f5f5;
    justify-content: flex-start;
    align-items: flex-start;
    text-align: left;
    transition: border-color 0.15s, transform 0.15s;
}
[class*="st-key-card-"] button:hover {
    border-color: #1e88e5;
    transform: translateY(-2px);
}
[class*="st-key-card-"] button:focus-visible {
    outline: 2px solid #1e88e5;
    outline-offset: 2px;
}
[class*="st-key-card-"] button div[data-testid="stMarkdownContainer"] {
    text-align: left;
    width: 100%;
}
[class*="st-key-card-"] button p:first-child { font-size: 18px; font-weight: 800; }
[class*="st-key-card-"] button p:not(:first-child) { font-size: 13px; color: #555; }
</style>
"""


def render_landing(pages: Sequence[st.Page]) -> None:
    st.title("Toronto City Tools")
    st.caption("Tools to help citizens of Toronto stay more informed and participate in city-related decisions.")

    pages_by_title = {page.title: page for page in pages}

    st.markdown(_CARD_CSS, unsafe_allow_html=True)
    st.write("")
    cols = st.columns(len(TOOLS))
    for n, (col, tool) in enumerate(zip(cols, TOOLS)):
        with col, st.container(key=f"card-{n}"):
            if st.button(f"**{tool['title']}**\n\n{tool['blurb']}", key=f"card-btn-{n}", use_container_width=True):
                st.switch_page(pages_by_title[tool["title"]])
