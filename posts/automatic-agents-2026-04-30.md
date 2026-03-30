# ReThink Product Demo: Automatic

Traditional issue tracking is dead. Jira, Linear, Asana—they were built for a fundamental constraint that no longer exists: human-to-human handoffs.

At the same time, the current AI landscape is fracturing. We are building "agent silos," where every SaaS application has its own isolated, context-starved agent bolted onto the side.

The solution isn't another copilot. The solution is a unified "context bus"—a shared environment where humans and AI collaborate on atomic tasks inside a chat-first interface. This is what we are building with **Automatic**, the latest addition to the ReThink product suite.

## Key Architectural Pillars

### 1. Atomic Tasks Over "Issues"
An "issue" or a "ticket" is too bulky and vague for an AI. The fundamental unit of work must shift to **atomic tasks**. These are highly scoped, executable nodes with a strict definition of done, perfectly sized for an LLM's context window. Instead of throwing a vague feature request at a model, we decompose it into executable atomic units.

### 2. The "Thread-as-a-Ticket" Interface
Every task or epic is a living chat thread. To prevent these threads from devolving into chaotic noise, we split them into two distinct streams:

*   **`#discuss` (The What & Why):** This is for high-level scoping. Human PMs and "product agents" debate requirements, refine the product spec, and automatically spawn atomic tasks directly from the conversation.
*   **`#dev` (The How):** This is the execution layer. Human engineers and "coding agents" collaborate here. Agents don't just paste code snippets; they drop interactive code diffs directly into the chat for humans to approve, reject, or tweak.

### 3. The Dependency Digraph (DAG)
Tasks are not a flat list; they are mapped as a Directed Acyclic Graph (DAG). Agents natively understand dependencies (e.g., Task C cannot start until Task A and Task B are merged).

This enables **cascading execution**. Once a human approves and merges the database schema update (Task A), the system automatically wakes up the API agent (Task B), feeding it the freshly merged code as context to immediately begin building the endpoints.

### 4. Implementation Forking
AI compute is cheap. Developer time is expensive. Because of this inversion, you can assign multiple coding agents to the exact same task using completely different technical approaches.

*Example:* Branch A's agent writes a pure SQL fix; Branch B's agent implements a Redis caching layer.

The human engineer simply reviews the benchmarks and diffs for both approaches directly in the `#dev` thread, clicks "Merge" on the winner, and instantly discards the loser.

### 5. Humans as Editors, Not Writers
The endgame of agentic coding isn't replacing developers; it's shifting their role. The system elevates the developer from writing boilerplate code to managing intent, reviewing logic, and orchestrating high-level architectural decisions.

![Task Decomposition](/assets/task_decomp.png)
![Task Lifecycle](/assets/life_cycle.png)
