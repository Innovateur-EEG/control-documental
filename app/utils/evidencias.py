"""Small orchestration helpers for storage-backed persistence workflows."""


def upload_then_persist(upload, persist, rollback, compensate=None):
    """Upload an object, persist its metadata, and compensate on persistence failure.

    The optional compensate callback removes the newly uploaded object if
    persistence fails. Cleanup errors are suppressed to preserve the original
    exception. It is only called when upload completed successfully.
    """
    uploaded = False
    try:
        upload()
        uploaded = True
        persist()
    except Exception:
        try:
            rollback()
        except Exception:
            pass
        if uploaded and compensate is not None:
            try:
                compensate()
            except Exception:
                pass
        raise
