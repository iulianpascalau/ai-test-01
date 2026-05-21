import os
from dotenv import load_dotenv

# Load .env from the parent directory
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

REQUIRED_ENV_VARS = [
    "JWT_SECRET_KEY",
    "LITELLM_BASE_URL",
    "LITELLM_API_KEY",
    "MODEL_NAME",
    "ADMIN_USERNAME",
    "ADMIN_PASSWORD"
]

# Check for missing environment variables
missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]

if missing_vars:
    raise ValueError(f"CRITICAL ERROR: The following required environment variables are missing in .env: {', '.join(missing_vars)}")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
AUDIO_SERVER_URL = os.getenv("AUDIO_SERVER_URL", "http://127.0.0.1:8001")
