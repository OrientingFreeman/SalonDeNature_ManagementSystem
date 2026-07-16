import os
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "beauty_shop.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    KAKAO_REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY")
    KAKAO_REDIRECT_URI = os.environ.get("KAKAO_REDIRECT_URI")
    KAKAO_CLIENT_SECRET = os.environ.get("KAKAO_CLIENT_SECRET")
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.getenv(
        "GOOGLE_REDIRECT_URI",
        "https://salondenature.shop/login/google/callback"
    )
    TOSS_CLIENT_KEY = os.getenv("TOSS_CLIENT_KEY")
    TOSS_SECRET_KEY = os.getenv("TOSS_SECRET_KEY")

    SMS_ENABLED = os.getenv("SMS_ENABLED", "false").lower() == "true"
    SOLAPI_API_KEY = os.getenv("SOLAPI_API_KEY")
    SOLAPI_API_SECRET = os.getenv("SOLAPI_API_SECRET")
    SOLAPI_FROM_NUMBER = os.getenv("SOLAPI_FROM_NUMBER")
    SOLAPI_API_BASE_URL = os.getenv("SOLAPI_API_BASE_URL", "https://api.solapi.com")
    SOLAPI_TIMEOUT_SECONDS = int(os.getenv("SOLAPI_TIMEOUT_SECONDS", "10"))
    API_RATE_LIMIT = int(os.getenv("API_RATE_LIMIT", "120"))
    API_RATE_WINDOW_SECONDS = int(os.getenv("API_RATE_WINDOW_SECONDS", "60"))
    API_CORS_ALLOWED_ORIGINS = [
        origin.strip()
        for origin in os.getenv("API_CORS_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    ]

