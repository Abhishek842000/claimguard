from sqlalchemy import text
from sqlalchemy.engine import Engine


def test_test_db_fixture_connects(test_db: Engine) -> None:
    with test_db.connect() as conn:
        value = conn.execute(text("SELECT id FROM smoke")).scalar_one()
    assert value == 1
