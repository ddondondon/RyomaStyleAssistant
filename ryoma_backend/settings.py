# ryoma_backend/settings.py
from pathlib import Path
import environ, os

BASE_DIR = Path(__file__).resolve().parent.parent

# --- .env 読み込み ---
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", default="").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # 追加
    "rest_framework",
    "corsheaders",
    "django.contrib.postgres",
    "api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # ← CORSを先頭寄りに
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ryoma_backend.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "ryoma_backend.wsgi.application"

# --- DB設定（Aurora/PostgreSQL互換） ---
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST"),
        "PORT": env("DB_PORT"),
        "CONN_MAX_AGE": 60,  # 接続再利用
        "OPTIONS": {"sslmode": "prefer"},  # Auroraに切り替え時も無難
    }
}

# 静的ファイル
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# タイムゾーン/言語
LANGUAGE_CODE = "ja"
TIME_ZONE = "Asia/Tokyo"
USE_I18N = True
USE_TZ = True

# CORS
CORS_ALLOWED_ORIGINS = [o.strip() for o in env("CORS_ORIGINS", default="").split(",") if o.strip()]
# 開発中のみワイルドカード許可したい場合は:
# CORS_ALLOW_ALL_ORIGINS = DEBUG

# DRF（必要に応じて最小設定）
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
}
