from fastapi import FastAPI

from app.routers import customers, documents, products, sales

app = FastAPI(
    title="High Times - generalAPI",
    description=(
        "Internal-only service. This is the SINGLE point of contact with "
        "Aronium's own database (pos.db). Almost everything here is "
        "read-only; the deliberate exceptions are narrow, atomic writes: "
        "/products/{id}/reduce-stock (and its compensating /increase-stock), "
        "used to take a product out of Aronium's real Stock the moment a "
        "sale completes; POST /sales, which records a real Sales Document "
        "for a cash purchase made in the loyalty app; and POST /customers, "
        "used once at sign-up to create a real Aronium customer (no "
        "password or credential is ever stored here). Nothing else in the "
        "project is allowed to know pos.db's file path, and nothing else "
        "can write to it. This service should be bound to 127.0.0.1 only "
        "and never exposed on the store's Wi-Fi network - only fidelityAPI "
        "(running on the same machine) talks to it, using a shared secret "
        "key."
    ),
    version="1.0.0",
)

app.include_router(customers.router)
app.include_router(products.router)
app.include_router(documents.router)
app.include_router(sales.router)


@app.get("/", tags=["health"])
def health_check():
    return {"status": "ok", "service": "generalapi"}
