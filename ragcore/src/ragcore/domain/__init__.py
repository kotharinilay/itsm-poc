"""Pure domain model.

This package imports NOTHING outside the Python standard library. No FastAPI, no Pydantic,
no SQLAlchemy, no provider SDK. ``tests/architecture/test_layering.py`` asserts it, and the
assertion is the reason the rule survives contact with a deadline.
"""
