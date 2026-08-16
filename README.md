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
