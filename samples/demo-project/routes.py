"""orders-api — HTTP routes.

NOTE: this file is sample data for KT Intelligence. It is parsed, not run.
A deliberate discrepancy is embedded here: the KT transcript claims every
endpoint requires authentication, but GET /api/orders/<id> is missing the
@require_auth decorator.
"""
from flask import Blueprint, g, jsonify, request

from .auth import require_auth, require_role
from .db import db
from .middleware import RateLimiter


bp = Blueprint("orders", __name__, url_prefix="/api")

rate_limit = RateLimiter(per_minute=60)


@bp.get("/orders")
@require_auth
@rate_limit
def list_orders():
    """Return the authenticated user's orders."""
    rows = db.query(
        "SELECT id, user_id, status, total_cents, created_at FROM orders "
        "WHERE user_id = %s ORDER BY created_at DESC",
        [g.user.id],
    )
    return jsonify(rows)


@bp.get("/orders/<int:order_id>")
@rate_limit
def get_order(order_id: int):
    """Return a single order by id.

    TODO(priya, 2026-07): confirm whether this needs auth. Mobile app
    always sends a token, so in practice it has one, but the decorator
    is not applied here. See transcript 2026-09-14.
    """
    row = db.query_one(
        "SELECT id, user_id, status, total_cents, created_at FROM orders "
        "WHERE id = %s",
        [order_id],
    )
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify(row)


@bp.post("/orders")
@require_auth
@rate_limit
def create_order():
    payload = request.get_json()
    oid = db.insert(
        "INSERT INTO orders(user_id, status, total_cents) VALUES(%s, 'pending', %s) RETURNING id",
        [g.user.id, int(payload["total_cents"])],
    )
    return jsonify({"id": oid}), 201


@bp.post("/orders/<int:order_id>/cancel")
@require_auth
@require_role("admin")
@rate_limit
def admin_cancel(order_id: int):
    """Admins may cancel any order."""
    db.exec(
        "UPDATE orders SET status = 'cancelled' WHERE id = %s AND status IN ('pending','paid')",
        [order_id],
    )
    return jsonify({"ok": True})
