# LangGraph Subgraphs — Study Notes

> Based on the official LangChain docs: https://docs.langchain.com/oss/python/langgraph/use-subgraphs
> This is an original explanation/summary, not a copy of the source page. For exact copy-paste snippets or the architecture diagram, visit the link above.

## What is a subgraph?

A subgraph is simply a compiled LangGraph graph that gets used as a single node inside a *different* (parent) graph. You reach for this pattern when you want to:

- Build multi-agent systems, where each agent is its own self-contained graph
- Reuse the same set of nodes across several parent graphs
- Let separate teams build independent pieces of a larger system — as long as everyone agrees on the input/output shape of each subgraph, nobody needs to see inside anyone else's implementation

## The two ways a parent and subgraph can talk to each other

The core design decision is: **do the parent graph and the subgraph share any state keys?**

### 1. Different (non-overlapping) state schemas → call it inside a node

If the subgraph's state doesn't overlap with the parent's state at all, you can't just drop the subgraph in as a node directly — you need a small wrapper function. That wrapper:

1. Takes the parent state
2. Builds the input dict the subgraph expects
3. Calls `subgraph.invoke(...)`
4. Takes the subgraph's output and maps it back into whatever shape the parent state needs

This is the pattern you'll use most in multi-agent setups where each agent should keep its own private conversation history rather than sharing one big state object.

```python
from typing_extensions import TypedDict
from langgraph.graph.state import StateGraph, START

class SubState(TypedDict):
    note: str

def sub_step(state: SubState):
    return {"note": "processed: " + state["note"]}

sub_builder = StateGraph(SubState)
sub_builder.add_node(sub_step)
sub_builder.add_edge(START, "sub_step")
sub_graph = sub_builder.compile()

class ParentState(TypedDict):
    text: str

def run_subgraph(state: ParentState):
    result = sub_graph.invoke({"note": state["text"]})
    return {"text": result["note"]}

parent = StateGraph(ParentState)
parent.add_node("delegate", run_subgraph)
parent.add_edge(START, "delegate")
graph = parent.compile()
```

This same wrapper approach also works for multiple nesting levels (parent → child → grandchild) — each layer just transforms state going down and translates results coming back up. None of the layers can see each other's private keys; only what's explicitly passed through the wrapper functions crosses a boundary.

### 2. Shared state keys → add it directly as a node

If the subgraph reads and writes the *same* keys the parent uses (a common example: everyone shares a `messages` list), you don't need any wrapper at all. You just compile the subgraph and pass it straight into `add_node`:

```python
class SharedState(TypedDict):
    text: str

def sub_step(state: SharedState):
    return {"text": "hi! " + state["text"]}

sub_builder = StateGraph(SharedState)
sub_builder.add_node(sub_step)
sub_builder.add_edge(START, "sub_step")
sub_graph = sub_builder.compile()

parent = StateGraph(SharedState)
parent.add_node("step_one", sub_graph)   # compiled subgraph passed directly
parent.add_edge(START, "step_one")
graph = parent.compile()
```

The subgraph reads from and writes to the parent's channels automatically — no translation layer needed.

## Persistence: what happens to subgraph state between calls?

When a subgraph is compiled, the `checkpointer` argument controls how much it remembers between invocations. Think of a support bot with a "billing" subagent — should it forget the customer between questions, or build context over the conversation? There are three modes:

| Mode                     | `checkpointer=` | What it means                                                                                                                     |
| ------------------------ | --------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Per-invocation (default) | `None`          | Starts fresh every call, but still inherits the parent's checkpointer so interrupts/durable execution work *within* a single call |
| Per-thread               | `True`          | State builds up across repeated calls on the same thread — like a subagent with ongoing memory                                    |
| Stateless                | `False`         | No checkpointing at all — behaves like a plain function call, no pause/resume, no crash recovery                                  |

**Per-invocation** is the right default for most multi-agent setups — e.g., a fruit-expert subagent that just answers one question at a time doesn't need to recall earlier questions.

**Per-thread** is for cases where a subagent genuinely needs multi-turn memory — a research assistant that accumulates context, or a coding assistant tracking which files it already touched. One catch: per-thread subgraphs can't be called in parallel safely, since concurrent calls would collide when writing to the same checkpoint namespace. If an LLM might call the same per-thread subagent tool twice at once, you need to explicitly prevent that (e.g., via a tool-call-limit style middleware, or by disabling parallel tool calls).

**Stateless** trades away recovery and pausing for simplicity/speed — fine for subgraphs that are truly one-shot, side-effect-free calls.

### Namespace isolation

When you have several *different* per-thread subgraphs (a fruit expert and a veggie expert, say), each needs its own storage space so their checkpoints don't clobber each other. If you call subgraphs inside a node function, LangGraph assigns namespaces based on call order — which means reordering calls can accidentally scramble which state loads where. The fix is to wrap each subagent in its own tiny `StateGraph` with a distinct node name, which gives it a stable namespace regardless of call order. Subgraphs added directly as nodes (the shared-state pattern above) already get automatic, name-based namespaces, so this workaround is only needed for the "call inside a node" pattern.

## Inspecting subgraph state

Once persistence is turned on, you can inspect what's happening inside a subgraph via `graph.get_state(config, subgraphs=True)`. Two important caveats:

- With stateless subgraphs (`checkpointer=False`), there's nothing to inspect — no checkpoints are written.
- LangGraph has to be able to **statically discover** the subgraph — meaning it was added as a node or invoked directly inside a node function. If a subgraph is buried inside a tool function (a common pattern for wrapping subagents as tools), its state isn't inspectable this way, though interrupts still bubble up to the top level regardless.

## Streaming subgraph output

By default, `graph.stream(...)` only shows you events from the parent graph. Pass `subgraphs=True` to also see events emitted from inside any nested subgraphs. Each streamed chunk carries a namespace (`ns`) tuple telling you which graph produced it — an empty tuple `()` means the top-level parent, while something like `("node_2:<task_id>",)` tells you it came from the subgraph running inside `node_2`. This lets you distinguish "the parent just finished a step" from "a nested subgraph just finished a step" when watching a live run.

## Quick decision guide

- **Do parent and subgraph share state keys?** Yes → add as a node directly. No → write a small wrapper and call `.invoke()` inside a node.
- **Does the subagent need to remember past calls on the same thread?** Yes → `checkpointer=True` (per-thread). No, but you still want interrupts/durable execution → leave the default (per-invocation). Don't need either → `checkpointer=False` (stateless).
- **Multiple different per-thread subagents?** Give each its own wrapped `StateGraph` with a unique node name so their checkpoint namespaces don't collide.

---
*For the official diagram, exact copy-paste code blocks, and full API reference tables, see the source page: https://docs.langchain.com/oss/python/langgraph/use-subgraphs*