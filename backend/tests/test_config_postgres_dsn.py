from app.core.config import Settings


def test_postgres_dsn_escapes_reserved_characters() -> None:
    settings = Settings.model_validate(
        {
            "postgres_host": "127.0.0.1",
            "postgres_port": 5432,
            "postgres_db": "ragdb",
            "postgres_user": "postgres",
            "postgres_password": "rABYgaKFO@:/",
        }
    )

    assert settings.postgres_dsn == "postgresql://postgres:rABYgaKFO%40%3A%2F@127.0.0.1:5432/ragdb"
