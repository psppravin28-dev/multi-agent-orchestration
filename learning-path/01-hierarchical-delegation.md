# Module 1: Hierarchical delegation

Read [../learning-path/README.md](README.md) first if you haven't — it
covers the vocabulary (state, node, edge, structured output, etc.) this
file assumes. Have [../01-hierarchical-delegation/](../01-hierarchical-delegation/)
open alongside this.

## Exercise 1 — mechanics warm-up, no AI yet

Open [exercise1_warmup.py](../01-hierarchical-delegation/exercise1_warmup.py).
Deliberately, this file never calls an LLM — its only job is to make
LangGraph's plumbing click before any "brain" gets added.

Walk it in order:

1. `IntakeState` (lines 15-19) — the state schema. Every field here is
   something a node might read or write.
2. `parse_request` (lines 22-39) — a node. It receives `state`, returns
   `{"category": ..., "amount_usd": ...}` — note it does **not** return
   the whole state, just the keys it's changing.
3. `lookup_vendors` (lines 42-48) — a second node, calling the real
   procurement API with `httpx`.
4. The wiring (lines 51-57) — `add_edge(START, "parse_request")` then
   `add_edge("parse_request", "lookup_vendors")` then
   `add_edge("lookup_vendors", END)`. This is a straight line: A → B →
   done. No decisions anywhere.

**Try this yourself:** run it, then change `raw_request` in the
`__main__` block to a different category/amount and re-run — watch how
`category`/`amount_usd` change but the graph shape doesn't.

📺 [LangGraph Deep Dive — State, Nodes, Edges & Agents Explained Clearly](https://www.youtube.com/watch?v=GE7mqOhAj_o)

## Exercise 2 — a decision enters the graph

Open [exercise2_supervisor_routing.py](../01-hierarchical-delegation/exercise2_supervisor_routing.py).
Now an LLM shows up, and with it, the first *branch*.

1. `SupervisorDecision` (lines 43-56) — this Pydantic class is the schema
   forced onto the LLM's output. The `Field(description=...)` text isn't
   a comment for humans — it's sent to the model as part of the schema,
   literally telling it what each field means.
2. `supervisor_llm = ChatOpenAI(...).with_structured_output(SupervisorDecision)`
   (lines 70-72) — this is the line that turns "free-text LLM" into "LLM
   that only returns valid `SupervisorDecision` objects."
3. `supervisor` node (lines 75-86) — sends a system prompt (the routing
   policy) + the user's raw request, gets back a typed decision, writes
   its fields into state.
4. `route_after_supervisor` (lines 89-90) — a plain function of state,
   returns a string key. This is the **router**: a separate function,
   distinct from the node itself, deciding where to go next.
5. `add_conditional_edges("supervisor", route_after_supervisor, {...})`
   (lines 130-134) — the dict maps whatever `route_after_supervisor`
   returns to an actual node name. This is the mechanic that makes
   hierarchical delegation *hierarchical*: one decision-maker, three
   possible next-hops.

The key mental model: **the node computes; a separate router function
decides where the graph goes next.** Those are two different
responsibilities in Module 1. (Module 2 merges them into one — that's
the whole point of `Command`.)

📺 [Hierarchical multi-agent systems with LangGraph](https://www.youtube.com/watch?v=B_0TNuYi56w) —
this is literally the pattern this exercise builds, explained by the
people who built LangGraph.

## Exercise 3 — the loop, and a real bug worth understanding

Open [exercise3_supervisor_loop.py](../01-hierarchical-delegation/exercise3_supervisor_loop.py).
The one change that matters most:

```python
graph.add_edge("find_vendor", "supervisor")
graph.add_edge("check_compliance", "supervisor")
graph.add_edge("create_purchase_order", "supervisor")
```

In Exercise 2, every specialist edged to `END`. Here, every specialist
edges **back to `supervisor`** — so after each delegation, the
supervisor gets another turn to look at what just happened and decide:
delegate again, or finish (`"finish"` maps to `END` in the
conditional-edges dict).

Two things to internalize:

- `history: Annotated[list[dict], operator.add]` (lines 48-50) — this
  `Annotated[..., operator.add]` is a **reducer**. Normally a node's
  returned dict *overwrites* that state key. With this annotation, each
  node's `{"history": [...]}` return gets *appended* to the existing
  list instead — which is exactly what lets the loop accumulate a trail
  of everything delegated so far without each turn wiping out the last.
- `MAX_DELEGATIONS` safety cap (lines 34-37) — a loop driven by an LLM's
  own judgment about when to stop needs a hard backstop, or a confused
  model spins forever.

### The scope-creep bug (worth remembering for any future supervisor loop)

When this was first built, the request *"Find laptop vendors for us"*
crashed. The supervisor, after seeing `find_vendor`'s results, decided
on its own to *also* check compliance on one of the vendors found — even
though nothing asked for that — then had no vendor/amount to check
compliance *for*, and crashed.

That's **scope creep**: an LLM asked "what's next?" on a loop will often
invent a next step rather than recognizing the request is already
answered. The fix was one line of prompt, not code — see
`SUPERVISOR_SYSTEM_PROMPT` (lines 79-95), specifically the `finish`
bullet telling it explicitly to stop the moment the literal request is
satisfied.

**Lesson for any future supervisor/router prompt you write:** explicitly
tell the model to stop once the original request is answered, and not to
perform delegations the request didn't ask for. Don't assume "finish
when done" is implicit — it isn't, and an LLM will happily keep being
"helpful" past the point the user actually wanted.

📺 [LangGraph Supervisor Agent Tutorial: Master Multi-Agent Orchestration](https://www.youtube.com/watch?v=rclPM7dcWMA) —
covers this exact loop-back-to-supervisor shape end to end.

---

**Checkpoint:** predict, then verify by running, what happens if you
feed Exercise 3 a request like *"Find office supplies vendors, then
create a PO for the best one for $2000"* — walk through in your head
which nodes fire, in what order, and why, before running it.
