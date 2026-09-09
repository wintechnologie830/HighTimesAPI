import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app.config import settings


def _connect() -> sqlite3.Connection:
    db_path = Path(settings.aronium_db_path)
    if not db_path.exists():
        raise FileNotFoundError(
            f"Aronium database not found at '{db_path}'. "
            "Check ARONIUM_DB_PATH in general_api/.env."
        )
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _connect_write() -> sqlite3.Connection:
    db_path = Path(settings.aronium_db_path)
    if not db_path.exists():
        raise FileNotFoundError(
            f"Aronium database not found at '{db_path}'. "
            "Check ARONIUM_DB_PATH in general_api/.env."
        )
    conn = sqlite3.connect(db_path.as_posix())
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
        SELECT p.Id, p.Name, p.Code, p.Price, p.IsService,
               COALESCE((SELECT SUM(s.Quantity) FROM Stock s WHERE s.ProductId = p.Id), 0) AS Quantity
        FROM Product p
        WHERE p.IsEnabled = 1
    """
    params: tuple = ()
    if search:
        query += " AND (p.Name LIKE ? OR p.Code LIKE ?)"
        like = f"%{search}%"
        params = (like, like)
    query += " ORDER BY p.Name LIMIT ?"
    params = params + (limit,)

    with aronium_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_product(product_id: int) -> dict | None:
    with aronium_connection() as conn:
        row = conn.execute(
            """
            SELECT p.Id, p.Name, p.Code, p.Price, p.IsService,
                   COALESCE((SELECT SUM(s.Quantity) FROM Stock s WHERE s.ProductId = p.Id), 0) AS Quantity
            FROM Product p
            WHERE p.Id = ?
            """,
            (product_id,),
        ).fetchone()
        return dict(row) if row else None


# ---------- Customer creation (another narrow, deliberate write) ----------

def create_customer(name: str, email: str | None, phone: str | None) -> dict:
    conn = _connect_write()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            """
            INSERT INTO Customer (
                Name, Email, PhoneNumber, IsEnabled, IsCustomer, IsSupplier,
                DueDatePeriod, DateCreated, DateUpdated, IsTaxExempt
            ) VALUES (?, ?, ?, 1, 1, 0, 0, DATETIME('now'), DATETIME('now'), 0)
            """,
            (name, email, phone),
        )
        customer_id = cur.lastrowid
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return get_customer(customer_id)


# ---------- Sale recording (the other narrow, deliberate write) ----------

def _next_document_number(conn, type_code: str) -> str:
    year = datetime.now().strftime("%y")
    counter_name = f"Document.{type_code}.20{year}"
    row = conn.execute("SELECT Value FROM Counter WHERE Name = ?", (counter_name,)).fetchone()
    if row is None:
        next_value = 1
        conn.execute("INSERT INTO Counter (Name, Value) VALUES (?, ?)", (counter_name, next_value))
    else:
        next_value = row["Value"] + 1
        conn.execute("UPDATE Counter SET Value = ? WHERE Name = ?", (next_value, counter_name))
    return f"{year}-{type_code}-{next_value:06d}"


SALES_DOCUMENT_TYPE_ID = 2
SALES_DOCUMENT_TYPE_CODE = "200"
DEFAULT_WAREHOUSE_ID = 1
DEFAULT_USER_ID = 1


def record_sale(
    customer_id: int | None,
    product_id: int,
    quantity: int,
    unit_price: float,
    payment_type_id: int = 1,
) -> dict | None:
    if quantity <= 0:
        raise ValueError("quantity must be positive")

    total = round(unit_price * quantity, 2)

    conn = _connect_write()
    try:
        conn.execute("BEGIN IMMEDIATE")

        stock_rows = conn.execute(
            "SELECT Id, Quantity FROM Stock WHERE ProductId = ? ORDER BY Id",
            (product_id,),
        ).fetchall()
        total_available = sum(r["Quantity"] for r in stock_rows)
        if total_available < quantity:
            conn.rollback()
            return None

        remaining = quantity
        for row in stock_rows:
            if remaining <= 0:
                break
            take = min(row["Quantity"], remaining)
            if take <= 0:
                continue
            conn.execute("UPDATE Stock SET Quantity = Quantity - ? WHERE Id = ?", (take, row["Id"]))
            remaining -= take

        number = _next_document_number(conn, SALES_DOCUMENT_TYPE_CODE)

        cur = conn.execute(
            """
            INSERT INTO Document (
                Number, UserId, CustomerId, Date, StockDate, Total,
                IsClockedOut, DocumentTypeId, WarehouseId, DateCreated,
                DateUpdated, PaidStatus, ServiceType
            ) VALUES (
                ?, ?, ?, DATETIME('now'), DATETIME('now'), ?,
                0, ?, ?, DATETIME('now'), DATETIME('now'), 2, 1
            )
            """,
            (number, DEFAULT_USER_ID, customer_id, total, SALES_DOCUMENT_TYPE_ID, DEFAULT_WAREHOUSE_ID),
        )
        document_id = cur.lastrowid

        conn.execute(
            """
            INSERT INTO DocumentItem (
                DocumentId, ProductId, Quantity, PriceBeforeTax, Price,
                ProductCost, PriceBeforeTaxAfterDiscount, PriceAfterDiscount,
                Total, TotalAfterDocumentDiscount
            ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
            """,
            (document_id, product_id, quantity, unit_price, unit_price, unit_price, unit_price, total, total),
        )

        conn.execute(
            """
            INSERT INTO Payment (
                DocumentId, PaymentTypeId, Amount, Date, UserId, DateCreated
            ) VALUES (?, ?, ?, DATETIME('now'), ?, DATETIME('now'))
            """,
            (document_id, payment_type_id, total, DEFAULT_USER_ID),
        )

        conn.commit()
        return {"document_id": document_id, "number": number, "total": total}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def reduce_stock(product_id: int, quantity: int) -> bool:
    if quantity <= 0:
        raise ValueError("quantity must be positive")

    conn = _connect_write()
    try:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            "SELECT Id, Quantity FROM Stock WHERE ProductId = ? ORDER BY Id",
            (product_id,),
        ).fetchall()

        total_available = sum(r["Quantity"] for r in rows)
        if total_available < quantity:
            conn.rollback()
            return False

        remaining = quantity
        for row in rows:
            if remaining <= 0:
                break
            take = min(row["Quantity"], remaining)
            if take <= 0:
                continue
            conn.execute(
                "UPDATE Stock SET Quantity = Quantity - ? WHERE Id = ?",
                (take, row["Id"]),
            )
            remaining -= take

        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def increase_stock(product_id: int, quantity: int) -> None:
    if quantity <= 0:
        raise ValueError("quantity must be positive")

    conn = _connect_write()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT Id FROM Stock WHERE ProductId = ? ORDER BY Id LIMIT 1",
            (product_id,),
        ).fetchone()
        if row is None:
            raise LookupError(f"No Stock row found for product {product_id}")

        conn.execute(
            "UPDATE Stock SET Quantity = Quantity + ? WHERE Id = ?",
            (quantity, row["Id"]),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
