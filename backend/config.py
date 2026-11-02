"""
Central place for every setting the app reads from the environment.

Locally the values come from a .env file in the project root; when hosted
they come from the platform's secrets (Hugging Face Space secrets or
Google Secret Manager).
"""

import os
import tempfile

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# True when hosted: Hugging Face Spaces sets SPACE_ID, Google Cloud Run sets K_SERVICE.
IS_PRODUCTION = bool(os.getenv("SPACE_ID") or os.getenv("K_SERVICE"))

# --- Admin login ---------------------------------------------------------
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "")

# --- Storage -------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "")
SQLITE_PATH = os.path.join(PROJECT_ROOT, "data", "auditor.db")
POLICY_PATH = os.path.join(PROJECT_ROOT, "data", "policy.txt")
# Uploaded audio is kept only until the audit finishes, so the system temp folder is enough.
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "call-auditor-uploads")

# --- Groq (speech-to-text and LLM) ---------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_LLM_MODEL = os.getenv("GROQ_LLM_MODEL", "openai/gpt-oss-120b")
GROQ_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3")

# --- Pinecone (policy retrieval) -----------------------------------------
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "call-auditor-policy")
PINECONE_EMBED_MODEL = os.getenv("PINECONE_EMBED_MODEL", "multilingual-e5-large")
PINECONE_EMBED_DIMENSION = int(os.getenv("PINECONE_EMBED_DIMENSION", "1024"))
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

# --- Uploads -------------------------------------------------------------
# Groq's free tier accepts audio files up to 25 MB.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_AUDIO_EXTENSIONS = {"mp3", "wav", "m4a", "ogg", "webm", "flac", "mp4", "mpeg", "mpga"}
