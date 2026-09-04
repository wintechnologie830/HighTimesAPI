from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import customers, points, sync

app = FastAPI(
    title="Aronium Loyalty / Points API",
    description=(
        "Reads customer & sales data from Aronium's own database (pos.db) "
        "READ-ONLY, and manages a separate points/loyalty program in its "
        "own database. Built for a companion fidelity/points mobile app."
    ),
    version="1.0.0",
)

# Allow your mobile app to call this API. Tighten this to your app's
# actual origin(s) before shipping to production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customers.router)
app.include_router(points.router)
app.include_router(sync.router)


@app.on_event("startup")
def on_startup():
    # Creates tables in loyalty.db only. Never touches pos.db.
    init_db()


@app.get("/", tags=["health"])
def health_check():
    return {"status": "ok", "service": "aronium-loyalty-api"}
