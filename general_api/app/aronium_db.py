import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import settings


def _connect() -> sqlite3.Connection:
    db_path = Path(settings.aronium_db_path)
    if not db_path.exists():
        raise FileNotFoundError(
            f"Aronium database not found at '{db_path}'. "
            "Check ARONIUM_DB_PATH in general_api/.env."
        )
    # uri=True + mode=ro => read-only connection, guarantees we can't write
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def aronium_connection():
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


# ---------- Customers ----------

def list_customers(search: str | None = None) -> list[dict]:
    query = """
        SELECT Id, Code, Name, Email, PhoneNumber, City, IsEnabled
        FROM Customer
        WHERE IsCustomer = 1
    """
    params: tuple = ()
    if search:
        query += " AND (Name LIKE ? OR Email LIKE ? OR Code LIKE ?)"
        like = f"%{search}%"
        params = (like, like, like)
    query += " ORDER BY Name"

    with aronium_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_customer(customer_id: int) -> dict | None:
    with aronium_connection() as conn:
        row = conn.execute(
            """
            SELECT Id, Code, Name, Email, PhoneNumber, City, IsEnabled
            FROM Customer
            WHERE Id = ?
            """,
            (customer_id,),
        ).fetchone()
        return dict(row) if row else None


def get_customer_by_loyalty_card(card_number: str) -> dict | None:
    with aronium_connection() as conn:
        row = conn.execute(
            """
            SELECT c.Id, c.Code, c.Name, c.Email, c.PhoneNumber, c.City, c.IsEnabled
            FROM Customer c
            JOIN LoyaltyCard lc ON lc.CustomerId = c.Id
            WHERE lc.CardNumber = ?
            """,
            (card_number,),
        ).fetchone()
        return dict(row) if row else None


# ---------- Sales / documents ----------

def list_customer_documents(customer_id: int, limit: int = 50) -> list[dict]:
    """Purchase history for a customer, most recent first."""
    with aronium_connection() as conn:
        rows = conn.execute(
            """
            SELECT d.Id, d.Number, d.Date, d.Total,
                   dt.Name AS DocumentTypeName, dt.Code AS DocumentTypeCode
            FROM Document d
            JOIN DocumentType dt ON dt.Id = d.DocumentTypeId
            WHERE d.CustomerId = ?
            ORDER BY d.Date DESC
            LIMIT ?
            """,
            (customer_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def list_recent_documents(since_id: int = 0, limit: int = 100) -> list[dict]:
    """
    Used by fidelityAPI's /sync endpoint to find new sales that haven't been
    turned into loyalty points yet (Id > since_id).
    """
    with aronium_connection() as conn:
        rows = conn.execute(
            """
            SELECT d.Id, d.Number, d.CustomerId, d.Date, d.Total,
                   dt.Name AS DocumentTypeName, dt.Code AS DocumentTypeCode
            FROM Document d
            JOIN DocumentType dt ON dt.Id = d.DocumentTypeId
            WHERE d.Id > ? AND d.CustomerId IS NOT NULL
            ORDER BY d.Id ASC
            LIMIT ?
            """,
            (since_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------- Products (so the app can show what points can be redeemed for) ----------

def list_products(search: str | None = None, limit: int = 200) -> list[dict]:
    query = """
        SELECT Id, Name, Code, Price, IsService
        FROM Product
        WHERE IsEnabled = 1
    """
    params: tuple = ()
    if search:
        query += " AND (Name LIKE ? OR Code LIKE ?)"
        like = f"%{search}%"
        params = (like, like)
    query += " ORDER BY Name LIMIT ?"
    params = params + (limit,)

    with aronium_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_product(product_id: int) -> dict | None:
    with aronium_connection() as conn:
        row = conn.execute(
            "SELECT Id, Name, Code, Price, IsService FROM Product WHERE Id = ?",
            (product_id,),
        ).fetchone()
        return dict(row) if row else None
