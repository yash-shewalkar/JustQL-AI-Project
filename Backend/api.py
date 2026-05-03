

# app.py

from flask import Flask, request, jsonify
from flask_cors import CORS
from langchain_groq import ChatGroq
from dotenv import load_dotenv
import os
import tempfile
import re
from langchain_core.documents import Document
# Your existing imports
import logging
logging.basicConfig(level=logging.DEBUG)
# ---------------------------------------------------
# Setup
# ---------------------------------------------------

load_dotenv()

app = Flask(__name__)

CORS(app, resources={
    r"/suggest": {"origins": "*"},
    r"/api/*": {"origins": "*"}
})

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY missing in .env")


# ---------------------------------------------------
# Utility Functions
# ---------------------------------------------------

def calculate_max_tokens(user_query):
    base_tokens = 90
    input_length = len(user_query.split())
    max_tokens = base_tokens + (input_length * 3)
    return min(max_tokens, 500)


def get_llm(max_tokens):
    return ChatGroq(
        model="qwen/qwen3-32b",
        temperature=0.0,
        max_tokens=max_tokens,
        timeout=10,
        max_retries=3,
        groq_api_key=GROQ_API_KEY
    )


# ---------------------------------------------------
# 1️⃣ SQL Suggest API
# ---------------------------------------------------
cached_schema = ""

@app.route("/suggest", methods=["POST"])
def suggest():
    global cached_schema
    data = request.json
    user_query = data.get("query", "").strip()
    schema = data.get("schema", "").strip()

    if schema and schema != cached_schema:
        cached_schema = schema

    if len(user_query.split()) > 3:
        max_tokens = calculate_max_tokens(user_query)
        prompt = f"""
        You are a SQL autocompletion assistant. Your task is to suggest a SQL query based on the provided schema and user input.
        You will be given a SQL schema and a user query. Your response should be a valid SQL query that completes the user input.
        assume that user is typing and you are its copilot and you are helping him to complete the query.
        You should not answer anything else. Do not add any extra text or explanation. Just give the SQL query in continution without any thinking thoguhts in output. Don't even add "<think>"
        Given the SQL schema:
        {cached_schema}

        Complete the SQL query:
        {user_query}
        """
        llm = get_llm(max_tokens)
        response = llm.invoke(prompt)
        suggestion = response.content.strip() if response and response.content else ""
        # Remove think blocks if present
        import re
        suggestion = re.sub(r"<think>.*?</think>", "", suggestion, flags=re.DOTALL).strip()
        return jsonify({"suggestion": suggestion})

    return jsonify({"suggestion": ""})





# ---------------------------------------------------
# Run Server
# ---------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

