"""
Exercise 1: LangGraph mechanics warm-up (no LLM yet)
Two nodes: parse a request, then look up real vendors from the procurement app.
"""
from typing import Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
import httpx

PROCUREMENT_API_URL = "http://127.0.0.1:8000"

KNOWN_CATEGORIES = ["laptops", "office_supplies", "software_licenses"]


class IntakeState(TypedDict):
    raw_request: str
    category: Optional[str]
    amount_usd: Optional[float]
    vendor_results: list[dict]


def parse_request(state: IntakeState) -> dict:
    text = state["raw_request"]

    category = next((c for c in KNOWN_CATEGORIES if c in text), None)

    amount_usd = None
    if "$" in text:
        after_dollar = text.split("$", 1)[1]
        digits = ""
        for char in after_dollar:
            if char.isdigit():
                digits += char
            else:
                break
        if digits:
            amount_usd = float(digits)

    return {"category": category, "amount_usd": amount_usd}


def lookup_vendors(state: IntakeState) -> dict:
    response = httpx.get(
        f"{PROCUREMENT_API_URL}/vendors",
        params={"category": state["category"], "min_rating": 4.0},
    )
    response.raise_for_status()
    return {"vendor_results": response.json()}


graph = StateGraph(IntakeState)
graph.add_node("parse_request", parse_request)
graph.add_node("lookup_vendors", lookup_vendors)
graph.add_edge(START, "parse_request")
graph.add_edge("parse_request", "lookup_vendors")
graph.add_edge("lookup_vendors", END)
app_graph = graph.compile()


if __name__ == "__main__":
    result = app_graph.invoke({
        "raw_request": "50 laptops, budget $60000",
        "category": None,
        "amount_usd": None,
        "vendor_results": [],
    })
    print(result)