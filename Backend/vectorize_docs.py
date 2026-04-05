# vectorize_docs.py
import os
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

# Configuration - Fixed the Trino path and set separate output directories
TRINO_DOC_PATH = "./data/preprocessed_trino.txt" 
SPARK_DOC_PATH = "./data/preprocessed_spark.txt"
TRINO_VECTOR_STORE_DIR = "./data/vector_store_trino"
SPARK_VECTOR_STORE_DIR = "./data/vector_store_spark"

def build_single_vector_store(filepath: str, engine_name: str, output_dir: str):
    """Processes a single document and saves it to its own vector store."""
    print(f"\n--- Building Vector Store for {engine_name.upper()} ---")
    
    if not os.path.exists(filepath):
        print(f"⚠️ Warning: {filepath} not found. Skipping {engine_name}.")
        return

    print(f"1. Loading document from {filepath}...")
    loader = TextLoader(filepath, encoding='utf-8')
    documents = loader.load()

    print("2. Splitting text into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, 
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Created {len(chunks)} chunks for {engine_name}.")

    print("3. Initializing HuggingFace Embeddings (BAAI/bge-small-en-v1.5)...")
    embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")

    print(f"4. Building FAISS vector store for {engine_name}...")
    vectorstore = FAISS.from_documents(chunks, embeddings)

    print(f"5. Saving vector store locally to '{output_dir}'...")
    vectorstore.save_local(output_dir)
    print(f"✅ {engine_name.capitalize()} vector store is ready!")

def build_all_vector_stores():
    # Build Trino Database
    build_single_vector_store(TRINO_DOC_PATH, "trino", TRINO_VECTOR_STORE_DIR)
    # Build Spark Database
    build_single_vector_store(SPARK_DOC_PATH, "spark", SPARK_VECTOR_STORE_DIR)

if __name__ == "__main__":
    # Ensure the data directory exists
    os.makedirs("./data", exist_ok=True)
    
    # Create dummy files for testing if they don't exist
    for file in [TRINO_DOC_PATH, SPARK_DOC_PATH]:
        if not os.path.exists(file):
            with open(file, 'w') as f:
                f.write(f"This is dummy documentation for {os.path.basename(file)}")
                
    build_all_vector_stores()