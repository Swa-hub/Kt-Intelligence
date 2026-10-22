# ORDR-412 — Duplicate order rows under mobile retry

**Status:** Open
**Severity:** Medium
**Reporter:** Dev B
**Opened:** 2026-08-29

## Summary
Mobile client occasionally issues the same `POST /api/orders` twice when
the first response is slow or times out at the carrier. The backend
accepts both calls and inserts two rows, differing only in `id` and
`created_at`.

## Steps to reproduce
1. Create an order from the mobile app on a flaky connection.
2. On the carrier side, drop the first response's TCP connection after
   the server has already committed the INSERT.
3. The mobile client retries the same request.
4. Observe two rows in `orders` for the same user, same `total_cents`,
   within a few seconds of each other.

## Suspected cause
`routes.py::create_order` doesn't accept an `Idempotency-Key` header
and the mobile client doesn't send one. There is no uniqueness
constraint that would catch this at the DB layer either.

## Proposed fix (not applied yet)
- Mobile: generate an idempotency key per order attempt.
- Backend: hash the key with user id into a unique index, and on
  conflict return the previously created order.

## Notes
Priya mentioned this during the 2026-09-14 KT session but no owner
was assigned. See transcript, timestamp ~00:35:00.
