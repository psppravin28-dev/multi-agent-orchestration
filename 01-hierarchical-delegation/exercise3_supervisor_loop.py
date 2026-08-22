"""
Exercise 3: Supervisor loop (multi-step delegation)

Exercise 2's supervisor made one decision and the graph ended -- a single
dispatch. Real hierarchical delegation is a loop: a specialist finishes,
control returns to the supervisor, and the supervisor looks at what just
happened before deciding whether to delegate again or respond. That's
what lets one request like "check compliance for vendor 2 at $12000, and
if cleared create the PO for Alice" turn into two delegations chained
together, with the second decision depending on the first result.

Before running:
    - make sure the procurement app is up --
        cd ../prerequisites/procurement-app
        docker compose up -d
        uvicorn app.main:app --reload
    - set OPENAI_API_KEY in a .env file at the repo root (see .env.example)
"""
import operator
from typing import Annotated, Literal, Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
import httpx

load_dotenv()

PROCUREMENT_API_URL = "http://127.0.0.1:8000"

# Hard cap on delegations per request -- a safety net so a confused
# supervisor can't loop forever. Same principle as the procurement app
# re-checking compliance server-side: don't trust a single component
# (here, the LLM) to police its own termination.
MAX_DELEGATIONS = 4

Route = Literal["find_vendor", "check_compliance", "create_purchase_order", "finish"]


class DelegationState(TypedDict):
    raw_request: str
    route: Optional[Route]
    category: Optional[str]
    vendor_id: Optional[int]
    amount_usd: Optional[float]
    requested_by: Optional[str]
    # Annotated with operator.add so each node's {"history": [...]} return
    # is appended, not overwritten -- state accumulates across loop turns.
    history: Annotated[list[dict], operator.add]
    final_answer: Optional[str]


class SupervisorDecision(BaseModel):
    route: Route = Field(
        description="Which specialist to delegate to next, or 'finish' if the request is fully handled."
    )
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
    final_answer: Optional[str] = Field(
        default=None, description="Summary for the user, only when route is 'finish'."
    )


SUPERVISOR_SYSTEM_PROMPT = """You are a supervisor delegating procurement work to specialists, one \
step at a time. On each turn you see the original request and the results of every delegation so \
far, then choose ONE next action:

- find_vendor: look up vendors in a category (categories: laptops, office_supplies, software_licenses)
- check_compliance: check whether a vendor id is cleared to spend an amount -- only if the original
  request asks about compliance/clearance for a spend
- create_purchase_order: create a PO for a vendor id, amount, and requester name -- only after
  check_compliance has shown that vendor/amount is cleared, AND only if the original request
  actually asked for a PO to be created
- finish: choose this the moment every part of the ORIGINAL request has been answered by the
  delegations so far. Do not perform delegations the request did not ask for -- e.g. if the request
  only asked to find vendors, finish right after find_vendor returns, even though checking
  compliance on one of those vendors might seem like a natural next step. Set final_answer to a
  short summary of what happened.

Never repeat a delegation whose result you already have. Extract only the fields relevant to the
route you pick."""

supervisor_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(
    SupervisorDecision
)


def _history_as_messages(history: list[dict]) -> list[dict]:
    return [
        {"role": "assistant", "content": f"Delegated to {step['route']}, result: {step['result']}"}
        for step in history
    ]


def supervisor(state: DelegationState) -> dict:
    if len(state["history"]) >= MAX_DELEGATIONS:
        return {
            "route": "finish",
            "final_answer": "Stopped after reaching the delegation limit without a clean finish.",
        }

    messages = [
        {"role": "system", "content": SUPERVISOR_SYSTEM_PROMPT},
        {"role": "user", "content": state["raw_request"]},
        *_history_as_messages(state["history"]),
    ]
    decision = supervisor_llm.invoke(messages)
    return {
        "route": decision.route,
        "category": decision.category,
        "vendor_id": decision.vendor_id,
        "amount_usd": decision.amount_usd,
        "requested_by": decision.requested_by,
        "final_answer": decision.final_answer,
    }


def route_after_supervisor(state: DelegationState) -> Route:
    return state["route"]


def find_vendor(state: DelegationState) -> dict:
    response = httpx.get(
        f"{PROCUREMENT_API_URL}/vendors",
        params={"category": state["category"], "min_rating": 4.0},
    )
    response.raise_for_status()
    return {"history": [{"route": "find_vendor", "result": response.json()}]}


def check_compliance(state: DelegationState) -> dict:
    response = httpx.post(
        f"{PROCUREMENT_API_URL}/compliance/check",
        json={"vendor_id": state["vendor_id"], "amount_usd": state["amount_usd"]},
    )
    response.raise_for_status()
    return {"history": [{"route": "check_compliance", "result": response.json()}]}


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
    return {"history": [{"route": "create_purchase_order", "result": response.json()}]}


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
    "finish": END,
})
# The loop: every specialist reports back to the supervisor instead of
# going straight to END, so the supervisor gets another turn to decide.
graph.add_edge("find_vendor", "supervisor")
graph.add_edge("check_compliance", "supervisor")
graph.add_edge("create_purchase_order", "supervisor")
app_graph = graph.compile()


def _run(raw_request: str) -> None:
    result = app_graph.invoke({
        "raw_request": raw_request,
        "route": None,
        "category": None,
        "vendor_id": None,
        "amount_usd": None,
        "requested_by": None,
        "history": [],
        "final_answer": None,
    })
    print(f"\n> {raw_request}")
    for i, step in enumerate(result["history"], start=1):
        print(f"  step {i}: {step['route']} -> {step['result']}")
    print(f"  final: {result['final_answer']}")


if __name__ == "__main__":
    _run("Check if vendor 2 is cleared to spend $12000, and if so create the PO for Alice.")
    _run("Check if vendor 3 is cleared to spend $75000, and if so create the PO for Bob.")
    _run("Find laptop vendors for us")
