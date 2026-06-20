"""Reference-number generation: PREFIX-NNNNNN, monotonic per document type.

Uses a persistent `sequence` table with a row-locked read-modify-write so references are never
reused or duplicated under deletes / concurrency / failed transactions. The increment participates
in the caller's transaction (the caller commits). See spec/sequences-and-conventions.md.
"""
from app.extensions import db
from app.models.sequence import Sequence

VALID_PREFIXES = {"SO", "PO", "MO", "BOM", "PRD"}


def next_reference(prefix: str) -> str:
    """Return the next `PREFIX-NNNNNN`, advancing the persistent counter atomically."""
    if prefix not in VALID_PREFIXES:
        raise ValueError(f"Unknown sequence prefix: {prefix}")

    # Row-lock the counter where the backend supports it (no-op/ignored on SQLite, which
    # serializes writes anyway). On Postgres/MySQL this prevents two sessions colliding.
    row = (
        db.session.query(Sequence)
        .filter_by(prefix=prefix)
        .with_for_update()
        .one_or_none()
    )
    if row is None:
        row = Sequence(prefix=prefix, next_value=1)
        db.session.add(row)
        db.session.flush()

    number = row.next_value
    row.next_value = number + 1
    db.session.flush()
    return f"{prefix}-{number:06d}"
