# Learning path: multi-agent orchestration, ground up

Notes from working through this repo module by module, written for
someone (future you, or a peer) who wants the concepts explained from
scratch rather than just the code. One file per module; read them in
order, alongside the actual exercise files.

## The shape of the whole journey

All four modules wire together the **same four specialists** (search
vendors, check contract terms, check compliance, create a purchase
order — see the root [README](../README.md)'s closing note). Only *how
they're coordinated* changes module to module:

| Module | Question it answers | Mechanism |
|---|---|---|
| [1. Hierarchical delegation](01-hierarchical-delegation.md) | One boss decides who does what | `add_conditional_edges`, then a `Command` loop |
| [2. Handoff patterns](02-handoff-patterns.md) | Can an agent pass control directly to another, no boss involved? | `Command(goto=...)` between peers |
| [3. Specialist network](03-specialist-network.md) | What if the LLM itself picks which tool to call? | native tool-calling (`bind_tools`) |
| [4. Swarm intelligence](04-swarm-intelligence.md) | What if many agents work at once and vote? | `Send` fan-out + consensus |

Once you've read all four modules, see
[comparison.md](comparison.md) for pros/cons of all four modules and a
reasoned recommendation on which pattern(s) actually belong in
production.

## Vocabulary (assume nothing is known going in)

- **LLM** — a model (this repo uses OpenAI's `gpt-4o-mini`) that takes
  text in and produces text (or, as you'll see, structured data) out. On
  its own it does nothing — no memory, no ability to call an API, no
  loop. It only reasons about what it's handed *this one time*.
- **Agent** — code that puts an LLM in a loop and gives it something to
  actually *do* — call a real function, read the result, decide again.
  The LLM supplies judgment; the surrounding Python supplies hands.
- **Multi-agent system** — instead of one do-everything agent, work is
  split across several focused "specialist" agents, each good at one
  narrow job.
- **Orchestration** — the part that decides who runs, in what order, and
  how information passes between them. This is the entire subject of all
  four modules.
- **LangGraph** — the library everything here is built in. It models a
  workflow as a graph:
  - **State** — a shared dict (defined as a `TypedDict`) that flows
    through every step. Think of it as a clipboard every node can read
    and write.
  - **Node** — an ordinary Python function: takes the current state,
    returns a dict of updates to it.
  - **Edge** — "after this node, run that node." Either fixed
    (`add_edge`) or decided while the graph is running.
  - **START / END** — where the graph begins and where it's allowed to
    stop.
  - **`graph.compile()`** — turns node/edge definitions into something
    runnable.
  - **`app_graph.invoke(initial_state)`** — actually runs it, start to
    finish, once.
- **Structured output** (`.with_structured_output(SomeModel)`) — forces
  the LLM to hand back data matching a schema (a Pydantic model) instead
  of loose text, so code can reliably read `decision.route` rather than
  parsing sentences.
- **Tool calling / function calling** — a different way an LLM can act:
  instead of returning a schema the caller invokes itself, the LLM is
  given a list of Python functions ("tools") with descriptions, and it
  decides which one(s) to call and with what arguments. Module 3 is
  built entirely on this.

## General video resources

- [AI Agents for Beginners — full course (Microsoft)](https://www.youtube.com/watch?v=OhI005_aJkA) —
  what an "agent" is before any framework enters the picture.
- [LangGraph Deep Dive — State, Nodes, Edges & Agents Explained Clearly](https://www.youtube.com/watch?v=GE7mqOhAj_o) —
  if state/node/edge still feels abstract after reading the code.
