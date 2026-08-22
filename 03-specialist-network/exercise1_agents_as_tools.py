"""
Exercise 1: Agents-as-tools mechanics warm-up

Modules 1 and 2 both routed with graph primitives -- conditional edges or
Command -- something explicit in the code decided which node ran next. A
specialist *network* routes differently: every specialist is exposed to
one orchestrator as an ordinary LLM tool, and the model's own native
tool-calling decides which to call, how many times, and in what order.
There's no router function to write at all; `bind_tools` plus a
loop until the model stops calling tools *is* the routing mechanism.

The four tools below map 1:1 onto the procurement app's own docstrings
("this is what the vendor_sourcing agent's search_vendors tool calls",
etc, in vendors.py/contracts.py/compliance.py/purchase_orders.py) -- the
delivered app was already scaffolded assuming this exact specialist
lineup.

Before running:
    - procurement app up (docker compose up -d && uvicorn app.main:app --reload)
    - OPENAI_API_KEY set in ../.env
"""
from typing import Optional

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
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
def get_vendor_contract_terms(vendor_id: int) -> dict:
    """Get the active contract terms (payment terms, liability cap, etc) for a vendor id."""
    response = httpx.get(f"{PROCUREMENT_API_URL}/vendors/{vendor_id}/contract")
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


@tool
def generate_purchase_order(vendor_id: int, amount_usd: float, requested_by: Optional[str] = None) -> dict:
    """Create a purchase order for a vendor id and amount in USD, optionally naming a requester."""
    response = httpx.post(
        f"{PROCUREMENT_API_URL}/purchase-orders",
        json={"vendor_id": vendor_id, "amount_usd": amount_usd, "requested_by": requested_by},
    )
    response.raise_for_status()
    return response.json()


TOOLS = [search_vendors, get_vendor_contract_terms, check_compliance_policy, generate_purchase_order]

ORCHESTRATOR_SYSTEM_PROMPT = """You are a procurement orchestrator. You have four specialist tools
available -- call whichever ones you need, in whatever order, as many times as needed, to fully
answer the request. Don't guess data you can look up with a tool. When you're done, give the user
a short plain-language summary."""

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools(TOOLS)


def agent(state: MessagesState) -> dict:
    return {"messages": [llm.invoke(state["messages"])]}


# --- graph wiring ---
# The classic ReAct shape: agent decides (possibly calling tools), tools
# node executes whatever it called, control returns to agent, repeat until
# the model responds without any tool calls. `tools_condition` is a
# prebuilt router that reads the last message's tool_calls for us.
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
                print(f"  [tool call] {call['name']}({call['args']})")
        elif msg.type == "tool":
            print(f"  [tool result] {msg.content}")
        elif msg.type == "ai":
            print(f"  [answer] {msg.content}")


if __name__ == "__main__":
    _run("Find laptop vendors, then check if the top-rated one is cleared to spend $8000")
    _run("What are the contract terms for vendor 2?")
