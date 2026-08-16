# Procurement app

The real system of record your agentic layer operates on. This isn't
mocked — it's a running FastAPI service with a database, validated end to
end via automated tests and live HTTP calls (see "Verified" below).

## Prerequisites

- Python 3.11+ (built and tested on 3.12)
- pip
- No external database needed — SQLite file, zero setup
- No API keys needed to run this app on its own (only the agentic layer
  needs an `ANTHROPIC_API_KEY`)

```bash
pip install -r requirements.txt
```

## Architecture

```
app/
  main.py         FastAPI app, wires routers together, lifespan/init_db
  database.py     Engine + session (SQLite by default, Postgres-ready)
  models.py       SQLModel tables: Vendor, Contract, PurchaseOrder
  schemas.py      Request/response shapes that aren't tables
  seed.py         Sample vendors + contracts to develop against
  routers/
    vendors.py         search + CRUD
    contracts.py        create + lookup by vendor
    compliance.py       policy check (sanctions list, spend threshold)
    purchase_orders.py  create (auto-runs compliance) + approve + get
tests/
  test_api.py     8 tests, in-memory DB, no network — <1s
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
python -m app.seed                                    # one-time: sample data
uvicorn app.main:app --reload                          # http://127.0.0.1:8000
# interactive API docs: http://127.0.0.1:8000/docs
```

```bash
pytest tests/ -v      # 8 tests, in-memory DB, no server needed
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

- 8/8 `pytest` tests pass against an isolated in-memory DB
- Live server tested with real HTTP calls: vendor search returned seeded
  results, a $500 request auto-cleared and issued, a $60,000 request was
  correctly flagged `pending_approval` with the CFO sign-off reason, and
  approving it transitioned it to `issued` with `approved_by` recorded

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
- Postgres instead of SQLite for anything beyond local dev
- RFQ / multi-vendor bidding workflow (currently: pick one vendor, done)
- Audit log table (who created/approved what, when) — separate from the
  agent-side structured logging in the orchestrator
- Pagination on `/vendors` once the catalog is bigger than a demo dataset
