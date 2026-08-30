# Module 4: Swarm intelligence

Read [[Home]], [[Module 1 Hierarchical Delegation]],
[[Module 2 Handoff Patterns]], and [[Module 3 Specialist Network]]
first. Have the repo's
[04-swarm-intelligence/](https://github.com/psppravin28-dev/multi-agent-orchestration/tree/main/04-swarm-intelligence)
folder open alongside this, with the procurement app running.

## What's actually new here

Every graph in Modules 1-3 ran **one node at a time** — even Module 1's
loop and Module 3's unbounded tool-calling never had two things
executing simultaneously. Swarm intelligence starts from a different
premise: run *many* independent workers concurrently on either many
pieces of the same problem (Exercise 1) or many perspectives on the
*same* piece of data (Exercise 2), then combine what they each found.
No single worker's output is authoritative by itself — only the
combining step is.

## Exercise 1 — parallel fan-out over data

Open [exercise1_parallel_fanout.py](https://github.com/psppravin28-dev/multi-agent-orchestration/blob/main/04-swarm-intelligence/exercise1_parallel_fanout.py).
Instead of a supervisor picking one vendor to check (the Module 1
shape), *every* vendor in a category gets scored at once.

1. [`scores: Annotated[list[dict], operator.add]`](https://github.com/psppravin28-dev/multi-agent-orchestration/blob/main/04-swarm-intelligence/exercise1_parallel_fanout.py#L36-L43) —
   the same reducer pattern as Module 1 Exercise 3's `history` field, for
   the same reason: several nodes are each going to return
   `{"scores": [one_entry]}`, and without `operator.add` each return
   would overwrite the last instead of accumulating.
2. [`fan_out_to_scorers`](https://github.com/psppravin28-dev/multi-agent-orchestration/blob/main/04-swarm-intelligence/exercise1_parallel_fanout.py#L60-L64) —
   the new primitive. It's used as a conditional edge, but instead of
   returning one node-name string (Module 1's router) or one `Command`
   (Module 2), it returns a **list of `Send` objects** — one per vendor
   found. Each `Send("score_vendor", {...})` is its own independent
   invocation of `score_vendor`, with its own private payload, and
   LangGraph runs all of them concurrently.
3. [`score_vendor`](https://github.com/psppravin28-dev/multi-agent-orchestration/blob/main/04-swarm-intelligence/exercise1_parallel_fanout.py#L67-L82) —
   notice its parameter is `payload: ScoreVendorInput`, **not** the graph's
   `SwarmState`. A `Send`-invoked node receives exactly what its `Send`
   call handed it, not the shared state — each parallel branch is
   genuinely isolated. Also notice the disqualification logic at
   [lines 75-77](https://github.com/psppravin28-dev/multi-agent-orchestration/blob/main/04-swarm-intelligence/exercise1_parallel_fanout.py#L75-L77):
   a vendor that isn't cleared to spend gets `score = -1.0` regardless of
   rating, so a highly-rated but non-compliant vendor can never win.
4. [The wiring](https://github.com/psppravin28-dev/multi-agent-orchestration/blob/main/04-swarm-intelligence/exercise1_parallel_fanout.py#L90-L98) —
   `add_conditional_edges("find_candidates", fan_out_to_scorers, ["score_vendor"])`.
   That third argument (a list of possible destination names) exists
   purely so LangGraph can still draw a complete graph diagram even
   though the actual branch *count* is unknown until runtime.
5. `aggregate` (lines 85-87) only runs once every fanned-out
   `score_vendor` branch has finished — LangGraph waits for all of them
   before a node with a converging edge runs, the same join behavior
   Module 4 Exercise 2 relies on for its three static branches.

**Verified behavior:** for `category="laptops", amount_usd=15000`, all
four laptop vendors were scored concurrently. Dell Business, Lenovo, and
HP Enterprise scored their own rating (4.6 / 4.4 / 4.2). "Shady
Supplies Ltd" — on the sanctions list — scored **-1.0** despite a 3.9
rating and was correctly excluded from winning; Dell Business won.

📺 [Map-Reduce with the Send() API in LangGraph](https://www.youtube.com/watch?v=5iYV0q6eKbM)
📺 [LangGraph Fan-Out & Fan-In Explained | Parallel Workflows Simplified](https://www.youtube.com/watch?v=h1RWITSgySo)

## Exercise 2 — consensus review (independent votes, majority rules)

Open [exercise2_consensus_review.py](https://github.com/psppravin28-dev/multi-agent-orchestration/blob/main/04-swarm-intelligence/exercise2_consensus_review.py).
Exercise 1 fanned out over *data* (one vendor per branch, all doing the
same kind of check). This one fans out over *perspective*: three
reviewers look at the exact same purchase request, each caring about
one different thing, each reaching its own verdict with zero visibility
into what the other two decided.

1. Three reviewer nodes —
   [`risk_reviewer`](https://github.com/psppravin28-dev/multi-agent-orchestration/blob/main/04-swarm-intelligence/exercise2_consensus_review.py#L55-L68) (compliance/sanctions only),
   [`cost_reviewer`](https://github.com/psppravin28-dev/multi-agent-orchestration/blob/main/04-swarm-intelligence/exercise2_consensus_review.py#L71-L85) (contracted liability cap only),
   [`relationship_reviewer`](https://github.com/psppravin28-dev/multi-agent-orchestration/blob/main/04-swarm-intelligence/exercise2_consensus_review.py#L88-L98) (rating/sanctions only) —
   each hits a *different* API endpoint, each has a narrow one-sentence
   system prompt, and each returns the same shaped `Vote` via structured
   output (Module 1's mechanism, reused here for a different purpose:
   forcing a clean `approve`/`reject` instead of a paragraph).
2. [The wiring at lines 138-143](https://github.com/psppravin28-dev/multi-agent-orchestration/blob/main/04-swarm-intelligence/exercise2_consensus_review.py#L138-L143) —
   unlike Exercise 1's dynamic `Send`-based fan-out, this is a **static**
   fan-out: three plain `add_edge(START, ...)` calls, known at graph-build
   time because the reviewer count never varies. Both are "parallel," but
   only Exercise 1 needed `Send` — use it when the branch *count* is
   unknown ahead of time, plain edges when it isn't.
3. [`tally`](https://github.com/psppravin28-dev/multi-agent-orchestration/blob/main/04-swarm-intelligence/exercise2_consensus_review.py#L101-L112) —
   counts approvals, and — like Module 2's nodes — returns a `Command`
   to route itself: `goto="po_generation"` on a majority, `goto=END`
   otherwise. This is Module 2's mechanism reappearing for a different
   job: not a peer handing off work, but a join point turning N votes
   into one routing decision.

**The mental model that matters:** in Module 1, one supervisor's
judgment *was* the decision. In Module 3, one orchestrator's tool
choices *were* the decision. Here, no individual reviewer's vote is
ever authoritative — the request only proceeds if a majority agrees,
which means the group can catch and overrule any single reviewer's
mistake or overly narrow framing.

**Verified behavior** (three real runs, seeded data):
- Vendor 1, $9,000 — all three reviewers approved unanimously (3/3);
  a PO was issued.
- Vendor 6 ("Shady Supplies Ltd," on the sanctions list), $5,000 — `cost`
  approved (the amount was within its contract cap, all that reviewer
  looks at), but `risk` and `relationship` both rejected on sanctions
  grounds — 1/3, consensus REJECT, no PO created.
- Vendor 3, $20,000, after giving it a $10,000 liability cap — a genuine
  **2-1 split**: `cost` rejected (over its own cap), but `risk` and
  `relationship` approved (compliance cleared it, rating was fine) — 2/3,
  majority still APPROVEd and a PO was issued despite one dissenting
  reviewer.

That middle case is the one worth sitting with: `cost_reviewer` was
*correct* that $20,000 exceeded the $10,000 cap it was told to check —
and got outvoted anyway, because a liability cap alone wasn't this
system's bar for rejecting the whole request. Consensus doesn't mean
"everyone was right"; it means the majority's narrower framing won.

📖 [Patterns for Democratic Multi-Agent AI: Voting-Based Council — Part 2, Implementation](https://medium.com/@edoardo.schepis/patterns-for-democratic-multi-agent-ai-voting-based-council-part-2-implementation-2992c3e7c2be)

---

**Checkpoint:** the 2-1 split case above shipped a PO despite one
reviewer's correct objection. Design a change to `tally` (still using
`Command`, no new graph shape needed) that would make it require
**unanimous** approval instead of a majority — then think about which of
this repo's three example requests would come out differently. Is
unanimous strictly "safer," or does it trade one failure mode for
another (a single overcautious reviewer permanently blocking a
legitimate request)?

---
⬅ Back to [[Home]]
