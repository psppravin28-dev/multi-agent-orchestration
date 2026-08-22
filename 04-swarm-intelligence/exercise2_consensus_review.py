"""
Exercise 2: Consensus review (independent votes, majority rules)

Exercise 1 fanned out over DATA (one vendor per branch). This one fans
out over PERSPECTIVE: three reviewers look at the *same* purchase
request, each caring about something different -- compliance risk,
contract cost exposure, vendor relationship quality -- and each reaches
its own approve/reject independently, from its own tool call, with no
visibility into what the other two decided. Only after all three finish
does a tally node combine their votes.

This is what "swarm" adds that a single supervisor (Module 1) or a single
network orchestrator (Module 3) doesn't have: no individual agent's
verdict is authoritative by itself. A request only proceeds if a majority
of independent reviewers agree -- which also means the group can overrule
any one reviewer's mistake or narrow framing, including a case where the
three genuinely disagree.

Before running:
    - procurement app up (docker compose up -d && uvicorn app.main:app --reload)
    - OPENAI_API_KEY set in ../.env
"""
import operator
from typing import Annotated, Literal, Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
import httpx

load_dotenv()

PROCUREMENT_API_URL = "http://127.0.0.1:8000"


class ConsensusState(TypedDict):
    vendor_id: int
    amount_usd: float
    requested_by: Optional[str]
    votes: Annotated[list[dict], operator.add]
    final_answer: Optional[str]


class Vote(BaseModel):
    vote: Literal["approve", "reject"]
    reason: str = Field(description="One short sentence.")


vote_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(Vote)


def risk_reviewer(state: ConsensusState) -> dict:
    """Cares only about compliance/sanctions risk."""
    response = httpx.post(
        f"{PROCUREMENT_API_URL}/compliance/check",
        json={"vendor_id": state["vendor_id"], "amount_usd": state["amount_usd"]},
    )
    response.raise_for_status()
    compliance = response.json()
    decision = vote_llm.invoke([
        {"role": "system", "content": "You are a compliance risk reviewer. Approve only if the "
         "compliance check cleared the spend."},
        {"role": "user", "content": f"Compliance check result: {compliance}"},
    ])
    return {"votes": [{"reviewer": "risk", "vote": decision.vote, "reason": decision.reason}]}


def cost_reviewer(state: ConsensusState) -> dict:
    """Cares only about spend staying inside the vendor's contracted liability cap."""
    try:
        response = httpx.get(f"{PROCUREMENT_API_URL}/vendors/{state['vendor_id']}/contract")
        response.raise_for_status()
        contract = response.json()
        context = f"Vendor's contracted liability cap: ${contract['liability_cap_usd']:,.0f}. Requested amount: ${state['amount_usd']:,.0f}."
    except httpx.HTTPStatusError:
        context = f"No active contract on file for this vendor. Requested amount: ${state['amount_usd']:,.0f}."
    decision = vote_llm.invoke([
        {"role": "system", "content": "You are a contract cost reviewer. Approve only if the amount "
         "is within the vendor's contracted liability cap. If there is no contract on file, reject."},
        {"role": "user", "content": context},
    ])
    return {"votes": [{"reviewer": "cost", "vote": decision.vote, "reason": decision.reason}]}


def relationship_reviewer(state: ConsensusState) -> dict:
    """Cares only about vendor quality: rating and sanctions status."""
    response = httpx.get(f"{PROCUREMENT_API_URL}/vendors/{state['vendor_id']}")
    response.raise_for_status()
    vendor = response.json()
    decision = vote_llm.invoke([
        {"role": "system", "content": "You are a vendor relationship reviewer. Approve only if the "
         "vendor is not on the sanctions list and has a rating of 4.0 or above."},
        {"role": "user", "content": f"Vendor: {vendor}"},
    ])
    return {"votes": [{"reviewer": "relationship", "vote": decision.vote, "reason": decision.reason}]}


def tally(state: ConsensusState) -> Command[Literal["po_generation", "__end__"]]:
    approvals = sum(1 for v in state["votes"] if v["vote"] == "approve")
    total = len(state["votes"])
    summary = " | ".join(f"{v['reviewer']}: {v['vote']} ({v['reason']})" for v in state["votes"])

    if approvals > total / 2:
        return Command(goto="po_generation", update={"final_answer": f"Consensus APPROVE ({approvals}/{total}). {summary}"})

    return Command(
        goto=END,
        update={"final_answer": f"Consensus REJECT ({approvals}/{total} approved, no PO created). {summary}"},
    )


def po_generation(state: ConsensusState) -> dict:
    response = httpx.post(
        f"{PROCUREMENT_API_URL}/purchase-orders",
        json={
            "vendor_id": state["vendor_id"],
            "amount_usd": state["amount_usd"],
            "requested_by": state["requested_by"],
        },
    )
    response.raise_for_status()
    po = response.json()
    return {"final_answer": f"{state['final_answer']} -> PO {po['po_number']} created, status={po['status']}."}


graph = StateGraph(ConsensusState)
graph.add_node("risk_reviewer", risk_reviewer)
graph.add_node("cost_reviewer", cost_reviewer)
graph.add_node("relationship_reviewer", relationship_reviewer)
graph.add_node("tally", tally)
graph.add_node("po_generation", po_generation)
# Static parallel fan-out: three fixed edges out of START, all running
# concurrently, all converging on "tally" (LangGraph waits for all three
# before running a node with multiple incoming edges).
graph.add_edge(START, "risk_reviewer")
graph.add_edge(START, "cost_reviewer")
graph.add_edge(START, "relationship_reviewer")
graph.add_edge("risk_reviewer", "tally")
graph.add_edge("cost_reviewer", "tally")
graph.add_edge("relationship_reviewer", "tally")
graph.add_edge("po_generation", END)
app_graph = graph.compile()


def _run(vendor_id: int, amount_usd: float, requested_by: str) -> None:
    result = app_graph.invoke({
        "vendor_id": vendor_id,
        "amount_usd": amount_usd,
        "requested_by": requested_by,
        "votes": [],
        "final_answer": None,
    })
    print(f"\n> vendor_id={vendor_id} amount_usd={amount_usd}")
    for v in result["votes"]:
        print(f"  {v['reviewer']}: {v['vote']} -- {v['reason']}")
    print(f"  {result['final_answer']}")


if __name__ == "__main__":
    _run(vendor_id=1, amount_usd=9000, requested_by="Meera")
    _run(vendor_id=6, amount_usd=5000, requested_by="Meera")

    # A genuine 2-1 split: give vendor 3 a small contract cap, then request
    # more than that cap but still under the global compliance threshold --
    # risk and relationship approve, cost dissents, majority still wins.
    httpx.post(
        f"{PROCUREMENT_API_URL}/contracts",
        json={"vendor_id": 3, "liability_cap_usd": 10_000, "payment_terms": "Net-30"},
    ).raise_for_status()
    _run(vendor_id=3, amount_usd=20000, requested_by="Meera")
