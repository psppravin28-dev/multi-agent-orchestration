# Module 2: Handoff patterns

Read [../learning-path/README.md](README.md) and
[01-hierarchical-delegation.md](01-hierarchical-delegation.md) first —
this module is explained by contrast with Module 1's router-function
approach. Have [../02-handoff-patterns/](../02-handoff-patterns/) open
alongside this.

## What's actually new here

In Module 1, "deciding where the graph goes next" was always a
**separate function** from the node that did the work —
`route_after_supervisor` was its own thing, distinct from `supervisor`.
That's a hub-and-spoke shape: one central decision-maker, workers that
just report back.

Module 2 introduces **`Command`** — a return value that lets a node
decide its own destination *and* update state in the same step, with no
separate router function at all:

```python
return Command(goto="some_node", update={"key": "value"})
```

That single change is what makes a **handoff** possible: control passed
directly from one agent to another, agent-to-agent, rather than always
flowing back through one central dispatcher.

## Exercise 1 — `Command` mechanics warm-up

Open [exercise1_command_handoff.py](../02-handoff-patterns/exercise1_command_handoff.py).
Structurally it looks like Module 1 Exercise 2 (one intake step, two
possible specialists) — deliberately, so the mechanism can be compared
directly.

1. `intake_agent` (lines 59-75) — classifies the request via structured
   output, same as before, **but instead of returning a dict**, it
   returns `Command(goto=decision.next_agent, update={...})`. The
   routing decision (`goto`) and the state update happen in one object,
   from inside the node itself.
2. `vendor_sourcing` (lines 78-84) and `compliance` (lines 87-93) — each
   does its API call, then returns `Command(goto=END, update={"result": ...})`.
   Notice: **`END` is a valid `goto` target**, not just a graph-level
   edge.
3. The wiring (lines 100-105) — read the comment on lines 96-99
   carefully. There's `add_edge(START, "intake_agent")` and *nothing
   else*. No `add_conditional_edges`, no edges out of `intake_agent` at
   all. Each node's own `Command.goto` **is** the edge — LangGraph
   doesn't need edges declared in advance for a `Command`-returning
   node.

Compare this directly against Module 1 Exercise 2's
`route_after_supervisor` + `add_conditional_edges` — same routing
outcome, achieved by collapsing "decide" and "act" into one function
instead of two.

📺 [How Agent Handoff Works in LangGraph | Multi-Agent LLM Workflow Tutorial](https://www.youtube.com/watch?v=p1c_pm6LWI0)
📖 [Command: A new tool for building multi-agent architectures in LangGraph](https://blog.langchain.com/command-a-new-tool-for-multi-agent-architectures-in-langgraph/) —
the LangChain team's own writeup of exactly this primitive, worth
reading once.

## Exercise 2 — a real peer-to-peer chain

Open [exercise2_peer_handoff_chain.py](../02-handoff-patterns/exercise2_peer_handoff_chain.py).
Exercise 1 was still secretly a hub — `intake_agent` was the *only* node
making a decision; the two specialists it handed off to just finished.
This exercise removes the hub entirely.

1. `intake_agent` (lines 64-81) — extracts contract details, hands off
   to `contract_review`. Nothing new yet.
2. `contract_review` (lines 84-112) — this is the important one. It
   creates the contract via the real API, **then decides for itself**
   (lines 98-101) whether the deal is big enough to also need a
   compliance check:
   ```python
   if state["liability_cap_usd"] >= COMPLIANCE_ESCALATION_THRESHOLD_USD:
       return Command(goto="compliance", update=history_entry)
   ```
   If so, it hands off **directly to `compliance`** — control never
   routes back through `intake_agent` to make that call. If not, it goes
   straight to `END` itself (lines 103-112).
3. `compliance` (lines 115-131) — same shape as before, finishes at
   `END`.

**The mental model that matters:** in Module 1, only the supervisor
could ever decide "what's next" — every worker reported back to one
place. Here, *whichever agent currently holds control* decides, and it
might not be the agent that started the chain. `intake_agent` doesn't
know or care that `contract_review` might later hand off to
`compliance` — that decision lives entirely inside `contract_review`.

One more deliberate design choice worth noticing: the escalation check
(line 98) is a **plain Python `if`, not an LLM call**. This mirrors the
procurement app's own philosophy (see
[`compliance.py`'s docstring](https://github.com/psppravin28-dev/multi-agent-orchestration/blob/main/prerequisites/procurement-app/app/routers/compliance.py#L13-L17)
in the delivered app): policy thresholds are business logic you can
audit and version-control, not something you'd want an LLM guessing at
from a prompt every time.

Verified behavior: a $30,000 contract finishes right after
`contract_review`; a $200,000 contract hands off to `compliance`, which
correctly flags it as needing CFO sign-off.

📺 [LangGraph Advanced – Improve Multi Agent AI Systems with Custom Handoffs in Supervisor Architecture](https://www.youtube.com/watch?v=rn4TkOGYU64)

---

**Checkpoint:** in Module 1 Exercise 3, the supervisor looped by having
every specialist edge *back to the supervisor*. Here in Exercise 2,
`contract_review` hands off *laterally* to `compliance` — no loop back
anywhere. Make sure you can explain **why** you don't need a loop here
the way Module 1 did — what's structurally different about a chain of
one-way handoffs versus a supervisor that keeps re-evaluating? (Hint:
look at how many times each node in Exercise 2 can possibly run.)
