"""Small orchestration helpers for evidence upload workflows."""


def upload_then_persist(upload, persist, rollback):
    """Persist evidence metadata only after storage upload succeeds.

    The callbacks keep this helper independent of Supabase and SQLAlchemy so the
    failure path can be tested without external services or a live database.
    """
    try:
        upload()
        persist()
    except Exception:
        rollback()
        raise
