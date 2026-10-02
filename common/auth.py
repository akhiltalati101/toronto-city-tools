"""Shared password gate, used by the hub entrypoint and by each app's
standalone (`streamlit run <app>/app.py`) entrypoint alike.
"""

import streamlit as st


def check_password(app_name: str) -> bool:
    """Gate behind a shared password stored in st.secrets.

    Cold-start data download + per-request graph/isochrone compute are
    expensive enough that these tools shouldn't sit at a fully open public
    URL.
    """
    if st.session_state.get("authed"):
        return True

    st.markdown(
        """
        <style>
        div[data-testid="stForm"] {
            border: 1px solid rgba(49, 51, 63, 0.15);
            border-radius: 16px;
            padding: 32px 28px 24px;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    st.write("")
    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        with st.form("login"):
            st.markdown(
                f"<div style='text-align:center; font-size:20px; font-weight:800;'>{app_name}</div>"
                "<div style='text-align:center; font-size:13px; color:#666; margin-bottom:18px;'>"
                "Enter password to continue</div>",
                unsafe_allow_html=True,
            )
            entered = st.text_input("Password", type="password", label_visibility="collapsed", placeholder="Password")
            submitted = st.form_submit_button("Continue", type="primary", use_container_width=True)

        if submitted:
            if entered == st.secrets.get("app_password"):
                st.session_state.authed = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    return False
