from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db
from app.routers import compliance, contracts, purchase_orders, vendors


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Procurement App",
    description="System of record for vendors, contracts, compliance checks, and purchase orders.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(vendors.router)
app.include_router(contracts.router)
app.include_router(compliance.router)
app.include_router(purchase_orders.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
