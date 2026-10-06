"""Landing/picker page shown when the hub loads. Blurbs match the opening
sentences of PROJECTS.md's per-tool intro paragraphs.
"""

from __future__ import annotations

from typing import Sequence

import streamlit as st

TOOLS = [
    {
        "title": "City Scorecard",
        "blurb": (
            "Score any Toronto address on the 15-minute city standard: groceries, "
            "healthcare, parks, schools, transit, and fitness within a short trip."
        ),
    },
    {
        "title": "Should I Own an EV?",
        "blurb": (
            "Can you charge an EV at this Toronto address? Checks home charging, "
            "or public charging access if home isn't an option."
        ),
    },
    {
        "title": "Should I Live Here?",
        "blurb": (
            "See what's changing near any Toronto address, how it compares on "
            "safety, and the maintenance record if it's a rental apartment."
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
