"""Boot smoke tests — Phase 0 regression guard (see ROADMAP.md).

These catch the blockers that stopped the assembled app from starting:
- api/routes/combat.py used `Query(...)` without importing `Query` (NameError at import).
- requirements.txt was missing python-jose/passlib/bcrypt (ModuleNotFoundError on auth import).
- core/errors.py AuthError subclasses passed `http_status` twice (TypeError on instantiation).

The existing unit suite imports app.core.* directly and so never exercised the
route/app layer; that is why a green suite did not catch these.
"""
import importlib

import pytest


def test_app_main_imports():
    """The FastAPI application module must import cleanly (i.e. it can boot)."""
    main = importlib.import_module("app.main")
    assert main.app is not None
    # Every router must have mounted (regression: a bad route import aborts the whole app).
    assert any(r.path == "/api/health" for r in main.app.routes)


@pytest.mark.parametrize(
    "error_name, expected_status",
    [
        ("InvalidCredentialsError", 401),
        ("TokenExpiredError", 401),
        ("TokenInvalidError", 401),
        ("ForbiddenError", 403),
    ],
)
def test_auth_errors_instantiate(error_name, expected_status):
    """Auth error classes must instantiate and carry the correct HTTP status."""
    from app.core import errors

    err = getattr(errors, error_name)()
    assert err.http_status == expected_status
