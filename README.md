# Aronium Loyalty / Points API

This API connects **Aronium POS** to a mobile loyalty app.

**In simple terms:** Aronium keeps handling customers and sales as usual. The API reads that information and manages loyalty points separately, without modifying Aronium.

### How it works

* **Aronium (`pos.db`)** → Customer and purchase information. **Read-only.**
* **Loyalty database (`loyalty.db`)** → Points, point history, and loyalty information.
* **Mobile app** → Communicates with the API to display and manage customer points.

```text
Aronium → Loyalty API → Mobile App
             ↓
         loyalty.db
```

## Setup

Install the required packages:

```bash
pip install -r requirements.txt
```

Then start the FastAPI server:

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

## Configuration

Create a `.env` file based on `.env.example` and configure:

* `ARONIUM_DB_PATH` → Location of Aronium's `pos.db`
* `LOYALTY_DB_PATH` → Location where `loyalty.db` should be stored
* `API_KEY` → Secret key used to protect the API

**Keep `loyalty.db` outside Aronium's `Data` folder.**

## Automatic Points

The API can periodically check Aronium for new sales and automatically award points.

This can be scheduled using **Windows Task Scheduler** or another scheduling system.

## Important

* Aronium's database is **never modified**.
* Loyalty data is stored separately in `loyalty.db`.
* Keep regular backups of `loyalty.db`.
* Keep the API key secret.
