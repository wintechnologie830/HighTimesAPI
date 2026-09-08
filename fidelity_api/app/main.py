import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db, SessionLocal
from app.routers import auth, customers, points, products, redemptions, sync

logger = logging.getLogger("fidelity_api.auto_sync")

app = FastAPI(
    title="High Times - fidelityAPI",
    description=(
        "The ONLY service the mobile app ever talks to. Owns loyalty.db "
        "(points/accounts/transactions) and never opens Aronium's pos.db "
        "directly - it asks generalAPI for anything it needs about "
        "customers, sales, or products."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(customers.router)
app.include_router(products.router)
app.include_router(points.router)
app.include_router(redemptions.router)
app.include_router(redemptions.staff_router)
app.include_router(sync.router)


_auto_sync_task: asyncio.Task | None = None


async def _auto_sync_loop():
    """
    Runs sync.perform_sync() on a timer, forever, so that a purchase rung
    up directly at the Aronium till - with a real customer selected via
    the "Search customer" screen, e.g. clicking "ali" instead of leaving
    it on "Walk-in customer" - earns that customer points automatically.
    No one has to press a "sync" button for it to happen.

    App purchases already earn points immediately (see points_service.
    purchase_product), so most of what this loop finds on any given tick
    is till sales; any app purchase it also sees again is just a no-op
    thanks to the shared `sale:{document_id}` reference (see sync.py).

    A single failed tick (e.g. generalAPI briefly unreachable, or Aronium
    not running yet) is logged and retried on the next tick - it never
    crashes the app or stops future ticks.
    """
    while True:
        await asyncio.sleep(settings.auto_sync_interval_seconds)
        db = SessionLocal()
        try:
            result = sync.perform_sync(db)
            if result.processed_documents:
                logger.info(
                    "auto-sync: awarded %.2f points across %d document(s)",
                    result.points_awarded,
                    result.processed_documents,
                )
        except Exception:
            logger.exception("auto-sync run failed, will retry next tick")
        finally:
            db.close()


@app.on_event("startup")
def on_startup():
    init_db()
    global _auto_sync_task
    _auto_sync_task = asyncio.create_task(_auto_sync_loop())


@app.on_event("shutdown")
async def on_shutdown():
    if _auto_sync_task is not None:
        _auto_sync_task.cancel()


@app.get("/", tags=["health"])
def health_check():
    return {"status": "ok", "service": "fidelityapi"}
