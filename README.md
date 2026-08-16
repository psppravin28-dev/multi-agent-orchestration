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

01-hierarchical-delegation/   <- CORE LEARNING. Hand-written, hands-on.
02-handoff-patterns/          <- (not started yet)
03-specialist-network/        <- (not started yet)
04-swarm-intelligence/        <- (not started yet)
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

# 2. In another terminal, work through the current module
cd 01-hierarchical-delegation
pip install langgraph httpx
python exercise1_warmup.py
```

## Progress

- [x] Procurement app (prerequisite) — built, tested, verified live
- [ ] Module 1: Hierarchical delegation — in progress (Exercise 1: LangGraph mechanics warm-up)
- [ ] Module 2: Handoff patterns
- [ ] Module 3: Specialist network
- [ ] Module 4: Swarm intelligence
