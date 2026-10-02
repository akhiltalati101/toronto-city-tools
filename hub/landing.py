"""Landing/picker page shown when the hub loads. Blurbs are copied verbatim
from PROJECTS.md's per-tool intro paragraphs.
"""

from __future__ import annotations

from typing import Sequence

import streamlit as st

TOOLS = [
    {
        "icon": "🏙️",
        "title": "City Scorecard",
        "blurb": (
            "Score any address in Toronto on how well it meets the 15-minute city "
            "standard — groceries, healthcare, parks, schools, transit, and fitness "
            "all within a short trip."
        ),
    },
    {
        "icon": "🔌",
        "title": "Should I Own an EV?",
        "blurb": (
            "Check any Toronto address for whether it's realistic to own an EV "
            "there. First question: can you charge at home? If not, the app scores "
            "public charging access instead."
        ),
    },
    {
        "icon": "🏘️",
        "title": "Should I Live Here?",
        "blurb": (
            "Check any Toronto address for what's changing nearby, how it compares "
            "on safety, and — if it's a rental apartment — its official maintenance "
            "record."
        ),
    },
]


def render_landing(pages: Sequence[st.Page]) -> None:
    st.title("Toronto City Tools")
    st.caption("Tools to help citizens of Toronto stay more informed and participate in city-related decisions.")

    pages_by_title = {page.title: page for page in pages}

    st.write("")
    cols = st.columns(len(TOOLS))
    for col, tool, page in zip(cols, TOOLS, (pages_by_title[t["title"]] for t in TOOLS)):
        with col:
            st.markdown(
                f"""
                <div style="padding: 20px; border-radius: 12px; background: #f5f5f5; min-height: 220px;">
                  <div style="font-size: 32px;">{tool['icon']}</div>
                  <div style="font-size: 18px; font-weight: 800; margin-top: 8px;">{tool['title']}</div>
                  <div style="font-size: 13px; color: #555; margin-top: 8px;">{tool['blurb']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.write("")
            st.page_link(page, label=f"Open {tool['title']}", use_container_width=True)
