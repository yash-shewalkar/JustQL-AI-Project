# rag_search.py
import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

TRINO_VECTOR_STORE_DIR = "./data/vector_store_trino"
SPARK_VECTOR_STORE_DIR = "./data/vector_store_spark"

class SQLRetriever:
    def __init__(self):
        """Initializes the embeddings and loads both local FAISS indexes."""
        self.embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")
        
        # Load Trino Store
        if os.path.exists(TRINO_VECTOR_STORE_DIR):
            self.trino_store = FAISS.load_local(
                TRINO_VECTOR_STORE_DIR, 
                self.embeddings, 
                allow_dangerous_deserialization=True 
            )
        else:
            self.trino_store = None
            print(f"⚠️ Warning: Trino store not found at {TRINO_VECTOR_STORE_DIR}")

        # Load Spark Store
        if os.path.exists(SPARK_VECTOR_STORE_DIR):
            self.spark_store = FAISS.load_local(
                SPARK_VECTOR_STORE_DIR, 
                self.embeddings, 
                allow_dangerous_deserialization=True 
            )
        else:
            self.spark_store = None
            print(f"⚠️ Warning: Spark store not found at {SPARK_VECTOR_STORE_DIR}")

    def search_docs(self, query: str, engine: str, top_k: int = 3) -> str:
        """
        Routes the query to the specific vector store based on the requested engine.
        Returns a formatted string of the retrieved documentation.
        """
        engine = engine.lower()
        
        # 1. Route to the correct vector store
        if engine == "trino" and self.trino_store:
            retriever = self.trino_store.as_retriever(search_kwargs={"k": top_k})
        elif engine == "spark" and self.spark_store:
            retriever = self.spark_store.as_retriever(search_kwargs={"k": top_k})
        else:
            return f"-- No vector store available or loaded for engine: {engine}."
        
        # 2. Retrieve documents
        docs = retriever.invoke(query)
        
        if not docs:
            return f"-- No specific documentation context found for {engine}."
            
        # 3. Format and return
        context_string = "\n\n---\n\n".join([doc.page_content for doc in docs])
        return context_string

# Singleton instance to be imported by your Flask app (api.py)
rag_retriever = SQLRetriever()