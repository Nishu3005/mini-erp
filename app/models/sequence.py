"""Persistent sequence counters — one row per document prefix.

Replaces the race-prone count()+1 approach: the next number is read-and-incremented under a row
lock inside the caller's transaction, so concurrent "New" clicks, deletes, and failed transactions
never reuse or collide on a reference. See spec/sequences-and-conventions.md.
"""
from app.extensions import db


class Sequence(db.Model):
    __tablename__ = "sequence"

    prefix = db.Column(db.String(8), primary_key=True)   # SO / PO / MO / BOM / PRD
    next_value = db.Column(db.Integer, nullable=False, default=1)
