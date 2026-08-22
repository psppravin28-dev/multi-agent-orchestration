"""
Exercise 2: Peer handoff chain (agent decides its own next hop)

Exercise 1 still had a hub shape: intake_agent was the only node making a
routing decision, the specialists it handed off to just finished the
graph. This exercise removes the hub. contract_review, once it has done
its own job, decides FOR ITSELF whether the deal also needs a compliance
check -- and if so hands off directly to compliance. Nothing routes back
through intake_agent to make that call. That's the real difference from
Module 1's hierarchical delegation: there, only the supervisor could ever
decide "what's next"; here, whichever agent currently holds control
decides, and it may not be the same agent that started the chain.

The decision to escalate to compliance is a plain threshold check, not an
LLM call -- deliberately mirroring the procurement app's own philosophy
(see compliance.py's docstring): policy thresholds are business logic,
not something to leave to a prompt.

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

# Same figure the procurement app itself flags spend at (schemas.py's
# COMPLIANCE_FLAG_THRESHOLD_USD) -- contracts with a liability cap at or
# above it are exactly the ones compliance would also want to see.
COMPLIANCE_ESCALATION_THRESHOLD_USD = 50_000


class ChainState(TypedDict):
    raw_request: str
    vendor_id: Optional[int]
    liability_cap_usd: Optional[float]
    payment_terms: Optional[str]
    term_months: Optional[int]
    history: Annotated[list[dict], operator.add]
    final_answer: Optional[str]


class IntakeExtraction(BaseModel):
    vendor_id: int = Field(description="Which vendor the contract is with.")
    liability_cap_usd: float = Field(description="The liability cap for the contract, in USD.")
    payment_terms: str = Field(default="Net-30", description="e.g. 'Net-30', 'Net-60'.")
    term_months: int = Field(default=12, description="Contract length in months.")


intake_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(IntakeExtraction)


def intake_agent(state: ChainState) -> Command[Literal["contract_review"]]:
    extraction = intake_llm.invoke([
        {
            "role": "system",
            "content": "Extract the contract details from this request. "
            "Default payment_terms to Net-30 and term_months to 12 if not mentioned.",
        },
        {"role": "user", "content": state["raw_request"]},
    ])
    return Command(
        goto="contract_review",
        update={
            "vendor_id": extraction.vendor_id,
            "liability_cap_usd": extraction.liability_cap_usd,
            "payment_terms": extraction.payment_terms,
            "term_months": extraction.term_months,
        },
    )


def contract_review(state: ChainState) -> Command[Literal["compliance", "__end__"]]:
    response = httpx.post(
        f"{PROCUREMENT_API_URL}/contracts",
        json={
            "vendor_id": state["vendor_id"],
            "liability_cap_usd": state["liability_cap_usd"],
            "payment_terms": state["payment_terms"],
            "term_months": state["term_months"],
        },
    )
    response.raise_for_status()
    contract = response.json()
    history_entry = {"history": [{"agent": "contract_review", "result": contract}]}

    if state["liability_cap_usd"] >= COMPLIANCE_ESCALATION_THRESHOLD_USD:
        # Peer handoff: contract_review decided this on its own -- control
        # never passes back through intake_agent.
        return Command(goto="compliance", update=history_entry)

    return Command(
        goto=END,
        update={
            **history_entry,
            "final_answer": (
                f"Contract {contract['id']} created for vendor {state['vendor_id']} "
                f"(cap ${state['liability_cap_usd']:,.0f}, below compliance threshold, no review needed)."
            ),
        },
    )


def compliance(state: ChainState) -> Command[Literal["__end__"]]:
    response = httpx.post(
        f"{PROCUREMENT_API_URL}/compliance/check",
        json={"vendor_id": state["vendor_id"], "amount_usd": state["liability_cap_usd"]},
    )
    response.raise_for_status()
    result = response.json()
    return Command(
        goto=END,
        update={
            "history": [{"agent": "compliance", "result": result}],
            "final_answer": (
                f"Contract created for vendor {state['vendor_id']} "
                f"(cap ${state['liability_cap_usd']:,.0f}); compliance review: {result['reason']}"
            ),
        },
    )


graph = StateGraph(ChainState)
graph.add_node("intake_agent", intake_agent)
graph.add_node("contract_review", contract_review)
graph.add_node("compliance", compliance)
graph.add_edge(START, "intake_agent")
app_graph = graph.compile()


def _run(raw_request: str) -> None:
    result = app_graph.invoke({
        "raw_request": raw_request,
        "vendor_id": None,
        "liability_cap_usd": None,
        "payment_terms": None,
        "term_months": None,
        "history": [],
        "final_answer": None,
    })
    print(f"\n> {raw_request}")
    for step in result["history"]:
        print(f"  {step['agent']} -> {step['result']}")
    print(f"  final: {result['final_answer']}")


if __name__ == "__main__":
    _run("Set up a contract with vendor 1, liability cap $30000, Net-30")
    _run("Set up a contract with vendor 2, liability cap $200000, Net-60, 24 months")
