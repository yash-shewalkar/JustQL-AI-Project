# api.py

from flask import Flask, request, jsonify
from flask_cors import CORS
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv
import os
import re
import PyPDF2
import docx
import logging
import datetime

# Import the RAG retriever we created previously
from rag_search import rag_retriever 
from routes.file_routes import file_bp

logging.basicConfig(level=logging.DEBUG)

# ---------------------------------------------------
# Setup
# ---------------------------------------------------

load_dotenv()

app = Flask(__name__)


################ REGISTER  FILE  ROUTES  ##############

app.register_blueprint(file_bp, url_prefix="/api/files")


########### CORS #################3

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

def get_llm(max_tokens=1500):
    """General LLM fetcher. Increased default tokens for DDL/SQL generation."""
    return ChatGroq(
        model="qwen/qwen3-32b", # Ensure this model name is correct for your Groq tier
        temperature=0.0,
        max_tokens=max_tokens,
        timeout=15,
        max_retries=3,
        groq_api_key=GROQ_API_KEY
    )
import PyPDF2

def extract_text_from_file(file):
    import PyPDF2

    text = ""

    try:
        # ✅ Case 1: file is a string path (Supabase temp file)
        if isinstance(file, str):
            with open(file, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() or ""

        # ✅ Case 2: file is Flask FileStorage
        else:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() or ""

    except Exception as e:
        print("PDF extraction error:", e)

    return text

def clean_sql_output(raw_text):
    """Removes <think> tags and markdown formatting from LLM output."""
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
    cleaned = re.sub(r"```sql", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"```", "", cleaned).strip()
    return cleaned

def log_rag_retrieval(engine, query, context):
    """Prints retrieved RAG context to console and appends to a log file."""
    log_file = "rag_logs.txt"
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Format the log entry
    log_entry = f"\n{'='*60}\n"
    log_entry += f"🕒 TIMESTAMP: {timestamp}\n"
    log_entry += f"⚙️ ENGINE: {engine.upper()}\n"
    log_entry += f"🗣️ USER QUERY: {query}\n"
    log_entry += f"📚 RETRIEVED CONTEXT:\n{context}\n"
    log_entry += f"{'='*60}\n"
    
    # 1. Print to console
    print(log_entry)
    
    # 2. Append to text file
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        logging.error(f"Failed to write to {log_file}: {e}")

# ---------------------------------------------------
# 1️⃣ SQL Suggest API (Existing)
# ---------------------------------------------------
cached_schema = ""
@app.route("/health", methods=["GET"])
def health_check():
    """
    Basic health check route to verify the API is alive.
    Returns 200 OK with a timestamp and status.
    """
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "service": "JustQL-AI-API"
    }), 200
    
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
        suggestion = re.sub(r"<think>.*?</think>", "", suggestion, flags=re.DOTALL).strip()
        return jsonify({"suggestion": suggestion})

    return jsonify({"suggestion": ""})


# ---------------------------------------------------
# 2️⃣ Schema Generator API
# ---------------------------------------------------
@app.route("/api/generate_schema", methods=["POST"])
def generate_schema():
    requirements = request.form.get("requirements", "")
    
    # Handle optional file upload
    if 'file' in request.files and request.files['file'].filename != '':
        extracted_text = extract_text_from_file(request.files['file'])
        requirements += "\n\nExtracted File Context:\n" + extracted_text

    if not requirements.strip():
        return jsonify({"error": "No requirements provided"}), 400

    prompt = PromptTemplate.from_template("""
    You are an Expert Database Architect. Your job is to convert the following business requirements into standard, optimized SQL DDL (Data Definition Language) statements.
    Include standard best practices (e.g., Primary Keys, Foreign Keys, basic constraints if implied). Use accurate compliance with Trino and Spark as specified by the User, if any.  
    
    Business Requirements:
    {requirements}
    
    Do not include any explanations or thought processes.
    Output ONLY valid SQL code with no Explanation or Thinking.
    Use ```  SQL DDL statements ``` format.
    """)
    
    llm = get_llm(max_tokens=2000)
    chain = prompt | llm
    
    try:
        response = chain.invoke({"requirements": requirements})
        ddl_output = clean_sql_output(response.content)
        return jsonify({"ddl": ddl_output})
    except Exception as e:
        logging.error(f"Schema generation failed: {e}")
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------
# 3️⃣ SQL Generator API with RAG Integration
# ---------------------------------------------------
from flask import request, jsonify
from config import supabase
import tempfile
import logging

@app.route("/api/generate_sql", methods=["POST"])
def generate_sql():
    engine = request.form.get("engine", "SQL")
    schema_text = request.form.get("schema", "")
    query = request.form.get("query", "")
    file_path = request.form.get("file_path")  # ✅ NEW

    # ---------------- FILE HANDLING ----------------

    # ✅ Case 1: Old flow (direct file upload)
    if 'file' in request.files and request.files['file'].filename != '':
        extracted_text = extract_text_from_file(request.files['file'])
        schema_text += "\n\nExtracted File Schema Context:\n" + extracted_text

    # ✅ Case 2: NEW flow (Supabase file_path)
    elif file_path:
        try:
            logging.info(f"Fetching file from Supabase: {file_path}")

            file_bytes = supabase.storage.from_("user-pdfs").download(path=file_path)

            # Save temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(file_bytes)
                temp_path = tmp.name

            extracted_text = extract_text_from_file(temp_path)

            schema_text += "\n\nExtracted File Schema Context:\n" + extracted_text

        except Exception as e:
            logging.error(f"Supabase file fetch failed: {e}")
            return jsonify({"error": f"File fetch failed: {str(e)}"}), 500

    # ---------------- VALIDATION ----------------

    if not schema_text.strip() or not query.strip():
        return jsonify({"error": "Both schema and query are required"}), 400

    # ---------------- RAG ----------------

    doc_context = ""

    if engine.lower() in ["trino", "spark"]:
        try:
            doc_context = rag_retriever.search_docs(query=query, engine=engine, top_k=3)
            logging.info(f"Successfully retrieved RAG context for {engine}")
            log_rag_retrieval(engine, query, doc_context)
        except Exception as e:
            logging.error(f"RAG retrieval failed: {e}")
            doc_context = "-- Note: Documentation retrieval failed."
    else:
        doc_context = f"-- Note: No local documentation vector store for {engine}"

    # ---------------- PROMPT ----------------

    prompt = PromptTemplate.from_template("""
    You are an expert Data Engineer specializing in {engine}. 
    Write a highly optimized {engine} SQL query to answer the user's request based strictly on the provided schema.
    
    CRITICAL INSTRUCTION: Use the provided Official Documentation Context to ensure strict syntax compliance for {engine}. 
    
    Official Documentation Context:
    {doc_context}
    
    Schema:
    {schema}
    
    User Request:
    {query}
    
    Output ONLY the valid {engine} SQL code.
    """)

    llm = get_llm(max_tokens=1500)
    chain = prompt | llm

    try:
        response = chain.invoke({
            "engine": engine,
            "schema": schema_text,
            "query": query,
            "doc_context": doc_context
        })

        sql_output = clean_sql_output(response.content)
        return jsonify({"sql": sql_output})

    except Exception as e:
        logging.error(f"SQL generation failed: {e}")
        return jsonify({"error": str(e)}), 500
    
    
@app.route("/api/schema/save", methods=["POST"])
def save_schema():
    try:
        data = request.json
        
        # Use upsert instead of insert
        # Supabase will look at the 'id' (Primary Key) to decide whether to update or create
        supabase.table("schema_history").upsert({
            "id": data["id"],
            "user_id": data["user_id"],
            "session_id": data["id"],
            "data": data
        }).execute()

        return jsonify({"status": "success"})

    except Exception as e:
        logging.error(f"Save error: {e}")
        return jsonify({"error": str(e)}), 500
    
@app.route("/api/schema/history", methods=["GET"])
def get_schema_history():
    try:
        user_id = request.args.get("user_id")

        res = supabase.table("schema_history") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .execute()

        history = [row["data"] for row in res.data]

        return jsonify({"history": history})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/schema/delete", methods=["POST"])
def delete_schema():
    try:
        chat_id = request.json.get("id")

        supabase.table("schema_history") \
            .delete() \
            .eq("id", chat_id) \
            .execute()

        return jsonify({"status": "deleted"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Pull the port from the environment variable 'PORT'
    # Default to 5000 if not found (for local testing)
    port = int(os.environ.get("PORT", 5000))
    
    # Use '0.0.0.0' to ensure it's accessible externally
    app.run(host="0.0.0.0", port=port, debug=False)