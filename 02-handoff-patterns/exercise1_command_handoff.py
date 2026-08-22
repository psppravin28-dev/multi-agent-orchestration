"""
Exercise 1: Command handoff mechanics warm-up

Module 1's supervisor used add_conditional_edges: a *separate* routing
function inspected state and told the graph where to go, while the node
itself only ever returned a plain dict of state updates. LangGraph's other
primitive, `Command`, collapses that into one step: a node returns
`Command(goto=<next node>, update=<state updates>)`, deciding its own
destination instead of a router deciding for it.

That distinction is the whole point of "handoff patterns" -- a handoff is
control passed directly, agent to agent, with no separate dispatcher in
between. This exercise is the smallest possible version of that: one
intake agent, and it hands off directly to whichever specialist should
own the request.

Before running:
    - procurement app up (docker compose up -d && uvicorn app.main:app --reload)
    - OPENAI_API_KEY set in ../.env
"""
from typing import Literal, Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
import httpx

load_dotenv()

PROCUREMENT_API_URL = "http://127.0.0.1:8000"

NextAgent = Literal["vendor_sourcing", "compliance"]


class HandoffState(TypedDict):
    raw_request: str
    category: Optional[str]
    vendor_id: Optional[int]
    amount_usd: Optional[float]
    result: Optional[dict]


class IntakeDecision(BaseModel):
    next_agent: NextAgent = Field(
        description="vendor_sourcing for requests to find vendors in a category; "
        "compliance for requests asking whether a vendor id is cleared to spend an amount."
    )
    category: Optional[str] = Field(default=None, description="Only for vendor_sourcing.")
    vendor_id: Optional[int] = Field(default=None, description="Only for compliance.")
    amount_usd: Optional[float] = Field(default=None, description="Only for compliance.")


intake_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(IntakeDecision)


def intake_agent(state: HandoffState) -> Command[NextAgent]:
    decision = intake_llm.invoke([
        {
            "role": "system",
            "content": "Classify the procurement request and hand it off to the right specialist. "
            "Categories: laptops, office_supplies, software_licenses.",
        },
        {"role": "user", "content": state["raw_request"]},
    ])
    return Command(
        goto=decision.next_agent,
        update={
            "category": decision.category,
            "vendor_id": decision.vendor_id,
            "amount_usd": decision.amount_usd,
        },
    )


def vendor_sourcing(state: HandoffState) -> Command[Literal["__end__"]]:
    response = httpx.get(
        f"{PROCUREMENT_API_URL}/vendors",
        params={"category": state["category"], "min_rating": 4.0},
    )
    response.raise_for_status()
    return Command(goto=END, update={"result": response.json()})


def compliance(state: HandoffState) -> Command[Literal["__end__"]]:
    response = httpx.post(
        f"{PROCUREMENT_API_URL}/compliance/check",
        json={"vendor_id": state["vendor_id"], "amount_usd": state["amount_usd"]},
    )
    response.raise_for_status()
    return Command(goto=END, update={"result": response.json()})


# --- graph wiring ---
# Note there's no add_conditional_edges and no edges out of intake_agent at
# all -- each node's own Command.goto IS the edge. The graph only needs a
# fixed edge for the one hop that isn't a decision: START -> intake_agent.
graph = StateGraph(HandoffState)
graph.add_node("intake_agent", intake_agent)
graph.add_node("vendor_sourcing", vendor_sourcing)
graph.add_node("compliance", compliance)
graph.add_edge(START, "intake_agent")
app_graph = graph.compile()


def _run(raw_request: str) -> None:
    result = app_graph.invoke({
        "raw_request": raw_request,
        "category": None,
        "vendor_id": None,
        "amount_usd": None,
        "result": None,
    })
    print(f"\n> {raw_request}")
    print(f"  result: {result['result']}")


if __name__ == "__main__":
    _run("Find office supplies vendors")
    _run("Is vendor 1 cleared to spend $10000?")
