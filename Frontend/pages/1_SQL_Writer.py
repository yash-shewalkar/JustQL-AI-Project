import streamlit as st
import streamlit.components.v1 as components
from login import show_login  # reuse login

st.set_page_config(layout="wide")

# ---------------- AUTH FLOW ----------------
logged_in = st.session_state.get("is_logged_in", False)

if not logged_in:
    is_now_logged_in = show_login()

    if is_now_logged_in:
        st.rerun()

    st.stop()

# ---------------- USER ----------------
user = st.session_state.get("user", {})

# ---------------- HEADER ----------------
col1, col2 = st.columns([6, 2])

with col1:
    st.header("SQL Writer (JS Powered)")

with st.sidebar:
    st.write(f"👤 {user.get('name')}")
    if st.button("Logout"):
        st.logout()
        st.session_state.clear()
        st.rerun()

# ---------------- APP ----------------
components.iframe(
    "http://localhost:5500/index.html",
    height=600,
    scrolling=True
)