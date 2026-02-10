# consensus_system.md
**Consensus-Mechanism Instantiations (Locked Experimental Protocol Layer)**

This file defines the **final, executable consensus protocols** used in experiments.
It assumes the global system model, memory taxonomy, and access regimes are defined elsewhere.
Nothing in this file introduces new memory artifacts or adaptive protocol behavior.

---

## 0. Shared Assumptions Across All Families

### 0.1 Intra-Round Phase Ordering (Authoritative)

Each round `r` executes the following **fixed, linear sequence**:

1. **Proposal Phase**
2. **Interaction / Refinement Phase**
3. **Evaluation Phase**
4. **State Update Phase**
5. **Decision Rule Evaluation**

There is **no branching or overlap** between phases.

**Key invariant**
- All memory writes (IM, SM, ES, RM) occur **before** the decision rule.
- The decision rule is **read-only** over frozen state.

---

### 0.2 Frozen Objects Consumed by Decision Logic

At the end of **State Update Phase** in round `r`, the following objects are frozen:

- **Proposal set**  
  `P_r` — final proposals produced in round `r`

- **Evaluation state**  
  `ES[r]` — evaluator outputs over `P_r` (if evaluators exist in the family)

- **Trust state**  
  `RM` — post-update trust weights for round `r` (if used by the family)

**Only these objects may be consumed by the decision rule.**

No decision logic reads:
- Interaction Memory (IM)
- Summary Memory (SM)
- Raw messages
- Intermediate drafts

---

## 0.3 Interaction Topology (Explicit Synchronization With Phases)

Topology controls **only the Interaction / Refinement Phase**.
All other phases are topology-independent.

### Why Interaction Exists at All

Interaction is **not** required for voting or quorum logic.
It exists to:
- allow critique and refinement,
- induce conformity or disagreement,
- shape which proposals survive into `P_r`.

Once `P_r` is frozen, topology is irrelevant.

---

### T1 — Centralized Star (Hub-and-Spoke)

**Graph**
- One distinguished hub agent `h`
- All other agents connect only to `h`

**Interaction Phase Semantics**
- Each non-hub agent sends critiques/refinements to `h`
- `h` aggregates and rebroadcasts a synthesized refinement
- Non-hub agents do **not** observe each other directly

**Evaluator implication**
- There may be **multiple evaluators**, but:
  - evaluators do **not** interact,
  - evaluators only see `P_r` (and optionally `SM[r]`), never raw IM

---

### T2 — Fully Connected (Complete Graph)

**Graph**
- Every agent connects to every other agent

**Interaction Phase Semantics**
- All agents see all critiques and refinements
- Refinement pressure is maximized
- Conformity emerges fastest in this topology

**Evaluator implication**
- Same as T1: evaluators never participate in interaction

---

**Topology constraint**
- Topology affects **what information flows during interaction**
- Topology never changes:
  - proposal freezing,
  - evaluation logic,
  - trust updates,
  - decision predicates

---

## 1. Family 1 — Vote-Based Aggregation

**One-round voting. No quorum memory. No persistence.**

Commitment may occur in **any round**.

---

### 1.1 Roles

- **Proposers**  
  Generate candidate proposals.

- **Voters**  
  Cast exactly one vote each.

- **Vote Counter**  
  Deterministic system module (not an agent).

---

### 1.2 Phase Alignment

| Phase | What Happens |
|-----|-------------|
| Proposal | Proposers generate candidates |
| Interaction | Optional refinement (topology-dependent) |
| Evaluation | *None* |
| State Update | *None* |
| Decision Rule | Votes are counted |

---

### 1.3 Variant A1 — Majority Voting (Unweighted)

**Decision rule (round `r`)**

1. Each voter selects **one** proposal from `P_r`.
2. Count votes per proposal.
3. Select the proposal with the most votes.
4. Commit **only if** it has a strict majority.

**Commit condition**
- More than half of voters selected the same proposal.

**If not met**
- No commit.
- Proceed to round `r+1`.

**Artifacts read**
- `P_r`
- Ballots

**Artifacts written**
- None

**Evaluator**
- Deterministic vote counter only.

---

### 1.4 Variant A2 — Trust-Weighted Voting

Same as A1, except votes are **weighted by trust**.

**Decision rule (round `r`)**

1. Each voter selects one proposal from `P_r`.
2. Each vote contributes weight `w_i` from `RM`.
3. Sum weights per proposal.
4. Commit if one proposal reaches ≥ 50% of total trust weight.

**Artifacts read**
- `P_r`
- `RM`
- Ballots

**Artifacts written**
- None

**Evaluator**
- Deterministic weighted vote counter.
- No agentic judgment or deliberation.

---

## 2. Family 2 — Weighted BFT-Style Commit Rules

**Leader nomination + weighted quorum voting.**

Commitment requires **two explicit quorum checks** in the same round.

---

### 2.1 Roles (Per Round)

- **Leader**  
  Exactly one agent, selected by trust.

- **Replicas**  
  All non-leader agents.

---

### 2.2 Phase Alignment

| Phase | What Happens |
|-----|-------------|
| Proposal | Proposers generate candidates |
| Interaction | Refinement (topology-dependent) |
| Evaluation | Evaluators score `P_r` |
| State Update | RM updated |
| Decision Rule | Leader nomination + quorum voting |

---

### 2.3 Leader Selection

At the **start of Decision Rule Evaluation**:

- Leader is the agent with highest trust in `RM`.
- Ties broken deterministically.

Leader selection:
- uses **only RM**,
- is recomputed every round,
- is not adaptive beyond trust updates.

---

### 2.4 Nomination Rule

Leader selects **exactly one** proposal from `P_r`.

Selection rule:
- Deterministic.
- Highest evaluator score in `ES[r]`.

Leader has **no other powers**.

---

### 2.5 Two-Phase Commit Logic

#### Phase A — Prepare

- Each replica votes ACCEPT or REJECT.
- Votes are weighted by trust.
- If < 2/3 of total trust ACCEPT → round fails.

#### Phase B — Commit

- Executed only if Prepare succeeds.
- Same voting rule.
- If ≥ 2/3 ACCEPT → commit and terminate task.

---

### 2.6 Artifacts

**Read**
- `P_r`
- `RM`
- `ES[r]`

**Written (audit only)**
- Leader identity
- Nomination
- Prepare votes
- Commit votes

---

## 3. Family 3 — Persistence-Based Finalization

**No voting. No quorum. No trust use.**

Commitment depends on **stability across rounds**.

---

### 3.1 Roles

- **Proposers**
- **Stability Engine** (system module)

No evaluators by default.

---

### 3.2 Phase Alignment

| Phase | What Happens |
|-----|-------------|
| Proposal | Proposals generated |
| Interaction | Optional refinement |
| Evaluation | *None* |
| State Update | *None* |
| Decision Rule | Stability check |

---

### 3.3 Canonical Selection

Each round:
- Select the proposal with the most proposer support.
- Deterministic tie-breaking.

---

### 3.4 Persistence Rule

- Track how many consecutive rounds the same proposal is selected.
- Commit once the same proposal appears for `β` consecutive rounds.

Default:
- `β = 2`

---

### 3.5 Artifacts

**Read**
- `P_r`
- Previous selected proposal

**Written**
- Selected candidate
- Persistence counter

---

## 4. Final Experimental Scope (Locked)

### What We Test

- 3 consensus families
- 2 interaction topologies (Star, Complete)
- 3 access regimes (A, B, C)
- Single-artifact + selected compound attacks

### What We Do *Not* Test

- Ring / expanding diffusion
- Adaptive leader policies
- Multiple equivalence metrics
- Multiple quorum thresholds
- Agentic vote counting
- Dynamic protocol switching

---

## 5. Why This Design Is Sufficient

This setup:
- Spans **voting**, **trust-weighted influence**, **quorum consensus**, and **temporal stability**
- Covers all **mechanistically distinct attack surfaces**
- Avoids parameter explosion
- Is feasible for a small, high-performing undergraduate team

Any further protocol variants would increase cost without increasing explanatory power.

**This protocol layer is final and locked.**

