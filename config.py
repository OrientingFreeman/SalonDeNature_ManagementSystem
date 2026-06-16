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
