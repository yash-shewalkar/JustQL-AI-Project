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
import tempfile

# Import the RAG retriever and config
from rag_search import rag_retriever 
from routes.file_routes import file_bp
from config import supabase

# ---------------------------------------------------
# Setup & Logging Configuration
# ---------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)

# Register Blueprints
app.register_blueprint(file_bp, url_prefix="/api/files")

# CORS Configuration
CORS(app, resources={
    r"/suggest": {"origins": ["http://127.0.0.1:5500", "http://localhost:5173"]},
    r"/api/*": {"origins": "*"}
})

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    logger.critical("GROQ_API_KEY missing in environment variables!")
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
    return ChatGroq(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        temperature=0.0,
        max_tokens=max_tokens,
        timeout=30,
        max_retries=3,
        groq_api_key=GROQ_API_KEY
    )

def extract_text_from_file(file):
    text = ""
    try:
        if isinstance(file, str):
            with open(file, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() or ""
        else:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() or ""
        logger.info("Successfully extracted text from PDF.")
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
    return text

def clean_sql_output(raw_text):
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
    cleaned = re.sub(r"```sql", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"```", "", cleaned).strip()
    return cleaned

def log_rag_retrieval(engine, query, context):
    log_file = "rag_logs.txt"
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"\n{'='*60}\n🕒 {timestamp} | ⚙️ {engine.upper()}\n🗣️ QUERY: {query}\n📚 CONTEXT: {context[:200]}...\n{'='*60}\n"
    print(log_entry)
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        logger.error(f"Failed to write to {log_file}: {e}")

# ---------------------------------------------------
# Routes
# ---------------------------------------------------




@app.route("/health", methods=["GET"])
def health_check():
    """
    Service health check.
    Response: {"status": "string", "timestamp": "ISO8601", "service": "string"}
    """
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "service": "JustQL-AI-API"
    }), 200

@app.route("/suggest", methods=["POST"])
def suggest():
    """
    Provides SQL autocompletion suggestions.
    Request JSON: {"query": "SELECT * FROM", "schema": "CREATE TABLE..."}
    Response JSON: {"suggestion": "users WHERE id = 1"}
    """
    global cached_schema
    data = request.json or {}
    user_query = data.get("query", "").strip()
    schema = data.get("schema", "").strip()

    logger.info(f"Autocomplete request received. Query length: {len(user_query)}")

    if schema and schema != globals().get('cached_schema', ''):
        globals()['cached_schema'] = schema

    if len(user_query.split()) > 3:
        try:
            max_tokens = calculate_max_tokens(user_query)
            prompt = f"""
            You are an SQL autocomplete engine (like GitHub Copilot for SQL).

            Task:
            Predict ONLY the next part of the SQL query based on what the user is currently typing.

            Strict Rules:
            - Output ONLY the continuation (no full query)
            - No explanations, no comments
            - Keep it short (1–2 clauses, ~50 tokens max)
            - Continue from the exact last token (even if incomplete)
            - Follow SQL syntax strictly
            - Use only tables/columns from the schema
            - If nothing meaningful to add, return empty string

            Schema:
            {globals().get('cached_schema')}

            Examples:

            User Query: SELECT name, age FROM users WH
            Output: ERE age > 18

            User Query: SELECT * FROM orders WHERE user_id =
            Output: 101

            User Query: SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.
            Output: user_id

            User Query: SELECT * FROM products ORDER BY pri
            Output: ce DESC

            User Query: INSERT INTO users (name, email) VAL
            Output: UES ('John', 'john@example.com')

            User Query: SELECT COUNT(*) FROM orders GROUP BY
            Output: user_id

            User Query: SELECT * FROM employees WHERE salary >
            Output: 50000 ORDER BY salary DESC

            User Query: SELECT * FROM logs LIMIT
            Output: 10

            Now complete:

            User Query: {user_query}
            Output:
            """
            llm = get_llm(max_tokens)
            response = llm.invoke(prompt)
            suggestion = clean_sql_output(response.content)
            return jsonify({"suggestion": suggestion})
        except Exception as e:
            logger.error(f"Suggestion failed: {e}")
            return jsonify({"suggestion": ""}), 500

    return jsonify({"suggestion": ""})

@app.route("/api/generate_schema", methods=["POST"])
def generate_schema():
    """
    Generates SQL DDL from business requirements or files.
    Request Form: {"requirements": "I need a table for users"}
    Request File (Optional): multipart PDF/Doc
    Response JSON: {"ddl": "CREATE TABLE..."}
    """
    requirements = request.form.get("requirements", "")
    logger.info("Schema generation triggered.")

    if 'file' in request.files and request.files['file'].filename != '':
        extracted_text = extract_text_from_file(request.files['file'])
        requirements += "\n\nExtracted File Context:\n" + extracted_text

    if not requirements.strip():
        logger.warning("Empty requirements sent to /generate_schema")
        return jsonify({"error": "No requirements provided"}), 400

    prompt = PromptTemplate.from_template("""
    You are a specialized Database Architect Bot.
    Your task is to convert Business Requirements into clean, valid, and optimized SQL DDL.

    ### RULES:
    1. Output ONLY valid SQL DDL statements.
    2. DO NOT include any explanations, markdown headers (other than the code block), or "Here is your SQL" text.
    3. DO NOT include <think> tags or internal thought processes.
    4. Use standard SQL constraints (Primary Keys, Foreign Keys, Not Null).

    ### EXAMPLE:
    User Requirements: I need a system to track students and the classes they are enrolled in.
    Output:
    CREATE TABLE students (
        student_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        first_name VARCHAR(50) NOT NULL,
        last_name VARCHAR(50) NOT NULL,
        email VARCHAR(100) UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE classes (
        class_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        class_name VARCHAR(100) NOT NULL,
        credits INT CHECK (credits > 0)
    );

    CREATE TABLE enrollments (
        enrollment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        student_id UUID REFERENCES students(student_id) ON DELETE CASCADE,
        class_id UUID REFERENCES classes(class_id) ON DELETE CASCADE,
        enrollment_date DATE DEFAULT CURRENT_DATE
    );

    ### ACTUAL TASK:
    User Requirements: {requirements}
    Output:
    """)
    llm = get_llm(max_tokens=6000)
    chain = prompt | llm

    try:
        response = chain.invoke({"requirements": requirements})
        ddl_output = clean_sql_output(response.content)
        logger.info("Schema generated successfully.")
        return jsonify({"ddl": ddl_output})
    except Exception as e:
        logger.exception("Schema generation failed")
        return jsonify({"error": str(e)}), 500

@app.route("/api/generate_sql", methods=["POST"])
def generate_sql():
    """
    Generates optimized SQL based on engine (Trino/Spark/SQL) and RAG.
    Request Form: {"engine": "Trino", "schema": "...", "query": "...", "file_path": "optional/path/to/pdf"}
    Response JSON: {"sql": "SELECT ..."}
    """
    engine = request.form.get("engine", "SQL")
    schema_text = request.form.get("schema", "")
    query = request.form.get("query", "")
    file_path = request.form.get("file_path")

    logger.info(f"SQL Generation started for engine: {engine}")

    # File extraction logic
    if 'file' in request.files and request.files['file'].filename != '':
        schema_text += "\n" + extract_text_from_file(request.files['file'])
    elif file_path:
        try:
            file_bytes = supabase.storage.from_("user-pdfs").download(path=file_path)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(file_bytes)
                temp_path = tmp.name
            schema_text += "\n" + extract_text_from_file(temp_path)
        except Exception as e:
            logger.error(f"Supabase fetch failed for {file_path}: {e}")
            return jsonify({"error": "Failed to fetch file from storage"}), 500

    if not schema_text.strip() or not query.strip():
        return jsonify({"error": "Schema and Query required"}), 400

    # RAG Logic
    doc_context = ""
    if engine.lower() in ["trino", "spark"]:
        try:
            doc_context = rag_retriever.search_docs(query=query, engine=engine, top_k=3)
            log_rag_retrieval(engine, query, doc_context)
        except Exception as e:
            logger.error(f"RAG failed: {e}")

    # Generation logic
    try:
        prompt = PromptTemplate.from_template("""
        You are a Senior Data Engineer and Expert {engine} SQL Architect.
        Your task is to translate Natural Language queries into valid, optimized {engine} SQL code based strictly on the provided schema.

        ### CONSTRAINTS:
        1. Output ONLY the raw {engine} SQL code.
        2. DO NOT include any explanations, markdown headers, or introductory text.
        3. DO NOT include <think> tags or chain-of-thought processing in the final output.
        4. If documentation context is provided, prioritize it for syntax accuracy.
        5. Use the exact table and column names provided in the schema.

        ### DOCUMENTATION CONTEXT:
        {doc_context}

        ### EXAMPLE:
        User Schema: CREATE TABLE sales (id INT, product_name VARCHAR, amount DOUBLE, sale_date DATE);
        User Query: What was the total revenue for 'Running Shoes' last month?
        Output:
        SELECT SUM(amount) AS total_revenue
        FROM sales
        WHERE product_name = 'Running Shoes'
        AND sale_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1' MONTH)
        AND sale_date < DATE_TRUNC('month', CURRENT_DATE);

        ### ACTUAL TASK:
        User Schema: {schema}
        User Query: {query}
        Engine: {engine}
        Output:
        """)
        chain = prompt | get_llm(1500)
        response = chain.invoke({"engine": engine, "schema": schema_text, "query": query, "doc_context": doc_context})
        return jsonify({"sql": clean_sql_output(response.content)})
    except Exception as e:
        logger.exception("SQL Generation failed")
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------
# 1️⃣ SCHEMA GENERATOR ROUTES (Table: schema_history)
# ---

@app.route("/api/schema/save", methods=["POST"])
def save_schema():
    """Saves to schema_history table"""
    try:
        data = request.json
        logger.info(f"Saving schema session: {data.get('id')}")
        supabase.table("schema_history").upsert({
            "id": data["id"],
            "user_id": data["user_id"],
            "session_id": data["id"],
            "data": data
        }).execute()
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Schema save failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/schema/history", methods=["GET"])
def get_schema_history():
    """Fetches from schema_history table"""
    user_id = request.args.get("user_id")
    try:
        res = supabase.table("schema_history").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return jsonify({"history": [row["data"] for row in res.data]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/schema/delete", methods=["POST"])
def delete_schema():
    chat_id = request.json.get("id")
    try:
        supabase.table("schema_history").delete().eq("id", chat_id).execute()
        return jsonify({"status": "deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------
# 2️⃣ SQL GENERATOR ROUTES (Table: sql_history)
# ---------------------------------------------------
@app.route("/api/sql/save", methods=["POST"])
def save_sql():
    """Saves to sql_history table"""
    try:
        data = request.json
        logger.info(f"Saving SQL session: {data.get('id')}")
        supabase.table("sql_history").upsert({
            "id": data["id"],
            "user_id": data["user_id"],
            "session_id": data["id"],
            "data": data
        }).execute()
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"SQL save failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/sql/history", methods=["GET"])
def get_sql_history():
    """Fetches from sql_history table"""
    user_id = request.args.get("user_id")
    try:
        res = supabase.table("sql_history").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return jsonify({"history": [row["data"] for row in res.data]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/sql/delete", methods=["POST"])
def delete_sql():
    chat_id = request.json.get("id")
    try:
        supabase.table("sql_history").delete().eq("id", chat_id).execute()
        return jsonify({"status": "deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)