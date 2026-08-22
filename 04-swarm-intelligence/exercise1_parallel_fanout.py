"""
Exercise 1: Parallel fan-out mechanics warm-up

Every graph so far has been sequential -- one node at a time, even inside
Module 1's loop. Swarm intelligence starts from a different premise: run
many independent workers on many independent pieces of a problem *at the
same time*, then combine what they found. Here, instead of one supervisor
picking one vendor to check, EVERY vendor in a category gets scored
concurrently, and only then does something decide which is best.

The mechanic that makes a dynamic (unknown until runtime) number of
parallel branches possible is `Send` -- a conditional-edge function
returns one Send(node_name, payload) per branch it wants to spawn,
instead of returning a single next-node name. LangGraph fans all of them
out, runs them concurrently, and joins their results (via the `scores`
reducer) before the next node runs.

Before running:
    - procurement app up (docker compose up -d && uvicorn app.main:app --reload)
    - OPENAI_API_KEY set in ../.env
"""
import operator
from typing import Annotated, Optional

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from typing_extensions import TypedDict
import httpx

load_dotenv()

PROCUREMENT_API_URL = "http://127.0.0.1:8000"


class SwarmState(TypedDict):
    category: str
    amount_usd: float
    vendors: list[dict]
    # operator.add reducer: every parallel score_vendor branch appends one
    # entry here; LangGraph merges them all before "aggregate" runs.
    scores: Annotated[list[dict], operator.add]
    best: Optional[dict]


class ScoreVendorInput(TypedDict):
    vendor: dict
    amount_usd: float


def find_candidates(state: SwarmState) -> dict:
    response = httpx.get(
        f"{PROCUREMENT_API_URL}/vendors",
        params={"category": state["category"], "min_rating": 0.0},
    )
    response.raise_for_status()
    return {"vendors": response.json()}


def fan_out_to_scorers(state: SwarmState) -> list[Send]:
    return [
        Send("score_vendor", {"vendor": vendor, "amount_usd": state["amount_usd"]})
        for vendor in state["vendors"]
    ]


def score_vendor(payload: ScoreVendorInput) -> dict:
    vendor = payload["vendor"]
    response = httpx.post(
        f"{PROCUREMENT_API_URL}/compliance/check",
        json={"vendor_id": vendor["id"], "amount_usd": payload["amount_usd"]},
    )
    response.raise_for_status()
    cleared = response.json()["cleared"]
    # Disqualify anything not cleared to spend, rather than let a high
    # rating alone win -- score is a joint fitness signal, not just rating.
    score = vendor["rating"] if cleared else -1.0
    return {
        "scores": [
            {"vendor_id": vendor["id"], "name": vendor["name"], "rating": vendor["rating"], "cleared": cleared, "score": score}
        ]
    }


def aggregate(state: SwarmState) -> dict:
    best = max(state["scores"], key=lambda s: s["score"])
    return {"best": best}


graph = StateGraph(SwarmState)
graph.add_node("find_candidates", find_candidates)
graph.add_node("score_vendor", score_vendor)
graph.add_node("aggregate", aggregate)
graph.add_edge(START, "find_candidates")
graph.add_conditional_edges("find_candidates", fan_out_to_scorers, ["score_vendor"])
graph.add_edge("score_vendor", "aggregate")
graph.add_edge("aggregate", END)
app_graph = graph.compile()


def _run(category: str, amount_usd: float) -> None:
    result = app_graph.invoke({
        "category": category,
        "amount_usd": amount_usd,
        "vendors": [],
        "scores": [],
        "best": None,
    })
    print(f"\n> category={category!r} amount_usd={amount_usd}")
    for s in sorted(result["scores"], key=lambda s: -s["score"]):
        flag = "" if s["cleared"] else "  (disqualified: not cleared)"
        print(f"  {s['name']}: rating={s['rating']} score={s['score']}{flag}")
    print(f"  best: {result['best']['name']}")


if __name__ == "__main__":
    _run("laptops", 15000)
