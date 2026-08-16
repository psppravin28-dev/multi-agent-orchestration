"""
Run once after a fresh init_db() to have realistic data to build the
agentic layer against: python -m app.seed
"""
from sqlmodel import Session

from app.database import engine, init_db
from app.models import Contract, Vendor


def seed():
    init_db()
    with Session(engine) as session:
        vendors = [
            Vendor(name="Dell Business", category="laptops", rating=4.6, contact_email="sales@dellbusiness.example"),
            Vendor(name="Lenovo ThinkPad Direct", category="laptops", rating=4.4),
            Vendor(name="HP Enterprise", category="laptops", rating=4.2),
            Vendor(name="Staples B2B", category="office_supplies", rating=4.0),
            Vendor(name="CDW", category="software_licenses", rating=4.5),
            Vendor(name="Shady Supplies Ltd", category="laptops", rating=3.9, on_sanctions_list=True),
        ]
        session.add_all(vendors)
        session.commit()
        for v in vendors:
            session.refresh(v)

        contracts = [
            Contract(vendor_id=vendors[0].id, payment_terms="Net-30", liability_cap_usd=250_000),
            Contract(vendor_id=vendors[1].id, payment_terms="Net-45", liability_cap_usd=150_000),
            Contract(vendor_id=vendors[3].id, payment_terms="Net-30", liability_cap_usd=50_000),
        ]
        session.add_all(contracts)
        session.commit()

    print("Seeded vendors and contracts.")


if __name__ == "__main__":
    seed()
