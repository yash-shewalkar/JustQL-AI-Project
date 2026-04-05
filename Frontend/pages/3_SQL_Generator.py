import streamlit as st
import requests
import uuid
from datetime import datetime
from login import show_login

st.set_page_config(page_title="SQL Generator", page_icon="🤖", layout="wide")

# ---------------- API ----------------
API_URL = "http://localhost:5000/api/generate_sql"

FILE_API_BASE = "http://localhost:5000/api/files"
UPLOAD_API = f"{FILE_API_BASE}/upload"
DOWNLOAD_API = f"{FILE_API_BASE}/download"

# ✅ NEW: History APIs (Supabase via Flask)
SAVE_API = "http://localhost:5000/api/schema/save"
HISTORY_API = "http://localhost:5000/api/schema/history"
DELETE_API = "http://localhost:5000/api/schema/delete"

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

# ---------------- HISTORY ----------------
def load_history():
    try:
        res = requests.get(HISTORY_API, params={"user_id": user_id})

        if res.status_code == 200:
            return res.json().get("history") or []
        return []
    except Exception as e:
        st.error(f"Load error: {e}")
        return []

def save_chat(entry):
    try:
        requests.post(SAVE_API, json={**entry, "user_id": user_id})
    except Exception as e:
        st.error(f"Save error: {e}")

def delete_chat(chat_id):
    try:
        requests.post(DELETE_API, json={"id": chat_id})

        st.session_state.sql_history = [
            h for h in st.session_state.sql_history if h["id"] != chat_id
        ]

        if st.session_state.sql_current_chat_id == chat_id:
            st.session_state.sql_current_chat_id = None

        st.rerun()
    except Exception as e:
        st.error(f"Delete error: {e}")

# ---------------- FILE ----------------
def upload_file(file, user_id, chat_id):
    files = {
        "file": (file.name, file.getvalue(), file.type)
    }

    data = {
        "user_id": user_id,
        "session_id": chat_id
    }

    try:
        res = requests.post(UPLOAD_API, files=files, data=data)

        if res.status_code == 200:
            return res.json().get("path")
        else:
            st.error("Upload failed")
            return None
    except Exception as e:
        st.error(f"Upload error: {e}")
        return None

def get_download_url(user_id, chat_id, file_name):
    return f"{DOWNLOAD_API}?user_id={user_id}&session_id={chat_id}&file_name={file_name}"

# ---------------- INIT ----------------
if "sql_history" not in st.session_state:
    st.session_state.sql_history = load_history()

if "sql_current_chat_id" not in st.session_state:
    st.session_state.sql_current_chat_id = None

# ---------------- HELPERS ----------------
def create_new_chat():
    st.session_state.sql_current_chat_id = None
    st.rerun()

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.write(f"👤 {user.get('name')}")

    if st.button("➕ New Chat"):
        create_new_chat()

    st.markdown("### 🕓 History")

    for item in reversed(st.session_state.sql_history):
        col1, col2 = st.columns([4, 1])

        with col1:
            if st.button(item["title"], key=f"select_sql_{item['id']}"):
                st.session_state.sql_current_chat_id = item["id"]
                st.rerun()

        with col2:
            if st.button("🗑️", key=f"delete_sql_{item['id']}"):
                delete_chat(item["id"])

    st.markdown("---")

    if st.button("Logout"):
        st.logout()
        st.session_state.clear()
        st.rerun()

# ---------------- SQL API ----------------
def api_generate_sql(engine, schema_text, file_path, query):
    data = {
        "engine": engine,
        "schema": schema_text,
        "query": query
    }

    if file_path:
        data["file_path"] = file_path

    try:
        res = requests.post(API_URL, data=data, timeout=30)

        if res.status_code == 200:
            return res.json().get("sql", "-- No SQL generated")
        else:
            return f"-- Error: {res.json().get('error', 'Unknown error')}"

    except Exception as e:
        return f"-- Failed to connect: {e}"

# ---------------- HEADER ----------------
st.header("🤖 Natural Language to SQL")

if st.button("➕ Start New Chat"):
    create_new_chat()

# ---------------- LOAD CURRENT ----------------
current_chat = None

if st.session_state.sql_current_chat_id:
    for h in st.session_state.sql_history:
        if h["id"] == st.session_state.sql_current_chat_id:
            current_chat = h
            break

# ---------------- DISPLAY ----------------
if current_chat:
    st.subheader("📂 Current Chat")

    st.write("**Engine:**", current_chat["engine"])

    if current_chat["schema_type"] == "text":
        st.code(current_chat["schema_input"])
    else:
        st.write(f"📄 File: {current_chat['schema_file_name']}")

        download_url = get_download_url(
            user_id,
            current_chat["id"],
            current_chat["schema_file_name"]
        )
        st.markdown(f"[📥 Download Schema File]({download_url})")

    st.markdown("### 💬 Queries")

    for q in current_chat["queries"]:
        st.markdown(f"**🧑 Query:** {q['question']}")
        st.code(q["sql"], language="sql")

# ---------------- INPUT ----------------
if st.session_state.sql_current_chat_id is None:

    engine = st.selectbox("Select SQL Engine", ["Trino", "Spark", "PostgreSQL", "Snowflake"])
    input_type = st.radio("Provide schema via:", ["Text Input", "File Upload"], horizontal=True)

    schema_text = ""
    schema_file = None

    if input_type == "Text Input":
        schema_text = st.text_area("Schema Details", height=200)
    else:
        schema_file = st.file_uploader("Upload Schema", type=["pdf", "docx", "txt"])

    if st.button("Ask Query"):
        if schema_text or schema_file:

            chat_id = str(uuid.uuid4())

            file_path = None
            file_name = None

            if schema_file:
                file_name = schema_file.name
                file_path = upload_file(schema_file, user_id, chat_id)

            entry = {
                "id": chat_id,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "engine": engine,
                "schema_type": "text" if schema_text else "file",
                "schema_input": schema_text if schema_text else None,
                "schema_file_name": file_name,
                "schema_file_path": file_path,
                "queries": [],
                "title": (schema_text[:30] if schema_text else file_name) + "..."
            }

            save_chat(entry)

            st.session_state.sql_history = load_history()
            st.session_state.sql_current_chat_id = chat_id

            st.rerun()
        else:
            st.warning("Provide schema first.")

else:
    st.subheader("Ask another question")

    new_query = st.text_area("Enter your query")

    if st.button("Generate SQL"):
        if new_query:
            with st.spinner("Generating SQL..."):

                schema_text = ""
                file_path = None

                if current_chat["schema_type"] == "text":
                    schema_text = current_chat["schema_input"]
                else:
                    file_path = current_chat["schema_file_path"]

                sql = api_generate_sql(
                    current_chat["engine"],
                    schema_text,
                    file_path,
                    new_query
                )

                current_chat["queries"].append({
                    "question": new_query,
                    "sql": sql
                })

                save_chat(current_chat)

                st.session_state.sql_history = load_history()

                st.rerun()
        else:
            st.warning("Enter a query.")