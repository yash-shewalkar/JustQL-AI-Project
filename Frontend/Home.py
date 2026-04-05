import streamlit as st
from login import show_login

st.set_page_config(
    page_title="Data Engineering Assistant",
    page_icon="⚡",
    layout="wide"
)

# ---------------- AUTH FLOW ----------------
logged_in = st.session_state.get("is_logged_in", False)

if not logged_in:
    is_now_logged_in = show_login()

    # After login → rerun to refresh UI
    if is_now_logged_in:
        st.rerun()

    st.stop()

# ---------------- APP ----------------
user = st.session_state.get("user", {})

st.title("JustQL AI Assistant")
st.header("")

# Sidebar logout (better UX)
with st.sidebar:
    st.write(f"👤 {user.get('name')}")
    if st.button("Logout"):
        st.logout()
        st.session_state.clear()
        st.rerun()

st.markdown("""
Welcome to the internal toolset. Please select a module:

* **SQL Writer**
* **Schema Generator**
* **SQL Generator**
""")

st.info("👈 Select a feature from the sidebar to begin.")