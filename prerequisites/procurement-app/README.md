# Procurement app

The real system of record your agentic layer operates on. This isn't
mocked — it's a running FastAPI service with a database, validated end to
end via automated tests and live HTTP calls (see "Verified" below).

## Prerequisites

- Python 3.11+ (built and tested on 3.12)
- pip
- **Docker Desktop** — runs Postgres locally with one command.
  [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)
  - Alternative: a native Postgres 14+ install if you'd rather not use Docker
    (adjust `DATABASE_URL` in `.env` accordingly)
- No API keys needed to run this app on its own (only the agentic layer
  needs an `ANTHROPIC_API_KEY`)

```bash
pip install -r requirements.txt
cp .env.example .env      # defaults match docker-compose.yml, adjust if needed
```

**Note the change from before:** `pytest` now requires `docker compose up -d`
to be running first — the test suite talks to real Postgres, not an
in-memory stand-in. There's no path to running the tests without Postgres up.

## Database: Postgres via Docker Compose

Postgres is the only supported database — there's no SQLite fallback, so
there's never ambiguity about which environment you're running against.

```bash
docker compose up -d          # starts Postgres, persists data in a named volume
docker compose ps             # confirm it's healthy
```

That's it — `DATABASE_URL` in `.env` already points at it
(`postgresql+psycopg://procurement:procurement@localhost:5432/procurement`).

**Stopping / resetting:**
```bash
docker compose down           # stop, keep data
docker compose down -v        # stop, wipe the volume (fresh DB next start)
```


## Architecture

```
app/
  main.py         FastAPI app, wires routers together, lifespan/init_db
  database.py     Engine + session (Postgres only, via .env)
  models.py       SQLModel tables: Vendor, Contract, PurchaseOrder
  schemas.py      Request/response shapes that aren't tables
  seed.py         Sample vendors + contracts to develop against
  routers/
    vendors.py         search + CRUD
    contracts.py        create + lookup by vendor
    compliance.py       policy check (sanctions list, spend threshold)
    purchase_orders.py  create (auto-runs compliance) + approve + get
tests/
  conftest.py     Session/client fixtures — real Postgres, savepoint-per-test isolation
  test_api.py     8 tests, ~0.2s against real Postgres
docker/
  init-test-db.sql   Creates procurement_test on first container start
docker-compose.yml   Local Postgres, one command
.env.example         Copy to .env — DATABASE_URL lives here
```

**Design decision worth understanding**: compliance is re-checked
server-side inside `create_purchase_order`, not trusted from whatever the
caller (agent or human) claims. This is the same principle as re-validating
a form on the server after client-side validation — an agent's prior
"CLEARED" read is not authorization to write.

## Data model

| Entity | Key fields | Notes |
|---|---|---|
| `Vendor` | name, category, rating, `on_sanctions_list` | `on_sanctions_list=True` always fails compliance |
| `Contract` | vendor_id, payment_terms, liability_cap_usd | one active contract per vendor in this MVP |
| `PurchaseOrder` | vendor_id, amount_usd, status | `draft → pending_approval → issued`, or `rejected` |

`COMPLIANCE_FLAG_THRESHOLD_USD = 50_000` in `schemas.py` — spend at or
above this, or any sanctioned vendor, flags the PO as `pending_approval`
instead of auto-issuing it.

## Running it

```bash
docker compose up -d                                    # start Postgres — required, no fallback
python -m app.seed                                       # one-time: sample data
uvicorn app.main:app --reload                             # http://127.0.0.1:8000
# interactive API docs: http://127.0.0.1:8000/docs
```

```bash
pytest tests/ -v      # 8 tests, real Postgres, savepoint-per-test isolation, ~0.2s
```

**Tests run against real Postgres, not a stand-in.** `docker-compose.yml`
creates a second database, `procurement_test`, alongside your dev database
on first start — same container, same credentials, isolated data. Each
test gets its own transaction that's rolled back afterward, so even though
the app code under test calls `session.commit()` exactly like it would in
production, nothing persists once the test ends. See `tests/conftest.py`
for the mechanism (`join_transaction_mode="create_savepoint"`) — verified
by running the suite three times in a row against the same database with
zero leakage before this was written into the fixture.

**If you already ran `docker compose up` before `procurement_test` was
added**, the init script won't retroactively run (Postgres only runs
`docker-entrypoint-initdb.d` scripts on a fresh, empty volume). Either:
```bash
docker compose down -v && docker compose up -d   # wipes dev data too, or:
docker exec procurement-postgres psql -U procurement -d procurement -c "CREATE DATABASE procurement_test;"
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/vendors?category=&min_rating=` | search vendors |
| POST | `/vendors` | create vendor |
| GET | `/vendors/{id}` | get vendor |
| POST | `/contracts` | create contract |
| GET | `/vendors/{id}/contract` | get vendor's active contract |
| POST | `/compliance/check` | check vendor + amount against policy |
| POST | `/purchase-orders` | create PO (auto-runs compliance) |
| POST | `/purchase-orders/{id}/approve` | approve a pending PO |
| GET | `/purchase-orders/{id}` | get PO |

Full interactive schema at `/docs` once the server is running.

## Verified (not just written)

- 8/8 `pytest` tests pass against real Postgres (`procurement_test`
  database), ~0.2s — ran the suite three times consecutively against the
  same database to confirm the savepoint-rollback isolation actually holds
  (a leak would show up immediately as a unique-constraint violation on
  `po_number` on the second run; it didn't)
- Seeded real Postgres via `docker compose up -d` + `python -m app.seed`,
  then confirmed the rows independently with `psql` — not just trusting
  the app's own read-back
- Live server run against that same Postgres instance: created a $75,000
  PO through real HTTP, correctly flagged `pending_approval`, and
  confirmed the row landed in Postgres via a direct `psql` query

## How this connects to the agentic layer (your hands-on track)

Your Module 1 `tools.py` currently calls mocked Python functions
(`search_vendors`, `check_compliance_policy`, etc.) that return hardcoded
data. The natural next exercise: rewrite those four tool functions to make
real `httpx` calls against this running app instead —

```python
# what you'll write, roughly:
@tool
def search_vendors(category: str, min_rating: float = 4.0) -> list[dict]:
    resp = httpx.get(f"{PROCUREMENT_API_URL}/vendors", params={"category": category, "min_rating": min_rating})
    resp.raise_for_status()
    return resp.json()
```

Same tool signature, same agent code, same graph — only the body changes
from "return a hardcoded list" to "call the real API." That's the whole
point of the tool abstraction, and it's a good moment to *feel* why keeping
tools thin and swappable matters.

## Roadmap (intentionally out of scope for now)

- Auth (API keys / OAuth) on the endpoints — fine for local dev, not for
  anything reachable off your machine
- Alembic migrations — right now `init_db()` just calls
  `SQLModel.metadata.create_all()`, which is fine while the schema is still
  moving but won't handle changing an existing column in a real deployment
- RFQ / multi-vendor bidding workflow (currently: pick one vendor, done)
- Audit log table (who created/approved what, when) — separate from the
  agent-side structured logging in the orchestrator
- Pagination on `/vendors` once the catalog is bigger than a demo dataset
