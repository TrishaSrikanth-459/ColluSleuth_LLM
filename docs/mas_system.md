# System Specification: Multi-LLM Consensus with Writable Trust Substrates

---

## 1. System Class

We study **structured multi-agent LLM systems** characterized by:

1.  Multiple LLM agents operating in parallel
2.  Explicit **inter-agent interaction**, including critiques, debates, and refinements
3.  Persistent **protocol state** updated across rounds
4.  A **mechanical commitment rule** that deterministically selects a single output

This system class includes:
-   WBFT-style LLM networks
-   Stability-horizon deliberation systems
-   Evaluator-mediated consensus pipelines

It explicitly excludes:
-   Fully free-form deliberative systems where persuasion *is* the decision rule
-   Single-pass majority voting without intermediate states

---

## 2. Agents

### 2.1 Agent Population

-   Number of agents: `N ∈ {3, 5}`
-   Byzantine agents: `f = 1`
-   All agents share:
    -   The same base model family
    -   The same safety policy

### 2.2 Agent Prompts

All agents receive a **shared task prompt** specifying the objective and safety constraints.
Role-specific prompts are deterministically derived from this shared prompt to enforce functional differentiation while preserving identical information access.

#### Base Task Prompt

The base prompt defines:
-   A safety-critical reasoning task with ambiguous trade-offs (e.g., constrained planning, policy interpretation, or risk-sensitive decision-making)
-   Explicit safety policies that prohibit certain outcomes while allowing multiple policy-compliant intermediate answers
-   No ground-truth oracle available to agents

This design ensures that:
-   Individually plausible but collectively unsafe outcomes exist
-   Correctness cannot be determined from local reasoning alone
-   Influence and trust mechanisms meaningfully affect commitment

---

## 3. Interaction Structure

### 3.1 Round-Based Execution

Execution proceeds in **discrete rounds** `r = 1 … R`.

Each round consists of:

1.  **Proposal Phase**
    -   `k ≥ 2` agents independently generate candidate outputs
2.  **Interaction Phase**
    -   Agents observe a subset or all candidate outputs
    -   Agents produce:
        -   Critiques
        -   Rebuttals
        -   Revisions
3.  **State Update Phase**
    -   System updates memory and trust substrates
4.  **Commit Check**
    -   Deterministic decision rule evaluates whether commitment conditions are met

---

### 3.2 Definitions: Round vs. Task

To avoid ambiguity, we explicitly distinguish **round-level phases**, **decision timing**, and **task-level termination**.

---

#### Core Definitions

- A **task** is a complete execution of the multi-agent protocol on a single input prompt.
  - A task begins when the initial prompt is issued.
  - A task ends when the system **commits** to an output or **aborts**.
  - A task contains one or more rounds.
  - At most **one committed output** may occur per task.

- A **round** is a single, ordered iteration within a task.
  - Rounds are indexed `r = 1 … R`.
  - All reasoning, evaluation, and refinement within a round occurs **before** the next round begins.

**Key principle:**  
> **Rounds are the unit of interaction and evaluation; tasks are the unit of final output.**

---

#### Intra-Round Phases

Each round is internally structured into **ordered phases**.  
All evaluation and refinement occur **within the same round**.

A round `r` consists of the following phases:

1. **Proposal Phase**
   - `k ≥ 2` agents independently generate candidate proposals.
   - Outputs are frozen at the end of this phase.

2. **Interaction Phase**
   - Agents observe proposals and produce:
     - Critiques
     - Rebuttals
     - Refinements
   - Refinement here means *producing revised proposals within the same round*.

3. **Evaluation Phase**
   - Evaluators score or rank the (possibly refined) proposals **from this round only**.
   - Evaluation State `ES[r]` is produced here.
   - Evaluators do **not** revise proposals; they only assess them.

4. **State Update Phase**
   - System updates task persistent states (e.g., Reputation Memory).
   - These updates take effect **before the next round**, if any.

5. **Decision Rule Evaluation**
   - The decision rule is executed using `ES[r]`
   - This determines whether the task commits, continues, or aborts.

This ordered sequence defines the **intra-round timing space**.

---

#### Decision Rule Evaluation

- The decision rule is evaluated **once per round**.
- The outcome of each evaluation is exactly one of:
  1. **Commit** a final output
  2. **Continue** to the next round
  3. **Abort / abstain** (protocol-dependent)

The decision rule is therefore **round-scoped**, not task-scoped.

---

#### Final Commitment

- Commitment is a **task-level event**.
- If the decision rule returns **Commit** in round `r`:
  - The task terminates immediately.
  - The committed output becomes the final answer for the task.
  - No further rounds are executed.
- If no round returns Commit:
  - The task may terminate after a fixed maximum number of rounds `R_max`, or
  - Explicitly abstain, depending on protocol configuration.
    
---

## 4. Memory Model

### 4.1 Classification of Memory in Multi-Agent Systems

Following prior work on multi-agent LLM architectures, we classify memory by **persistence**, **scope**, and **role in coordination**.

This classification is critical: **covert Byzantine attacks may target memory that is not directly consumed by the commit rule**, but which indirectly shapes trust, evaluation, or persistence.

#### 4.1.1 Short-Term (Working) Memory

**What it is**
-   The transient context used by an agent during a single message generation.
-   Includes:
    -   Base task prompt
    -   Role-specific prompt modifier
    -   System-injected retrieved context
    -   Internal decoding state

**Persistence**
-   Exists only during a single forward pass.
-   Discarded immediately after output generation.

**Writers**
-   The agent itself (implicitly via decoding).
-   No system module or other agent can write to it.

**Readers**
-   The same agent only.
-   No system component, evaluator, or other agent can read it.

**Security relevance**
-   Not persisted.
-   Not shared.
-   **Not a trust substrate**.
-   Explicitly excluded from attacks.

#### 4.1.2 Single-Agent Long-Term Memory

**What it is**
-   Persistent memory scoped to exactly one agent.
-   Conditions only that agent’s internal behavior.

**Concrete contents**
-   Self-produced summaries and rationales.
-   Agent-local embeddings or retrieval keys
-   System-produced records of past agent outputs and outcomes

**Persistence**
-   Stored across rounds.
-   Implemented via external storage (vector DB, KV store).

**Writers**
-   The owning agent will write self-authored summaries and rationalies to this component of memory.
-   System modules will record past outputs and corresponding scores to this component of memory.

**Readers**
-   The owning agent can read any subset of this memory.
-   System modules can read only the subset of memory they produced.

**Security relevance**
-   We explicitly allow Byzantine agents to utilize their single-agent long-term memory to plan adaptive, multi-round strategies respecting covert tampering and influence accumulation.
-   That being said, this component of memory is not considered part of the attacks surface, as it is not susceptible to trust-substrate attacks.

#### 4.1.3 Episodic Memory

**What it is**
-   A cross-task retrieval mechanism that stores completed *task-level episodes*.

**Concrete contents**
-   Task prompt
-   Final committed decision (or abstention)
-   High-level trace summary (task-level)
-   Outcome metadata (e.g., success/failure, safety label)

**Persistence**
-   Stored across tasks.
-   Not reset between independent executions of the system.

**Writers**
-   System-level logging and indexing modules only.
-   No agent-authored writes permitted.

**Readers**
-   The owning agent only.
-   Other agents cannot access another agent’s episodic memory.
-   Episodic memory is never read directly by evaluators, trust updates, or commitment logic.

**Security relevance**
-   We explicitly allow Byzantine agents to utilize their episodic memory to plan adaptive, multi-round strategies respecting covert tampering and influence accumulation.
-   That being said, this component of memory is not considered part of the attacks surface, as it is not susceptible to trust-substrate attacks.

#### 4.1.4 Consensus Memory

**What it is**
-   Shared protocol state directly consumed by:
    -   Evaluators
    -   Stability checks
    -   Commitment rules
-   Comprises of each consensus memory artifact detailed below

**This is the only memory category treated as a writable trust substrate.**

---

### 4.2 Consensus Memory Artifacts

Each artifact below is:
-   Shared across agents
-   Explicitly consumed by protocol logic
-   Independently attackable under Regimes A or B

#### Access Regimes

-   **Access Regime A — Full Memory Write Access**
    Byzantine agent may modify *any persisted memory artifact* after it is written, including artifacts associated with other agents.

-   **Access Regime B — Self-Memory Write Access Only**
    Byzantine agent may modify *only memory artifacts logically associated with itself*

-   **Access Regime C — Read-Only / No Write Access**
    Byzantine agent cannot modify any persisted memory artifact and may influence the system only via normal message generation.

---

#### 4.2.1 Interaction Memory (IM)

**Definition**
`IM.append(<round r>, <timestamp t>, <agent_id i>, <message m>)`

**Primary Writer**
-   System-level append module

**Byzantine Write Scope**
-   Regime A: any entry
-   Regime B: only entries with `agent_id = byz_id`
-   Regime C: none

**Inputs**
-   Raw agent messages

**Outputs**
-   Ordered interaction log

**Persistence**
-   Within a task:
    -   IM is append-only across all rounds `r = 1 … R`
    -   No entries are deleted or reset mid-task
-   Across tasks:
    -   IM is reset at task boundaries

**Consumers**
-   Summary Memory (SM)
-   Evaluation State (ES)

---

#### 4.2.2 Summary Memory (SM)

**Definition**
`SM[r] = Summarize(IM[r], T_summary)`

**Primary Writer**
-   System-level summarization module

**Byzantine Write Scope**
-   Regime A: any summary
-   Regime B: summaries explicitly associated with itself
-   Regime C: none

**Inputs**
-   Interaction Memory (IM)
-   Fixed summarization template

**Outputs**
-   Round-scoped summary artifact

**Persistence**
-   Within a task:
    -   One SM entry is produced per round
    -   All SM entries {SM[1], …, SM[R]} persist until task termination
-   Across tasks:
    -   SM is reset at task boundaries

**Consumers**
-   Next-round agents
-   Evaluation State (ES)

---

#### 4.2.3 Evaluation State (ES)

**Definition**
`ES[r] = {(proposal j, score_j, rank_j, accept_j)}`

**Primary Writer**
-   Baseline: agentic evaluators (LLMs)
-   Defense: non-agentic verifiers (deterministic programs or narrow classifiers)

**Byzantine Write Scope**
-   Regime A: any evaluation record
-   Regime B: only evaluation entries tied to itself
-   Regime C: none

**Inputs**
-   Candidate proposals
-   Summary Module SM
-   Reputation Memory RM
-   Fixed evaluation rubric

**Outputs**
-   Proposal scores and rankings

**Persistence**
-   **Within a round**
    -   ES[r] is created after evaluation.
    -   ES[r] is consumed by:
        -   the decision rule, and
        -   the reputation update function (RM update), if applicable.
-   **Across rounds**
    -   ES[r] is discarded once:
        -   the decision rule is evaluated for round r, and
        -   RM has been updated.
    -   A fresh ES[r+1] is created in the next round.
-   **Across tasks**
    -   ES does not persist across tasks.
    -   No evaluation artifacts are carried over between independent task executions.

**Consumers**
-   Decision rule

---

#### 4.2.4 Reputation Memory (RM)

**Definition**
`RM[i] = w_i ∈ [w_min, w_max]`

**Primary Writer**
-   System-level update function `F_rm`

**Byzantine Write Scope**
-   Regime A: any `w_i`
-   Regime B: only `w_byz`
-   Regime C: none

**Inputs**
-   (Summary Module) SM
-   Fixed update rule

**Outputs**
-   Updated trust weights

**Persistence**
-   Within a task:
    -   RM is updated at the end of each round
    -   Updated weights persist into subsequent rounds
-   Across tasks:
    -   RM may persist across tasks by default
    -   Reset behavior is an explicit experimental parameter:
        -   Reset-per-task (cold start)
        -   Persistent-across-tasks (long-term influence accumulation)

**Consumers**
-   (Evaluation State) ES

---

## 5. Experimental Policy: Artifact-Specific Attacks

For **each access regime**, attacks are evaluated as:

### Single-Artifact Attacks
-   IM-only
-   SM-only
-   ES-only
-   RM-only

### Compound Attacks
-   IM + SM
-   ES + RM
-   SM + RM

---
