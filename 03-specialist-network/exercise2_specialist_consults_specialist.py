"""
Exercise 2: Specialist consults specialist

Exercise 1's network was one hop deep: the orchestrator called tools, the
tools called the procurement API, done. A real specialist network is a
mesh -- a specialist can be a *consumer* of another specialist too, and
that connection doesn't have to be visible to (or controlled by) whoever
is calling the first specialist.

Here, generate_purchase_order stops being a thin HTTP wrapper and becomes
its own small agent: before it will create a PO, it calls
check_compliance_policy itself and reads the result before deciding.
The top-level orchestrator that calls generate_purchase_order has no idea
that happened -- from its point of view it called one tool and got back
either a created PO or a refusal reason. That's the point: network
topology, not a fixed call graph -- the same check_compliance_policy tool
is reachable both directly (orchestrator -> compliance) and indirectly
(orchestrator -> po_generation -> compliance).

Before running:
    - procurement app up (docker compose up -d && uvicorn app.main:app --reload)
    - OPENAI_API_KEY set in ../.env
"""
from typing import Optional

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
import httpx

load_dotenv()

PROCUREMENT_API_URL = "http://127.0.0.1:8000"


@tool
def search_vendors(category: str, min_rating: float = 4.0) -> list[dict]:
    """Search active vendors by category and minimum rating.
    Categories: laptops, office_supplies, software_licenses."""
    response = httpx.get(
        f"{PROCUREMENT_API_URL}/vendors",
        params={"category": category, "min_rating": min_rating},
    )
    response.raise_for_status()
    return response.json()


@tool
def check_compliance_policy(vendor_id: int, amount_usd: float) -> dict:
    """Check whether a vendor id is cleared to spend a given amount in USD."""
    response = httpx.post(
        f"{PROCUREMENT_API_URL}/compliance/check",
        json={"vendor_id": vendor_id, "amount_usd": amount_usd},
    )
    response.raise_for_status()
    return response.json()


# --- po_generation's own private sub-agent -- only it uses this model ---
_po_agent_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools([check_compliance_policy])

_PO_AGENT_SYSTEM_PROMPT = """You handle purchase order requests. ALWAYS call check_compliance_policy
first for the given vendor_id and amount_usd -- never create a PO on your own judgement. After you
see the compliance result, respond with exactly the single word CREATE if cleared, or a short
explanation of why not if it isn't. Say nothing else."""


@tool
def generate_purchase_order(vendor_id: int, amount_usd: float, requested_by: Optional[str] = None) -> dict:
    """Create a purchase order for a vendor after independently verifying compliance.
    Callers do not need to check compliance first -- this specialist does that itself."""
    messages = [
        SystemMessage(_PO_AGENT_SYSTEM_PROMPT),
        HumanMessage(f"vendor_id={vendor_id}, amount_usd={amount_usd}, requested_by={requested_by}"),
    ]
    ai_msg = _po_agent_llm.invoke(messages)
    messages.append(ai_msg)

    for call in ai_msg.tool_calls:
        result = check_compliance_policy.invoke(call["args"])
        messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))

    decision: AIMessage = _po_agent_llm.invoke(messages)

    if decision.content.strip().upper() == "CREATE":
        response = httpx.post(
            f"{PROCUREMENT_API_URL}/purchase-orders",
            json={"vendor_id": vendor_id, "amount_usd": amount_usd, "requested_by": requested_by},
        )
        response.raise_for_status()
        return response.json()

    return {"created": False, "reason": decision.content}


TOOLS = [search_vendors, check_compliance_policy, generate_purchase_order]

ORCHESTRATOR_SYSTEM_PROMPT = """You are a procurement orchestrator. You have specialist tools
available -- call whichever ones you need. generate_purchase_order already verifies compliance
internally, so you do not need to call check_compliance_policy yourself before using it."""

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools(TOOLS)


def agent(state: MessagesState) -> dict:
    return {"messages": [llm.invoke(state["messages"])]}


graph = StateGraph(MessagesState)
graph.add_node("agent", agent)
graph.add_node("tools", ToolNode(TOOLS))
graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", tools_condition)
graph.add_edge("tools", "agent")
app_graph = graph.compile()


def _run(raw_request: str) -> None:
    result = app_graph.invoke({
        "messages": [
            SystemMessage(ORCHESTRATOR_SYSTEM_PROMPT),
            HumanMessage(raw_request),
        ]
    })
    print(f"\n> {raw_request}")
    for msg in result["messages"][1:]:
        if getattr(msg, "tool_calls", None):
            for call in msg.tool_calls:
                print(f"  [orchestrator -> {call['name']}] {call['args']}")
        elif msg.type == "tool":
            print(f"  [{msg.name} result] {msg.content}")
        elif msg.type == "ai":
            print(f"  [answer] {msg.content}")


if __name__ == "__main__":
    _run("Create a PO for vendor 1, $9000, requested by Priya")
    _run("Create a PO for vendor 3, $75000, requested by Priya")
