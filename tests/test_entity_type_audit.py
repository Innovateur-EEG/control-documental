"""Tests for the read-only entity type database audit."""
from scripts.audit_entity_types import audit_entity_types


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self._rows


class FakeConnection:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement):
        sql = str(statement)
        self.statements.append(sql)
        if '"personas"' in sql:
            return FakeResult([
                {"raw_value": "fisica", "row_count": 2},
                {"raw_value": "Moral", "row_count": 1},
                {"raw_value": "unknown", "row_count": 1},
            ])
        if '"configuracion_campos"' in sql:
            return FakeResult([{"raw_value": "ambas", "row_count": 3}])
        if '"configuracion_evidencias"' in sql:
            return FakeResult([{"raw_value": "Fisica", "row_count": 4}])
        raise AssertionError(f"Unexpected audit query: {sql}")


class FakeEngine:
    def __init__(self):
        self.connection = FakeConnection()

    def connect(self):
        return self.connection


def test_audit_reports_canonicalization_and_unknown_values_without_writes():
    engine = FakeEngine()

    results = audit_entity_types(engine)

    assert [(row["table"], row["raw_value"], row["canonical_value"], row["status"]) for row in results] == [
        ("personas", "fisica", "Fisica", "NORMALIZE"),
        ("personas", "Moral", "Moral", "CANONICAL"),
        ("personas", "unknown", None, "REVIEW REQUIRED"),
        ("configuracion_campos", "ambas", "Ambas", "NORMALIZE"),
        ("configuracion_evidencias", "Fisica", "Fisica", "CANONICAL"),
    ]
    assert len(engine.connection.statements) == 3
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in engine.connection.statements)
