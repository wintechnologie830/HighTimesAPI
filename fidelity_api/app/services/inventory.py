"""
Redeemable stock is no longer tracked as a separate counter in loyalty.db.

Previously this module kept its own `ProductInventory` row per product,
decremented in parallel with the real Aronium stock on every purchase and
redemption. That counter could silently drift away from the truth any time
stock changed through a path this app didn't see (a direct till sale, a
manual stock count, a refund, an admin adjusting quantity in Aronium, ...),
since nothing re-synced it except manually re-running fix_existing_inventory.py.

Redeemable stock and "buy with cash" stock are the exact same shelf, so they
must show the exact same number. The fix is to stop tracking a second number
altogether: the redeemable quantity is just the live Aronium `Quantity` for
that product, the same field the "Buy" tab already reads.
"""


def get_inventory(product: dict) -> int:
    """Live redeemable stock = live Aronium stock. No separate counter."""
    return int(product.get("Quantity") or 0)
