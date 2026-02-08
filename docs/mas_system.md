# System Specification: Multi-LLM Consensus with Writable Trust Substrates

---

## 1. System Class

We study **structured multi-agent LLM systems** characterized by:

1. Multiple LLM agents operating in parallel  
2. Explicit **inter-agent interaction**, including critiques, debates, and refinements  
3. Persistent **protocol state** updated across rounds  
4. A **mechanical commitment rule** that deterministically selects a single output  

This system class includes:
- WBFT-style LLM networks  
- Stability-horizon deliberation systems  
- Evaluator-mediated consensus pipelines  

It explicitly excludes:
- Fully free-form deliberative systems where persuasion *is* the decision rule  
- Single-pass majority voting without intermediate states  

---

## 2. Agents

### 2.1 Agent Population

- Number of agents: `N ∈ {3, 5}`  
- Byzantine agents: `f = 1`  
- All agents share:
  - The same base model family  
  - The same safety policy  

---

### 2.2 Agent Prompts

All agents receive a **shared task prompt** specifying the objective and safety constraints.  
Role-specific prompts are deterministically derived from this shared prompt to enforce functional differentiation while preserving identical information access.

#### Base Task Prompt

The base prompt defines:
- A safety-critical reasoning task with ambiguous trade-offs (e.g., constrained planning, policy interpretation, or risk-sensitive decision-making)
- Explicit safety policies that prohibit certain outcomes while allowing multiple policy-compliant intermediate answers
- No ground-truth oracle available to agents

This design ensures that:
- Individually plausible but collectively unsafe outcomes exist  
- Correctness cannot be determined from local reasoning alone  
- Influence and trust mechanisms meaningfully affect commitment  

---

## 3. Interaction Structure

### 3.1 Round-Based Execution

Execution proceeds in **discrete rounds** `r = 1 … R`.

Each round consists of:

1. **Proposal Phase**  
   - `k ≥ 2` agents independently generate candidate outputs `o_i^r`

2. **Interaction Phase**  
   - Agents observe a subset or all `{o_j^r}`
   - Agents produce:
     - Critiques
     - Rebuttals
     - Revisions

3. **State Update Phase**  
   - System updates memory and trust substrates

4. **Commit Check**  
   - Deterministic decision rule evaluates whether commitment conditions are met

---

## 4. Memory Model

### 4.1 Classification of Memory in Multi-Agent Systems

Following prior work on multi-agent LLM architectures, we classify memory by **persistence**, **scope**, and **role in coordination**.

This classification is critical: **covert Byzantine attacks may target memory that is not directly consumed by the commit rule**, but which indirectly shapes trust, evaluation, or persistence.

#### 4.1.1 Short-Term (Working) Memory
- Immediate, transient memory within an agent’s forward pass  
- Exists only during a single interaction or round  
- Not persisted and not directly attackable  
- Included for completeness; **not a trust substrate**

#### 4.1.2 Single-Agent Long-Term Memory
- Persistent memory scoped to an individual agent  
- Examples:
  - Agent-specific summaries of prior rounds
  - Self-associated reputation metadata
  - Cached justifications, rationales, or embeddings
- Typically stored in external storage (e.g., vector DB, KV store)

**Security relevance**:
- Primary target in **Access Regime B**
- Often implicitly assumed benign
- Enables covert influence accumulation without cross-agent tampering

#### 4.1.3 Episodic Memory
- Memory of past task episodes or interaction histories
- Used to condition behavior on “similar past cases”
- May be:
  - Agent-scoped → treated as **single-agent memory**
  - Shared → treated as **consensus memory**

#### 4.1.4 Consensus Memory
- Shared protocol state consumed by evaluation, voting, or commitment
- Includes:
  - Interaction summaries
  - Evaluation outputs
  - Trust / reputation scores
- Central target of **trust-substrate manipulation attacks**

---

## 4.2 Memory Components and Attack Granularity

The system maintains **four concrete memory artifacts**.  
Each artifact is explicitly parameterized by:
1. **Who can write to it**, and  
2. **Which access regime permits that write**

We do **not** assume that write access to one artifact implies write access to others.

---

## Access Regimes

- **Access Regime A — Full Memory Write Access**  
  Byzantine agent may modify *any persisted memory artifact* after it is written, including artifacts associated with other agents.

- **Access Regime B — Self-Memory Write Access Only**  
  Byzantine agent may modify *only memory artifacts logically associated with itself*  

- **Access Regime C — Read-Only / No Write Access**  
  Byzantine agent cannot modify any persisted memory artifact and may influence the system only via normal message generation.

---

## Memory Artifacts

Each artifact is independently attackable under Regimes A or B.

---

### 4.2.1 Interaction Memory (IM)

**Definition**
IM.append(<round r>, <timestamp t>, <agent_id i>, <message m>)


**Primary Writer**
- System-level append module

**Byzantine Write Scope**
- Regime A: any entry
- Regime B: only entries with `agent_id = byz_id`
- Regime C: none

**Inputs**
- Raw agent messages

**Outputs**
- Ordered interaction log

**Consumers**
- Summary Memory (SM)
- Evaluation State (ES)

---

### 4.2.2 Summary Memory (SM)

**Definition**
SM[r] = Summarize(IM[r], T_summary)


**Primary Writer**
- System-level summarization module

**Byzantine Write Scope**
- Regime A: any summary
- Regime B: summaries explicitly associated with itself
- Regime C: none

**Inputs**
- Interaction Memory
- Fixed summarization template

**Outputs**
- Round-scoped summary artifact

**Consumers**
- Next-round agents
- ES

---

### 4.2.3 Evaluation State (ES)

**Definition**
ES[r] = {(proposal j, score_j, rank_j, accept_j)}


**Primary Writer**
- Baseline: agentic evaluators (LLMs)
- Defense: non-agentic verifiers (deterministic programs or narrow classifiers)

**Byzantine Write Scope**
- Regime A: any evaluation record
- Regime B: only evaluation entries tied to itself
- Regime C: none

**Inputs**
- Candidate proposals
- Summary Memory
- Reputation Memory
- Fixed evaluation rubric

**Outputs**
- Proposal scores and rankings

**Consumers**
- Decision rule
- RM

---

### 4.2.4 Reputation Memory (RM)

**Definition**
RM[i] = w_i ∈ [w_min, w_max]


**Primary Writer**
- System-level update function `F_rm`

**Byzantine Write Scope**
- Regime A: any `w_i`
- Regime B: only `w_byz`
- Regime C: none

**Inputs**
- SM
- Fixed update rule

**Outputs**
- Updated trust weights

**Consumers**
- ES

---

## 6. Experimental Policy: Artifact-Specific Attacks

For **each access regime**, attacks are evaluated as:

### Single-Artifact Attacks
- IM-only
- SM-only
- ES-only
- RM-only

### Compound Attacks
- IM + SM
- ES + RM
- SM + RM
  
---

## 7. Summary

This specification:
- Preserves the full original proposal structure
- Explicitly incorporates **single-agent memory**, **episodic memory**, and **consensus memory**
- Precisely aligns memory artifacts with **access regimes**
- Avoids over-abstraction or protocol collapse
- Supports clean attribution of failures to specific trust substrates

This completes a **fully specified, literature-aligned, and experimentally separable system definition** for studying covert trust-substrate manipulation in multi-LLM consensus systems.
