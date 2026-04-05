import streamlit as st
import requests
import uuid
from datetime import datetime
from login import show_login

st.set_page_config(page_title="Schema Generator", page_icon="🏗️", layout="wide")

# ---------------- API ENDPOINTS ----------------
SAVE_API = "http://localhost:5000/api/schema/save"
HISTORY_API = "http://localhost:5000/api/schema/history"
DELETE_API = "http://localhost:5000/api/schema/delete"

GENERATE_API = "http://localhost:5000/api/generate_schema"

FILE_UPLOAD_API = "http://localhost:5000/api/files/upload"
FILE_DOWNLOAD_API = "http://localhost:5000/api/files/download"

# ---------------- AUTH ----------------
logged_in = st.session_state.get("is_logged_in", False)

if not logged_in:
    is_now_logged_in = show_login()
    if is_now_logged_in:
        st.rerun()
    st.stop()

# ---------------- USER ----------------
user = st.session_state.get("user", {})
user_id = user.get("email", "default_user").replace("@", "_").replace(".", "_")

# ---------------- FILE UPLOAD ----------------
def upload_file(file, user_id, chat_id):
    files = {
        "file": (file.name, file.getvalue(), file.type)
    }

    data = {
        "user_id": user_id,
        "session_id": chat_id
    }

    try:
        res = requests.post(FILE_UPLOAD_API, files=files, data=data)

        if res.status_code == 200:
            return res.json().get("path")
        else:
            st.error("File upload failed")
            return None

    except Exception as e:
        st.error(f"Upload error: {e}")
        return None

# ---------------- LOAD / SAVE ----------------
def load_history():
    try:
        res = requests.get(HISTORY_API, params={"user_id": user_id})

        if res.status_code == 200:
            return res.json().get("history") or []
        else:
            st.error("Failed to load history")
            return []

    except Exception as e:
        st.error(f"Load error: {e}")
        return []

def save_chat(entry):
    try:
        response = requests.post(SAVE_API, json={
            **entry,
            "user_id": user_id
        })

        if response.status_code != 200:
            st.error("Failed to save chat")

    except Exception as e:
        st.error(f"Save error: {e}")

# ---------------- INIT ----------------
if "history" not in st.session_state:
    st.session_state.history = load_history()

if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = None

# ---------------- HELPERS ----------------
def create_new_chat():
    st.session_state.current_chat_id = None
    st.rerun()

def delete_chat(chat_id):
    try:
        requests.post(DELETE_API, json={"id": chat_id})

        st.session_state.history = [
            h for h in st.session_state.history if h["id"] != chat_id
        ]

        if st.session_state.current_chat_id == chat_id:
            st.session_state.current_chat_id = None

        st.rerun()

    except Exception as e:
        st.error(f"Delete error: {e}")

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.write(f"👤 {user.get('name')}")

    if st.button("➕ New Chat"):
        create_new_chat()

    st.markdown("### 🕓 History")

    for item in reversed(st.session_state.history):
        col1, col2 = st.columns([4, 1])

        with col1:
            if st.button(item["title"], key=f"select_{item['id']}"):
                st.session_state.current_chat_id = item["id"]
                st.rerun()

        with col2:
            if st.button("🗑️", key=f"delete_{item['id']}"):
                delete_chat(item["id"])

    st.markdown("---")

    if st.button("Logout"):
        st.logout()
        st.session_state.clear()
        st.rerun()

# ---------------- GENERATE API ----------------
def api_generate_ddl(req_text: str, uploaded_file) -> str:
    data = {"requirements": req_text}
    files = {}

    if uploaded_file is not None:
        files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}

    try:
        response = requests.post(GENERATE_API, data=data, files=files, timeout=30)

        if response.status_code == 200:
            return response.json().get("ddl", "-- No DDL generated")
        else:
            return f"-- Error: {response.json().get('error', 'Unknown error')}"

    except Exception as e:
        return f"-- Failed to connect to backend: {e}"

# ---------------- HEADER ----------------
st.header("🏗️ Generate Database Schema")

if st.button("➕ Start New Chat"):
    create_new_chat()

# ---------------- LOAD CURRENT CHAT ----------------
current_chat = None

if st.session_state.current_chat_id:
    for h in st.session_state.history:
        if h["id"] == st.session_state.current_chat_id:
            current_chat = h
            break

# ---------------- DISPLAY ----------------
if current_chat:
    st.subheader("📂 Current Chat")

    if current_chat["type"] == "text":
        st.code(current_chat["input"])
    else:
        st.write(f"📄 File: {current_chat['file_name']}")

        # ✅ Supabase download link
        download_url = f"{FILE_DOWNLOAD_API}?user_id={user_id}&session_id={current_chat['id']}&file_name={current_chat['file_name']}"
        st.markdown(f"[📥 Download File]({download_url})")

    st.write("**Generated DDL:**")
    st.code(current_chat["output"], language="sql")

    st.markdown("---")

# ---------------- INPUT ----------------
if st.session_state.current_chat_id is None:

    schema_input_type = st.radio(
        "Provide requirements via:",
        ["Text Input", "File Upload"],
        horizontal=True
    )

    req_text = ""
    req_file = None

    if schema_input_type == "Text Input":
        req_text = st.text_area(
            "Business Requirements",
            height=150,
            placeholder="e.g., We need employee tracking system..."
        )
    else:
        req_file = st.file_uploader(
            "Upload Requirements Document",
            type=["pdf", "docx", "txt"]
        )

    if st.button("Generate DDL Statements", type="primary"):
        if req_text or req_file:

            with st.spinner("Generating schema..."):
                ddl_output = api_generate_ddl(req_text, req_file)

                st.success("Schema generated successfully!")
                st.code(ddl_output, language="sql")

                # ✅ SINGLE CHAT ID
                chat_id = str(uuid.uuid4())

                file_path = None
                file_name = None

                # ✅ Upload file to Supabase via API
                if req_file:
                    file_name = req_file.name
                    file_path = upload_file(req_file, user_id, chat_id)

                # ✅ Create entry
                entry = {
                    "id": chat_id,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "type": "text" if req_text else "file",
                    "input": req_text if req_text else None,
                    "file_name": file_name,
                    "file_path": file_path,  # Supabase path
                    "output": ddl_output,
                    "title": (req_text[:30] if req_text else file_name) + "..."
                }

                # ✅ Save to backend
                save_chat(entry)

                # ✅ Reload from DB (source of truth)
                st.session_state.history = load_history()
                st.session_state.current_chat_id = chat_id

                st.rerun()

        else:
            st.warning("Please provide business requirements.")