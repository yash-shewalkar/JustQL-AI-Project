# login.py

import streamlit as st

def show_login():
    st.title("SQL Assistant Login")

    # ---------------- LOGIN ----------------
    if not st.user.is_logged_in:
        st.subheader("Login required")

        if st.button("Login with Google"):
            st.login("google")

        return False  # not logged in

    # ---------------- STORE SESSION ----------------
    st.session_state["is_logged_in"] = True
    st.session_state["user"] = {
        "email": st.user.email,
        "name": st.user.name,
        "provider_id": st.user.email
    }

    st.success(f"Welcome {st.user.name}")

    # ---------------- FUTURE BACKEND ----------------
    # Uncomment when backend ready
    # import requests
    # API_URL = "http://localhost:5000"
    # ...

    # ---------------- LOGOUT ----------------
    if st.button("Logout"):
        st.logout()
        st.session_state.clear()
        st.rerun()

    return True  # logged in