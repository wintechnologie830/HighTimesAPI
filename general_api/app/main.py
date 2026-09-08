from fastapi import FastAPI

from app.routers import customers, documents, products

app = FastAPI(
    title="High Times - generalAPI",
    description=(
        "Internal-only service. This is the SINGLE point of contact with "
        "Aronium's own database (pos.db), always opened READ-ONLY. "
        "Nothing else in the project is allowed to know pos.db's file path. "
        "This service should be bound to 127.0.0.1 only and never exposed "
        "on the store's Wi-Fi network - only fidelityAPI (running on the "
        "same machine) talks to it, using a shared secret key."
    ),
    version="1.0.0",
)

# Intentionally NO CORS middleware and NO wildcard origins here - this
# service is not meant to be called from a browser or a phone, only from
# fidelityAPI running on the same machine.

app.include_router(customers.router)
app.include_router(products.router)
app.include_router(documents.router)


@app.get("/", tags=["health"])
def health_check():
    return {"status": "ok", "service": "generalapi"}
