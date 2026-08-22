# multi-agent-orchestration

Learning repo for multi-agent orchestration patterns (hierarchical
delegation, handoff, specialist network, swarm), built hands-on against a
real procurement domain.

## Repo structure — read this first

```
prerequisites/           Delivered code -- not the learning focus.
  procurement-app/        Real FastAPI + SQLite backend (vendors, contracts,
                           compliance, purchase orders). System of record
                           the agents call. See its own README for setup.

01-hierarchical-delegation/   <- CORE LEARNING. Hand-written, hands-on. (complete)
02-handoff-patterns/          <- (complete)
03-specialist-network/        <- (complete)
04-swarm-intelligence/        <- (complete)
learning-path/                 <- Concept-by-concept notes, written while working through
                                   the modules above -- start at learning-path/README.md.
wiki/                           <- Same notes, reformatted for the GitHub Wiki (see below).
```

**The split is deliberate.** Everything under `prerequisites/` is
infrastructure you don't need to hand-build to learn agentic AI — it's
there so the numbered modules have something real to call instead of
mocked functions. Everything under a numbered module folder is the actual
hands-on track: written exercise-by-exercise, reviewed, committed piece by
piece — that's where the mastery is meant to happen.

## Python environments

Two separate venvs, not one shared across the repo (let alone across
everything in `agentic-ai\`) — the procurement app is a service with its
own dependency lifecycle, the numbered modules are a learning track that
shares one growing dependency set. They never share code, only an HTTP
boundary, so there's no reason to share a venv either.

```
.venv\                          learning track — shared by 01-, 02-, 03-, 04-
prerequisites\procurement-app\.venv\   its own, separate
```

**Use `uv`, not plain pip+venv.** Two fully isolated venvs still share one
global package cache (hardlinked, not copied) — measured ~190MB with plain
pip down to ~88MB real disk with `uv`, confirmed via matching inodes for
shared packages like `httpx`. Same isolation, no duplication cost.

```powershell
irm https://astral.sh/uv/install.ps1 | iex     # one-time install

# procurement app
cd prerequisites\procurement-app
uv venv
uv pip install -r requirements.txt

# learning track (from repo root)
uv venv
uv pip install -r requirements.txt
```

Activation is unchanged either way: `.venv\Scripts\Activate.ps1`.

**Same-drive caveat:** hardlinks only work within one physical drive. If
`uv cache dir` resolves outside `P:\`, force it there so the savings
actually apply: `$env:UV_CACHE_DIR = "P:\uv-cache"`.

If `Activate.ps1` fails with an execution-policy error, run once per
machine: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

## Getting started

```powershell
# 1. Start the procurement app (leave running in its own terminal)
cd prerequisites\procurement-app
pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --reload

# 2. In another terminal, install once, then work through any module
pip install -r requirements.txt
cp .env.example .env   # set OPENAI_API_KEY -- needed from Module 1 Exercise 2 onward

cd 01-hierarchical-delegation
python exercise1_warmup.py
python exercise2_supervisor_routing.py
python exercise3_supervisor_loop.py

cd ../02-handoff-patterns
python exercise1_command_handoff.py
python exercise2_peer_handoff_chain.py

cd ../03-specialist-network
python exercise1_agents_as_tools.py
python exercise2_specialist_consults_specialist.py

cd ../04-swarm-intelligence
python exercise1_parallel_fanout.py
python exercise2_consensus_review.py
```

## Progress

- [x] Procurement app (prerequisite) — built, tested, verified live
- [x] Module 1: Hierarchical delegation — complete
  - [x] Exercise 1: LangGraph mechanics warm-up (fixed pipeline, no LLM)
  - [x] Exercise 2: Supervisor-routed delegation (LLM picks one specialist via `add_conditional_edges`)
  - [x] Exercise 3: Supervisor loop (specialists report back to the supervisor, which chains
    multiple delegations or finishes)
- [x] Module 2: Handoff patterns — complete
  - [x] Exercise 1: `Command` handoff mechanics warm-up (node decides its own destination,
    replacing the separate router function from Module 1)
  - [x] Exercise 2: Peer handoff chain (`contract_review` hands off directly to `compliance` for
    large contracts, with no central node deciding on its behalf)
- [x] Module 3: Specialist network — complete
  - [x] Exercise 1: Agents-as-tools mechanics warm-up (four specialists bound as native LLM tools
    to one orchestrator; the model's own tool-calling loop does the routing)
  - [x] Exercise 2: Specialist consults specialist (`generate_purchase_order` is itself a small
    agent that calls `check_compliance_policy` internally, invisibly to the top-level orchestrator)
- [x] Module 4: Swarm intelligence — complete
  - [x] Exercise 1: Parallel fan-out (`Send` scores every vendor in a category concurrently, then
    an aggregator picks the best)
  - [x] Exercise 2: Consensus review (three independent reviewer personas vote in parallel; a
    purchase order only proceeds on majority approval)

The four specialist roles (`vendor_sourcing`, `contract_review`, `compliance`, `po_generation`)
are the same across Modules 2-4 -- only the orchestration topology around them changes: graph
edges (Module 1) -> direct handoffs (Module 2) -> LLM-native tool calls (Module 3) -> parallel
fan-out/consensus (Module 4). Comparing those topologies over one fixed set of capabilities is
the actual point of the track.
