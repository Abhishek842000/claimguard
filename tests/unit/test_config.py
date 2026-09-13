from claimguard.config import Settings


def test_database_url_rewrites_postgres_scheme_to_psycopg() -> None:
    settings = Settings(database_url="postgres://user:pass@db.example:5432/claimguard")
    assert settings.database_url == "postgresql+psycopg://user:pass@db.example:5432/claimguard"


def test_database_url_rewrites_postgresql_scheme_to_psycopg() -> None:
    settings = Settings(database_url="postgresql://user:pass@db.example:5432/claimguard")
    assert settings.database_url == "postgresql+psycopg://user:pass@db.example:5432/claimguard"


def test_database_url_keeps_explicit_psycopg_driver() -> None:
    url = "postgresql+psycopg://claimguard:claimguard@localhost:5434/claimguard"
    assert Settings(database_url=url).database_url == url
