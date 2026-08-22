"""
Exercise 2: Supervisor-routed delegation (LLM decides, specialists execute)

Exercise 1 was a fixed pipeline -- every request took the same path. Real
hierarchical delegation means a supervisor *decides* which specialist gets
the work. Here, an LLM reads the raw request, picks one of three routes,
and extracts the fields that route needs -- then LangGraph sends the
request down a different edge depending on the answer.

Before running:
    - make sure the procurement app is up --
        cd ../prerequisites/procurement-app
        docker compose up -d
        uvicorn app.main:app --reload
    - set OPENAI_API_KEY in a .env file at the repo root (see .env.example)
"""
from typing import Literal, Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
import httpx

load_dotenv()

PROCUREMENT_API_URL = "http://127.0.0.1:8000"

Route = Literal["find_vendor", "check_compliance", "create_purchase_order"]


class DelegationState(TypedDict):
    raw_request: str
    route: Optional[Route]
    category: Optional[str]
    vendor_id: Optional[int]
    amount_usd: Optional[float]
    requested_by: Optional[str]
    result: Optional[dict]


class SupervisorDecision(BaseModel):
    route: Route = Field(description="Which specialist should handle this request.")
    category: Optional[str] = Field(
        default=None, description="Vendor category, only for find_vendor requests."
    )
    vendor_id: Optional[int] = Field(
        default=None, description="Vendor id, for check_compliance or create_purchase_order requests."
    )
    amount_usd: Optional[float] = Field(
        default=None, description="Spend amount in USD, for check_compliance or create_purchase_order requests."
    )
    requested_by: Optional[str] = Field(
        default=None, description="Name of the requester, only for create_purchase_order requests."
    )


SUPERVISOR_SYSTEM_PROMPT = """You route procurement requests to one of three specialists:

- find_vendor: the request is looking for vendors in a category
  (categories: laptops, office_supplies, software_licenses)
- check_compliance: the request asks whether a specific vendor (by id) is
  cleared to spend a specific amount
- create_purchase_order: the request asks to actually create a PO for a
  vendor id, amount, and (optionally) a requester name

Extract only the fields relevant to the route you pick."""

supervisor_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(
    SupervisorDecision
)


def supervisor(state: DelegationState) -> dict:
    decision = supervisor_llm.invoke([
        {"role": "system", "content": SUPERVISOR_SYSTEM_PROMPT},
        {"role": "user", "content": state["raw_request"]},
    ])
    return {
        "route": decision.route,
        "category": decision.category,
        "vendor_id": decision.vendor_id,
        "amount_usd": decision.amount_usd,
        "requested_by": decision.requested_by,
    }


def route_after_supervisor(state: DelegationState) -> Route:
    return state["route"]


def find_vendor(state: DelegationState) -> dict:
    response = httpx.get(
        f"{PROCUREMENT_API_URL}/vendors",
        params={"category": state["category"], "min_rating": 4.0},
    )
    response.raise_for_status()
    return {"result": response.json()}


def check_compliance(state: DelegationState) -> dict:
    response = httpx.post(
        f"{PROCUREMENT_API_URL}/compliance/check",
        json={"vendor_id": state["vendor_id"], "amount_usd": state["amount_usd"]},
    )
    response.raise_for_status()
    return {"result": response.json()}


def create_purchase_order(state: DelegationState) -> dict:
    response = httpx.post(
        f"{PROCUREMENT_API_URL}/purchase-orders",
        json={
            "vendor_id": state["vendor_id"],
            "amount_usd": state["amount_usd"],
            "requested_by": state["requested_by"],
        },
    )
    response.raise_for_status()
    return {"result": response.json()}


graph = StateGraph(DelegationState)
graph.add_node("supervisor", supervisor)
graph.add_node("find_vendor", find_vendor)
graph.add_node("check_compliance", check_compliance)
graph.add_node("create_purchase_order", create_purchase_order)
graph.add_edge(START, "supervisor")
graph.add_conditional_edges("supervisor", route_after_supervisor, {
    "find_vendor": "find_vendor",
    "check_compliance": "check_compliance",
    "create_purchase_order": "create_purchase_order",
})
graph.add_edge("find_vendor", END)
graph.add_edge("check_compliance", END)
graph.add_edge("create_purchase_order", END)
app_graph = graph.compile()


def _run(raw_request: str) -> None:
    result = app_graph.invoke({
        "raw_request": raw_request,
        "route": None,
        "category": None,
        "vendor_id": None,
        "amount_usd": None,
        "requested_by": None,
        "result": None,
    })
    print(f"\n> {raw_request}")
    print(f"  route:  {result['route']}")
    print(f"  result: {result['result']}")


if __name__ == "__main__":
    _run("Find laptop vendors for us")
    _run("Is vendor 3 cleared to spend $75000?")
    _run("Create a PO for vendor 2, $12000, requested by Alice")
