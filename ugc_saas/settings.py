from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def env_flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw_value = os.getenv(name, default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)).strip())


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-dev-key-change-me")
DEBUG = env_flag("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "studio",
    "tcc_portal",
    "desafio",
]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "tcc_portal.middleware.TccPortalCorsMiddleware",
    "desafio.middleware.DesafioCorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "ugc_saas.urls"


TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


WSGI_APPLICATION = "ugc_saas.wsgi.application"
ASGI_APPLICATION = "ugc_saas.asgi.application"


if os.getenv("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB"),
            "USER": os.getenv("POSTGRES_USER", "ugc"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "db"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


LANGUAGE_CODE = "pt-br"
TIME_ZONE = os.getenv("DJANGO_TIMEZONE", "America/Bahia")
USE_I18N = True
USE_TZ = True


STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    os.getenv(
        "DJANGO_EMAIL_BACKEND",
        "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
    ),
)
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    os.getenv("DJANGO_DEFAULT_FROM_EMAIL", "Layfe <layfe@thecreatorsclub.com.br>"),
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = env_int("EMAIL_PORT", 25)
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_flag("EMAIL_USE_TLS", False)
EMAIL_USE_SSL = env_flag("EMAIL_USE_SSL", False)


SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_flag("DJANGO_SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE = env_flag("DJANGO_SESSION_COOKIE_SECURE", False)
CSRF_COOKIE_SECURE = env_flag("DJANGO_CSRF_COOKIE_SECURE", False)

MERCADO_PAGO_PUBLIC_KEY = os.getenv("MERCADO_PAGO_PUBLIC_KEY", "").strip()
MERCADO_PAGO_ACCESS_TOKEN = os.getenv("MERCADO_PAGO_ACCESS_TOKEN", "").strip()
MERCADO_PAGO_WEBHOOK_SECRET = os.getenv("MERCADO_PAGO_WEBHOOK_SECRET", "").strip()
CHECKOUT_BASE_URL = os.getenv("CHECKOUT_BASE_URL", "https://app.thecreatorsclub.com.br").strip()

APIBRASIL_CEP_URL = os.getenv("APIBRASIL_CEP_URL", "").strip()
APIBRASIL_CEP_TOKEN = os.getenv("APIBRASIL_CEP_TOKEN", "").strip()
APIBRASIL_CEP_TIMEOUT = env_int("APIBRASIL_CEP_TIMEOUT", 8)
APIBRASIL_CNPJ_URL = os.getenv("APIBRASIL_CNPJ_URL", "").strip()
APIBRASIL_CNPJ_TOKEN = os.getenv("APIBRASIL_CNPJ_TOKEN", APIBRASIL_CEP_TOKEN).strip()
APIBRASIL_CNPJ_TIMEOUT = env_int("APIBRASIL_CNPJ_TIMEOUT", 8)

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

TCC_PORTAL_ADMIN_PASSWORD = os.getenv("TCC_PORTAL_ADMIN_PASSWORD", "tcc-admin-2026")
TCC_PORTAL_ALLOWED_ORIGINS = set(
    env_list(
        "TCC_PORTAL_ALLOWED_ORIGINS",
        "https://portal.thecreatorsclub.com.br,http://localhost:5500,http://127.0.0.1:5500,null",
    )
)

# Origens do site estatico que consomem a API do Desafio Postaria Mais.
DESAFIO_ALLOWED_ORIGINS = set(
    env_list(
        "DESAFIO_ALLOWED_ORIGINS",
        "https://thecreatorsclub.com.br,https://www.thecreatorsclub.com.br,http://localhost:9010,http://localhost:5500,null",
    )
)
