# Consensus-Mechanism Instantiations

---

## 0. Shared Assumptions Across All Families

### 0.1 Intra-Round Ordering

Each round `r` executes the following **fixed order**:

1. **Proposal Phase**
2. **Interaction / Refinement Phase**
3. **Evaluation Phase**
4. **State Update Phase**
5. **Decision Rule Evaluation**

All memory writes occur **before** the decision rule, except where explicitly noted.

---

### 0.2 Frozen Objects Consumed by Decision Logic

At the end of **State Update Phase** in round `r`, the following objects are frozen:

- **Proposal set**  
  `P_r`: finalized proposals for round `r`

- **Evaluation state**  
  `ES[r]`: evaluator outputs over `P_r`

- **Trust state**  
  `RM`: per-agent trust weights (post-update for this round)

**Only these frozen objects may be consumed by the decision rule.**

---

### 0.3 Interaction Topology

W fix **two** interaction topologies that
span the behavior space observed in prior work.

#### T1 — Centralized Star (Hub-and-Spoke)

- One hub agent `h`
- All agents communicate **only** with `h`
- Hub aggregates and rebroadcasts

---

#### T2 — Fully Connected Graph (Complete)
- Every agent observes every other agent

---

## 1. Family 1 — Vote-Based Aggregation

This family commits based on **per-round voting** over `P_r`.
Commitment may occur in **any round**.

### 1.1 Fixed Roles

- **Proposers**: generate proposals forming `P_r`
- **Voters**: cast ballots
- **Vote Counter**: deterministic system module

---

### 1.2 Ballot Object

Each voter `i` emits exactly one ballot:

\[
vote_i^r \in P_r
\]

---

### 1.3 Variant A1 — Majority Voting (Unweighted)

#### Commit Predicate (Round `r`)

Let:
\[
count(p) = |\{ i : vote_i^r = p \}|
\]

- Select:
  \[
  p^{*r} = \operatorname*{arg\,max}_p count(p)
  \]
  (deterministic tie-break)
- **Commit** iff:
  \[
  count(p^{*r}) > |V_r| / 2
  \]

If not satisfied, proceed to round `r+1`.

#### Artifacts Read
- `P_r`
- Ballots `{vote_i^r}`

#### Artifacts Written
- None required

#### Evaluator
A deterministic system module that counts each proposal's votes and outputs the highest-voted proposal. 

---

### 1.4 Variant A2 — Trust-Weighted Voting

Votes are weighted by trust weights from `RM`.

#### Weighted Tally

\[
W(p) = \sum_{i: vote_i^r=p} w_i,\quad
W_{total} = \sum_i w_i
\]

#### Commit Predicate

- Select:
  \[
  p^{*r} = \operatorname*{arg\,max}_p W(p)
  \]
- **Commit** iff:
  \[
  W(p^{*r}) \ge 0.5 \cdot W_{total}
  \]

#### Artifacts Read
- `P_r`
- `RM`
- Ballots `{vote_i^r}`

#### Artifacts Written
- None required

#### Evaluator
- A deterministic system module that considers both a proposal's votes and the corresponding proposer to decide which proposal to output. 

---

## 2. Family 2 — Weighted BFT-Style Commit Rules

This family implements **leader nomination + weighted quorum voting**.

---
### 2.1 Fixed Roles (Per Round `r`)

- **Leader** `ℓ_r`  
  Exactly one agent designated as leader for round `r`.

- **Replicas**  
  All agents except `ℓ_r`.  
  Replicas do not propose new candidates; they only vote on the leader’s nomination.

---

### 2.2 Leader Selection

- **Rotating leader (round-robin)**

Leader identity is fixed deterministically as:
\[
\ell_r = (r \bmod N)
\]

- The leader selection rule is fixed for the entire task.
- Leader identity does **not** depend on runtime behavior, votes, or trust updates.

---

### 2.3 Nomination Rule (Leader Action)

At round `r`, the leader selects **exactly one** proposal from the frozen proposal set:

\[
p_{\text{lead}}^r \in P_r
\]

**Nomination constraints**
- Selection is **deterministic**.
- Selection is a fixed function of the evaluation state:
\[
p_{\text{lead}}^r = \operatorname*{arg\,max}_{p \in P_r} \text{score}_{ES[r]}(p)
\]
(ties broken deterministically).

**Important clarifications**
- The leader does **not** modify proposals.
- The leader does **not** aggregate votes.
- The leader does **not** influence quorum thresholds.
- The leader’s only authority is proposal nomination.

---

### 2.4 Two-Phase Weighted Commit Protocol

Commitment requires passing **both** phases in the same round.

---

#### Phase A — Prepare

Each replica `i` independently evaluates the leader’s proposal and emits a prepare vote:

\[
prepare_i^r \in \{\text{ACCEPT}, \text{REJECT}\}
\]

Votes are weighted by trust:

\[
W_{\text{prepare}} = \sum_{i : prepare_i^r = \text{ACCEPT}} w_i
\]

Let:
\[
W_{\text{total}} = \sum_i w_i
\]

**Prepare threshold**
\[
W_{\text{prepare}} \ge \frac{2}{3} \cdot W_{\text{total}}
\]

- If the threshold is **not met**, the protocol:
  - does **not** commit,
  - does **not** enter Phase B,
  - proceeds to round `r+1`.

---

#### Phase B — Commit

Executed **only if** the Prepare phase succeeds.

Each replica `i` emits a commit vote:

\[
commit_i^r \in \{\text{ACCEPT}, \text{REJECT}\}
\]

Weighted support:
\[
W_{\text{commit}} = \sum_{i : commit_i^r = \text{ACCEPT}} w_i
\]

**Commit threshold**
\[
W_{\text{commit}} \ge \frac{2}{3} \cdot W_{\text{total}}
\]

- If satisfied:
  - `p_{\text{lead}}^r` is **committed**,
  - the task terminates immediately.
- If not satisfied:
  - no commitment occurs,
  - the task proceeds to round `r+1`.

---

### 2.5 Artifacts Read (Decision-Critical)

The commit predicate reads **only**:

- `P_r` — frozen proposal set
- `RM` — trust weights (structural)
- `ES[r]` — used **only** for leader nomination

No other memory artifacts are consulted by the commit logic.

---

### 2.6 Artifacts Written (Minimal Audit Set)

The following artifacts are persisted for correctness auditing:

- `Leader[r] = \ell_r`
- `Nomination[r] = p_{\text{lead}}^r`
- `PrepareVotes[r] = \{prepare_i^r\}`
- `CommitVotes[r] = \{commit_i^r\}`

These artifacts:
- are written **after** their respective phases,
- are not read by future rounds unless explicitly enabled for analysis,
- are sufficient to reconstruct whether quorum conditions were met.

---

## 3. Family 3 — Persistence-Based Finalization

This family commits **only after stability across rounds**.

---

### 3.1 Fixed Roles

- **Proposers**
- **Stability Engine** (system module)

No agentic evaluators by default.

---

### 3.2 Selection Function

Each round:
\[
p^{*r} = \operatorname*{arg\,max}_{p \in P_r} \text{plurality}(p)
\]

No trust weighting inside `S`.

---

### 3.3 Equivalence Relation

- **Exact match only**

---

### 3.4 Persistence Counter

Let `H_r` track consecutive identical selections:

- If `p^{*r} = p^{*(r-1)}` → `H_r = H_{r-1} + 1`
- Else → `H_r = 1`

---

### 3.5 Commit Predicate

Commit iff:
\[
H_r \ge \beta
\]

Default:
- `β = 2`

---

### 3.6 Artifacts Read
- `P_r`
- Past `p^{*}` history

### 3.7 Artifacts Written
- `Candidate[r]`
- `H_r`

---

## 4. Final Experimental Scope

### What We Test
- 3 consensus families
- 2 interaction topologies (Star, Complete)
- 3 access regimes (A, B, C)
- Single-artifact and selected compound attacks (as defined elsewhere)

### What We Explicitly Do *Not* Test
- Ring / expanding-ring diffusion
- Adaptive leader policies
- Multiple equivalence metrics
- Multiple quorum thresholds
- Agentic evaluators inside vote counting
- Dynamic protocol switching

---

## 5. Why This Is Enough

This configuration:
- Covers **direct voting**, **trust-weighted influence**, **quorum logic**, and **temporal persistence**
- Preserves all **mechanistically distinct attack surfaces**
- Avoids parameter explosion
- Is feasible for a small, focused research team

Any additional protocol variants would **increase cost without adding new explanatory power**.

This file defines the **final, locked-down protocol layer** for experiments.
