from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import customers, points, products, sync

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

# This is the service that IS meant to be reached from the mobile app on
# the store's isolated Wi-Fi. Tighten allow_origins to your app's actual
# origin before shipping to production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customers.router)
app.include_router(products.router)
app.include_router(points.router)
app.include_router(sync.router)


@app.on_event("startup")
def on_startup():
    # Creates tables in loyalty.db only.
    init_db()


@app.get("/", tags=["health"])
def health_check():
    return {"status": "ok", "service": "fidelityapi"}
