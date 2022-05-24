import os

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("TEST_DB_NAME", "test_database"),
        "USER": os.getenv("TEST_DB_USER", "test_user"),
        "PASSWORD": os.getenv("TEST_DB_PASSWORD", "test_password"),
        "HOST": os.getenv("TEST_DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("TEST_DB_PORT", "5432"),
    }
}

INSTALLED_APPS = [
    "rapidsms",
    "smpp_gateway",
]
