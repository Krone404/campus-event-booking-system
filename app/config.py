import os

class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    _DEFAULT_SQLITE = "sqlite:///local.db"

    @staticmethod
    def _build_db_uri() -> str:
        conn_name = os.environ.get("CLOUD_SQL_CONNECTION_NAME")
        db_name = os.environ.get("DB_NAME")
        db_user = os.environ.get("DB_USER")
        db_pass = os.environ.get("DB_PASS")

        # App Engine (Cloud SQL unix socket)
        if conn_name and db_name and db_user and db_pass:
            return (
                f"postgresql+psycopg2://{db_user}:{db_pass}@/{db_name}"
                f"?host=/cloudsql/{conn_name}"
            )

        # Local dev (optional DATABASE_URL), otherwise sqlite
        return os.environ.get("DATABASE_URL", Config._DEFAULT_SQLITE)

    SQLALCHEMY_DATABASE_URI = _build_db_uri.__func__()
