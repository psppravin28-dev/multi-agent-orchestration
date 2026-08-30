# Module 3: Specialist network

Read [../learning-path/README.md](README.md),
[01-hierarchical-delegation.md](01-hierarchical-delegation.md), and
[02-handoff-patterns.md](02-handoff-patterns.md) first — this module is
explained by contrast with both. Have
[../03-specialist-network/](../03-specialist-network/) open alongside
this, with the procurement app running (`docker compose up -d`, then
`uvicorn app.main:app --reload` from `../prerequisites/procurement-app/`).

## What's actually new here

Modules 1 and 2 both routed with a **graph primitive** — a conditional
edge in Module 1, a `Command` in Module 2. Either way, something
explicit in *your* code decided which node ran next, and you could point
to the exact line that made that decision.

Module 3 removes that entirely. Every specialist becomes an ordinary
LLM **tool**, exposed to one model via `bind_tools`, and the model's own
native tool-calling decides which tool(s) to call, in what order, and
how many times — there's no router function and no `Command.goto`
anywhere in this module's code. The routing mechanism *is* "give the
model a list of functions and let it decide."

## Exercise 1 — agents-as-tools mechanics warm-up

Open [exercise1_agents_as_tools.py](../03-specialist-network/exercise1_agents_as_tools.py).

1. Four `@tool`-decorated functions (lines 37-76) — `search_vendors`,
   `get_vendor_contract_terms`, `check_compliance_policy`,
   `generate_purchase_order` — each a thin `httpx` wrapper around the
   real procurement API. Notice each one's docstring isn't documentation
   for you; like `Field(description=...)` in Module 1's structured
   output, it's sent to the model as the tool's schema description, and
   it's the *only* thing the model has to decide when to call it.
2. `llm = ChatOpenAI(...).bind_tools(TOOLS)` (line 86) — this is the
   whole mechanism. Compare it to Module 1's
   `.with_structured_output(SupervisorDecision)`: that forced one shaped
   answer back; `bind_tools` instead gives the model a *menu* it can pick
   from zero or more times per turn.
3. `agent` node (lines 89-90) — deliberately tiny: invoke the tool-bound
   LLM on the message history, append whatever it returns (an answer, or
   a request to call tools).
4. The wiring (lines 98-104) — the classic ReAct loop: `agent` →
   (`tools_condition` checks the last message for tool calls) → `tools`
   (a prebuilt `ToolNode` that executes whatever got called) → back to
   `agent` → repeat until the model answers with no tool calls.
   `tools_condition` is LangGraph's own prebuilt router — you didn't
   write it, because for this exact shape ("did the last AI message
   request tools, yes or no") there's nothing request-specific to
   decide.

**Verified behavior** (ran live against the seeded procurement app):
for *"Find laptop vendors, then check if the top-rated one is cleared to
spend $8000"*, the model called `search_vendors({'category': 'laptops'})`
on its own initiative, read the three results back, picked the
top-rated one (Dell Business, 4.6) **itself** — nothing in the code told
it which vendor was "top-rated" — then called
`check_compliance_policy({'vendor_id': 1, 'amount_usd': 8000})` before
answering. Two tool calls, in a sequence nobody coded, to satisfy one
request. A second, unrelated request ("contract terms for vendor 2")
called only `get_vendor_contract_terms` and skipped the other three
tools entirely.

📺 [Tool-Calling Agent in LangGraph 🤖](https://www.youtube.com/watch?v=Nou6Jwsfe7w)
📖 [Use the graph API — Docs by LangChain](https://docs.langchain.com/oss/python/langgraph/use-graph-api) —
covers `bind_tools`, `ToolNode`, and `tools_condition` from the source.

## Exercise 2 — specialist consults specialist

Open [exercise2_specialist_consults_specialist.py](../03-specialist-network/exercise2_specialist_consults_specialist.py).
Exercise 1's network was one hop deep — the orchestrator called a tool,
the tool called the API, done. This exercise makes it a **mesh**: a tool
can itself be a small agent that calls another tool.

1. `_po_agent_llm` (line 63) — a *second*, private `ChatOpenAI` instance,
   bound only to `check_compliance_policy`, that only
   `generate_purchase_order` ever touches. The top-level orchestrator's
   `llm` (line 105) never sees it.
2. `generate_purchase_order` (lines 71-96) — this single `@tool`
   function is now a complete little agent loop by hand: it invokes
   `_po_agent_llm` (line 79), manually executes whatever tool call comes
   back by calling `check_compliance_policy.invoke(...)` directly (line
   83 — no `ToolNode` involved, just a plain function call), feeds the
   result back as a `ToolMessage` (line 84), invokes the model again for
   a final `CREATE`-or-not decision (line 86), and only then does the
   real `POST` (lines 88-94).
3. The system prompt at lines 65-68 — *"ALWAYS call
   check_compliance_policy first... never create a PO on your own
   judgement."* This is a prompt-level guarantee, not a code-level one —
   worth noticing, since the docstring at line 73 tells *callers* they
   don't need to check compliance themselves.

**The mesh point:** `check_compliance_policy` is reachable two ways —
directly, if the top-level orchestrator decides to call it itself, *and*
indirectly, buried inside `generate_purchase_order`, invisible to
whoever called that tool. That's a network topology, not a fixed call
graph: the same specialist can be a leaf for one caller and an internal
dependency for another, and nothing forces you to draw that as a single
diagram the way Module 1's `add_conditional_edges` dict could be.

**Verified behavior:** a request for vendor 1, $9,000 came back as
`{"status": "issued", "po_number": "PO-...", "compliance_note": "Dell
Business not restricted; spend within delegated authority."}` — created
in one orchestrator-visible tool call, with the compliance check having
happened invisibly inside it. A request for vendor 3, $75,000 came back
`{"created": false, "reason": "Spend of $75,000 requires CFO sign-off
per policy P-204."}` — refused, again without the orchestrator ever
calling `check_compliance_policy` itself; `generate_purchase_order`
caught it internally.

---

**Checkpoint:** Module 2's Exercise 2 also had one specialist
(`contract_review`) decide on its own to bring in another
(`compliance`) — a plain Python `if`, not an LLM call. Here,
`generate_purchase_order` also decides to consult `check_compliance_policy`
on its own. What's structurally different between the two? (Hint: look
at *how* each one decides to escalate — a `Command.goto` chosen by
reading a threshold, versus a tool call chosen by an LLM reading a
system prompt — and what that difference means for how confident you can
be, ahead of time, that the escalation will actually happen every time.)
