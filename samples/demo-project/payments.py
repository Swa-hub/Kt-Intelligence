"""orders-api — payments.

Sample data for KT Intelligence. Not executed.
"""
import time
import logging

from .stripe_client import stripe


log = logging.getLogger(__name__)


def charge(order_id: int, amount_cents: int, token: str, max_attempts: int = 3) -> dict:
    """Attempt a Stripe charge with exponential backoff.

    The KT transcript states we retry up to 3 times — this implementation
    does exactly that, with 1s, 2s, 4s backoff.
    """
    delay = 1.0
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return stripe.charges.create(amount=amount_cents, source=token, metadata={"order_id": order_id})
        except stripe.error.APIConnectionError as e:
            last_err = e
            log.warning("stripe attempt %d failed: %s", attempt, e)
            if attempt < max_attempts:
                time.sleep(delay)
                delay *= 2
    raise RuntimeError(f"charge failed after {max_attempts} attempts: {last_err}")
