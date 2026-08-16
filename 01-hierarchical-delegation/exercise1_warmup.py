"""
Exercise 1: LangGraph mechanics warm-up (no LLM yet)
Two nodes: parse a request, then look up real vendors from the procurement app.

Before running: make sure the procurement app is up --
    cd ../prerequisites/procurement-app
    docker compose up -d
    uvicorn app.main:app --reload
"""
from typing import Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
import httpx

PROCUREMENT_API_URL = "http://127.0.0.1:8000"


class IntakeState(TypedDict):
    raw_request: str
    category: Optional[str]
    amount_usd: Optional[float]
    vendor_results: list[dict]


def parse_request(state: IntakeState) -> dict:
    """
    TODO: extract category and amount_usd from state["raw_request"].

    Example input:  "50 laptops, budget $60000"
    Expected output: category="laptops", amount_usd=60000.0

    Keep it simple, no regex library needed:
      - category = whichever known word from
        ["laptops", "office_supplies", "software_licenses"] appears in the text
      - amount_usd = the digits right after the "$" sign, as a float

    Return only the keys you're setting -- e.g. {"category": ..., "amount_usd": ...}
    """
    # YOUR CODE HERE
    ...


def lookup_vendors(state: IntakeState) -> dict:
    """
    TODO: call the real procurement app --
    GET {PROCUREMENT_API_URL}/vendors?category=<category>&min_rating=4.0
    Store the parsed JSON list into vendor_results.
    """
    # YOUR CODE HERE
    ...


# --- graph wiring ---
# TODO:
#   1. graph = StateGraph(IntakeState)
#   2. add both nodes with graph.add_node("name", function)
#   3. wire START -> parse_request -> lookup_vendors -> END with graph.add_edge(...)
#   4. compile it: app_graph = graph.compile()

app_graph = None  # replace this


if __name__ == "__main__":
    result = app_graph.invoke({
        "raw_request": "50 laptops, budget $60000",
        "category": None,
        "amount_usd": None,
        "vendor_results": [],
    })
    print(result)
