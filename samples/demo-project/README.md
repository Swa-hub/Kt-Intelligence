# orders-api (sample project)

Small Flask-shaped sample used to demonstrate KT Intelligence. The files
are illustrative — they aren't a runnable service.

## Endpoints

- `GET  /api/orders` — list the caller's orders.
- `GET  /api/orders/<id>` — fetch one order.
- `POST /api/orders` — create a pending order.
- `POST /api/orders/<id>/cancel` — admin only.

## Known issues

- Duplicate orders can be created when the mobile client retries
  `POST /api/orders` without an idempotency key. Tracked in ORDR-412.

## Deployment

Fly.io, two regions. Secrets in Fly secrets, not in the repo.

> This README intentionally does **not** mention the auth gap on
> `GET /api/orders/<id>` — that's the planted contradiction the gap
> detector is expected to surface by comparing `transcript.txt` with
> `routes.py`.
