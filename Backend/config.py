import os
import logging
from dotenv import load_dotenv
from supabase import create_client

# 1. Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.info("Loading server configuration...")

load_dotenv()

# 2. Extract and Validate Environment Variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_NAME = os.getenv("BUCKET_NAME", "user-pdfs")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("Missing Supabase credentials! Check your .env file.")
    # In a server environment, you often want to crash early if config is missing
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set.")

try:
    # 3. Initialize Client with Debug Logging
    logger.debug(f"Attempting to connect to Supabase at: {SUPABASE_URL}")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Supabase client initialized successfully.")
except Exception as e:
    logger.exception("Failed to initialize Supabase client.")
    raise

logger.info(f"Storage bucket configured: {BUCKET_NAME}")