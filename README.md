# High Times — Loyalty App

Three pieces, same architecture as before (see each service's own docstrings
for the full reasoning):

```
loyalty-app (browser)
        │  (X-API-Key: FIDELITY_API_KEY)
        ▼
   fidelity_api  ──────────────►  general_api  ────►  pos.db (Aronium)
        │        (X-API-Key: GENERAL_API_KEY)
        ▼
   loyalty.db (points, accounts, transactions, sign-in credentials)
```

- **general_api** is the only thing that ever opens `pos.db`. Read-only for
  everything except three narrow, atomic writes: taking stock out/putting it
  back (`/products/{id}/reduce-stock`, `/increase-stock`), recording a real
  sale (`POST /sales` — Document + DocumentItem + Payment, in the same
  transaction as the stock reduction), and creating a customer at sign-up
  (`POST /customers`). It must stay bound to `127.0.0.1`.
- **fidelity_api** is the only thing the browser talks to. It never sees
  `pos.db`'s path. New in this version: `/auth/register` and `/auth/login`,
  backed by a `CustomerCredential` table that lives only in `loyalty.db` —
  Aronium's own `Customer` table has no password column and never gets one.
  Buying a product now calls `general_api`'s `/sales` endpoint, so a
  purchase shows up on Aronium's own Sales screen and counts toward
  "popular products", not just the loyalty side. Also new: individual
  staff login (`StaffCredential` / `/staff/auth/login`), separate from
  both the customer accounts above and from Aronium entirely — see
  "Staff accounts" below.
- **loyalty-app** is a single static `index.html` — no build step. Sign up
  or sign in, then buy products (earns points, is a real Aronium sale) or
  redeem points for products. Each product card shows Aronium's live stock
  count.

## Running it

### 1. general_api (on the machine running Aronium)
```bash
cd general_api
cp .env.example .env   # set ARONIUM_DB_PATH to your pos.db, pick a GENERAL_API_KEY
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

### 2. fidelity_api (same machine or another on the local network)
```bash
cd fidelity_api
cp .env.example .env   # GENERAL_API_KEY must match general_api's; pick a FIDELITY_API_KEY
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. loyalty-app
Just open `loyalty-app/index.html` in a browser (or serve it from anywhere —
it only needs to be able to reach `fidelity_api` over HTTP; CORS is already
open on the API). Under "connection settings", set the fidelity_api base
URL and its `X-API-Key`, then sign up or sign in.

### 4. Staff accounts
Staff sign up for their own account right on the pickup desk panel (a
"Create account" tab next to "Sign in") - no Aronium record, no link to
customer accounts, just a username/name/password stored in `loyalty.db`.
If you'd rather provision accounts yourself instead, `manage_staff.py`
still works the same way:

```bash
cd fidelity_api
# upgrading an existing loyalty.db? run this once first:
python migrate_staff_login.py

python manage_staff.py add jdoe "Jane Doe"     # prompts for a password
python manage_staff.py list
python manage_staff.py deactivate jdoe         # revoke without deleting
python manage_staff.py reset-password jdoe
```

At the pickup desk, staff still enter the shared "Staff PIN" to open the
panel at all, then sign in (or sign up) individually before "Mark picked
up" will work — that's what lets a redemption record *which* staff
member handed the item over, not just that the PIN was known. Customers
only ever see a staff **id** number on their own "My pickups" screen;
the actual name is only shown on the staff pickup desk.

## What's new since the last version

- Sign up / sign in, backed by `/auth/register` and `/auth/login`.
- Individual staff accounts (`/staff/auth/register`, `/staff/auth/login`),
  on top of the existing shared staff PIN — see "Staff accounts" above.
  Every fulfilled redemption now records which staff member completed it.
- "My pickups" and the staff pickup desk both show the exact time
  (HH:MM:SS) alongside the date, not just the date.
- Live inventory counts shown on every product card.
- Buying a product (not just redeeming with points) now takes real stock
  out of Aronium *and* writes a real Sales document, so it shows up in
  Aronium's reporting the same way a till sale would.

## Known trade-offs, worth revisiting before real production use

- `record_sale()` always uses `UserId=1` and `WarehouseId=1` as a fixed
  "web kiosk" identity — fine for a single-till, single-warehouse setup,
  worth revisiting otherwise.
- If this app runs alongside a real till that *also* rings up the same
  transaction, you'd double-count the sale — decide which system is the
  source of truth for a given purchase.
- Sign-in has no session token/expiry; the browser just remembers the
  customer id after a successful login. Fine for a single-user kiosk-style
  app, not meant to be internet-facing as-is.
- Staff sign-in tokens (`StaffSession`) similarly never expire on their
  own — sign out is manual (the "sign out" link on the pickup desk), or
  `deactivate` the account via `manage_staff.py` if a device is lost.
