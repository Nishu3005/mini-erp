"""Transaction discipline + safe input coercion shared by services and routes.

Addresses: services committing internally while routes also write; caught domain errors not rolling
back; raw int()/Decimal() in routes turning bad input into 500s.
"""
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation


class InputError(ValueError):
    """Bad user input — routes turn this into a flash message, never a 500."""


@contextmanager
def atomic():
    """Commit on success, roll back on ANY exception. The single write boundary.

    Usage:
        with atomic():
            ... mutate ORM objects ...
    """
    from app.extensions import db
    try:
        yield
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def to_decimal(value, field="value", *, minimum=None, allow_zero=True) -> Decimal:
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError, ValueError):
        raise InputError(f"{field} must be a number.")
    if minimum is not None and d < minimum:
        raise InputError(f"{field} cannot be less than {minimum}.")
    if not allow_zero and d == 0:
        raise InputError(f"{field} must be greater than zero.")
    return d


def to_int(value, field="value"):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise InputError(f"{field} is invalid.")
