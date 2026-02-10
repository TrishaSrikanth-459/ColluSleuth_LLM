**Consensus-Mechanism Instantiations**

This file specifies the **exact executable consensus mechanisms** evaluated in experiments.
It assumes that the system class, agent model, memory taxonomy (IM / SM / ES / RM),
and access regimes (A / B / C) are defined elsewhere.

This file answers one question only:

> *Given a frozen proposal set at the end of a round, how does the system decide whether to commit — and to what?*

---

## 0. Global Execution Model (Applies to All Families)

### 0.1 Intra-Round Phase Ordering

Each round `r` executes the following **fixed, linear sequence**:

1. **Proposal Phase**  
2. **Interaction / Refinement Phase**  
3. **Evaluation Phase** *(only if the family defines evaluators)*  
4. **State Update Phase** *(only if the family updates trust)*  
5. **Decision Rule Evaluation**

There is **no overlap or branching** between phases.

---

### 0.2 Frozen State for Decision Logic

At the end of the **State Update Phase**, the following objects are frozen:

- `P_r` — final proposal set for round `r`
- `ES[r]` — evaluation outputs (only if evaluators exist)
- `RM` — trust weights after update (only if trust is used)

**The decision rule may read only these frozen objects.**

It may **not** read:
- Interaction Memory (IM)
- Summary Memory (SM)
- Raw messages or drafts
- Intermediate votes or critiques
  
---

### 0.3 Interaction Topology

W fix two interaction topologies that span the behavior space observed in prior work.

---
### T1 — Centralized Star (Hub-and-Spoke)
- One hub agent h
- All agents communicate only with h
- Hub aggregates and rebroadcasts

### T2 — Fully Connected Graph

- Every agent observes every other agent's outputs.
- All proposals, critiques, and refinements are globally visible, although not all agents are responsible for responding to certain received outputs.

**Effect**:  
Maximum conformity pressure and fastest diffusion.

---

## 1. Family 1 — Vote-Based Aggregation

**Core idea:**  
> *Commit if enough agents explicitly vote for the same proposal in a single round.*

There is:
- **no evaluator**
- **no trust update**
- **no cross-round memory**

This family isolates *direct influence via voting*.

---

### 1.1 Roles

- **Proposers**  
  Generate proposals during the Proposal Phase.

- **Voters**  
  Every agent casts exactly one vote.

- **Vote Counter (System Module)**  
  Deterministically tallies votes and checks the commit condition.

---

### 1.2 Phase Mechanics

| Phase | Behavior |
|-----|---------|
| Proposal | Proposals generated |
| Interaction | *None* (topology irrelevant here) |
| Evaluation | *None* |
| State Update | *None* |
| Decision Rule | Votes counted |

---

### 1.3 Variant A1 — Majority Voting (Unweighted)

**Decision logic (round `r`)**

1. Each voter selects **one** proposal from `P_r`.
2. Count how many votes each proposal receives.
3. Identify the proposal with the highest count.
4. **Commit only if** that proposal has a strict majority.

**Commit condition**
- More than half of all voters selected the same proposal.

**If not met**
- No commitment.
- Task proceeds to round `r+1`.

**Artifacts read**
- `P_r`
- Ballots

**Artifacts written**
- None

**Key property**
- Influence is purely *numerical*.
- No agent has structural advantage.

---

### 1.4 Variant A2 — Trust-Weighted Voting

Same as A1, except votes are **weighted by trust**.

**Decision logic (round `r`)**

1. Each voter selects one proposal from `P_r`.
2. Each vote contributes weight `w_i` from `RM`.
3. Sum total trust weight per proposal.
4. **Commit if** a proposal accumulates at least 50% of total trust.

**Artifacts read**
- `P_r`
- `RM`
- Ballots

**Artifacts written**
- None

**Key property**
- Trust directly amplifies influence.
- Manipulating `RM` directly manipulates commitment.

---

## 2. Family 2 — Weighted BFT

**Core idea**  
A single trusted leader sets the agenda by nominating one proposal,  
while the group retains final authority via a weighted quorum vote.

Each round represents **one attempt to commit**.
A new round is entered **only if quorum is not reached**.

---

## 2.1 Roles

- **Proposers**  
  Agents that generate candidate proposals.

- **Leader**  
  One agent selected by trust at task initialization.
  The leader nominates exactly one proposal per round.

- **Replicas**  
  All non-leader agents.
  Replicas:
  - do not nominate proposals,
  - do not modify proposals,
  - cast advisory votes and quorum votes.

No evaluators are used in this family.

---

## 2.2 Leader Selection (Once Per Task)

Leader selection occurs **once**, before round `r = 1`.

\[
\ell = \arg\max_i RM_{\text{init}}[i]
\]

- `RM_init` is the trust state at task start.
- Ties are broken deterministically.

**Design constraints**
- Leader identity is fixed for the entire task.
- Leader selection:
  - does not change across rounds,
  - does not depend on runtime votes,
  - prevents mid-task RM manipulation from immediately yielding control.

---

## 2.3 Phase Alignment (Round `r`)

| Phase | What Happens |
|------|--------------|
| Proposal | Proposers generate candidate proposals |
| Interaction | *None* |
| Evaluation | *None* |
| State Update | RM updated |
| Decision Rule | Advisory voting → leader nomination → quorum vote |

All steps below occur **within a single round**.

---

## 2.4 Proposal Phase (Source of `P_r`)

At the start of round `r`:

- Each proposer independently generates one candidate output.
- All candidate outputs are collected into the frozen proposal set:

\[
P_r = \{p_1^r, p_2^r, \dots, p_k^r\}
\]

---

## 2.5 Advisory Replica Voting (Pre-Nomination)

Before leader nomination, each replica `i` casts **one advisory vote**:

\[
vote_i^r \in P_r
\]

Votes are collected as:

\[
Votes[r] = \{vote_i^r\}
\]

**Properties**
- Advisory votes:
  - are non-binding,
  - do not trigger commitment,
  - exist solely to inform the leader.
- Votes are cast on fully formed proposals in `P_r`.

---

## 2.6 Inputs Available to the Leader (Round `r`)

Before nomination, the leader may read:

- `P_r` — frozen proposal set
- `Votes[r]` — advisory replica preferences
- `RM` — trust weights (contextual information)

The leader does **not** see:
- replica internal reasoning,
- raw interaction logs,
- any future-round information.

---

## 2.7 Nomination Rule (Leader Action)

The leader selects **exactly one** proposal:

\[
p_{\text{lead}}^r \in P_r
\]

**Nomination policy**
- The choice is **agentic and non-deterministic**.
- The leader may consider:
  - advisory votes,
  - trust distribution,
  - its own internal reasoning.

**Hard constraints**
- The leader:
  - cannot modify proposals,
  - cannot merge or split proposals,
  - cannot adjust quorum thresholds,
  - cannot count or weight votes.

The leader’s authority is strictly **agenda-setting**.

---

## 2.8 Weighted Quorum Commit Logic (Within Round `r`)

After nomination, replicas independently decide whether the proposal is acceptable.

### Quorum Vote

Each replica `i` casts a binary vote:

\[
accept_i^r \in \{\text{ACCEPT}, \text{REJECT}\}
\]

Votes are **chosen agentically** by replicas.
Trust weights affect **aggregation only**, not vote choice.

### Aggregation

\[
W_{\text{accept}} = \sum_{i \text{ voting ACCEPT}} w_i
\]
\[
W_{\text{total}} = \sum_i w_i
\]

### Commit Condition

\[
W_{\text{accept}} \ge \frac{2}{3} \cdot W_{\text{total}}
\]

- If the condition is satisfied:
  - `p_{\text{lead}}^r` is **committed immediately**,
  - the task terminates,
  - **no further rounds are executed**.

- If the condition is not satisfied:
  - no commitment occurs in round `r`,
  - execution proceeds to round `r+1`.

---

## 2.9 Artifacts

**Read by decision logic**
- `P_r`
- `Votes[r]`
- `RM`

**Written (audit only)**
- Leader identity
- Advisory votes
- Nomination
- Quorum votes

---

## 3. Family 3 — Persistence-Based Finalization 

### Core Idea 

> A proposal is committed **only if multiple agents independently produce the same proposal
> in multiple consecutive rounds**.

There is:
- no voting,
- no trust,
- no leader,
- no evaluators.

Agreement is inferred **only from repeated independent generation**.

---

## 3.1 Roles

- **Proposers**  
  All agents act only as proposers.

- **Stability Engine** (system module)  
  Observes proposals and checks persistence conditions.
  It does **not** judge quality or correctness.

---

## 3.2 What Happens Each Round (Very Explicit)

### Step 1 — Proposal Generation
In round `r`, **every agent independently generates one proposal**.

This produces:
\[
P_r = \{p_1^r, p_2^r, \dots, p_N^r\}
\]

Agents do **not** vote, score, rank, or evaluate.

---

### Step 2 — Proposal Grouping (Exact Match Only)

The system groups proposals by **reasonable textual equality**, judged by a single LLM.  

Example:
- Agent 1: `"Plan A"`
- Agent 2: `"Plan A"`
- Agent 3: `"Plan B"`

Then:
- `"Plan A"` has support 2
- `"Plan B"` has support 1

---

### Step 3 — Round Candidate Selection

Let:
\[
support_r(p) = \text{number of agents who produced proposal } p \text{ in round } r
\]

Select the proposal with the **highest support**:
\[
p_r^* = \arg\max_p support_r(p)
\]

Ties are broken deterministically.

---

### Step 4 — Minimum Support Check

If:
\[
support_r(p_r^*) < \alpha
\]

then:
- **no candidate is accepted this round**, and
- the persistence counter resets.

Default:
- `α = 2`

This means:
> At least **two different agents** must independently produce the same proposal
> in the *same round* for it to even count.

A single Byzantine agent **cannot progress alone**.

---

## 3.3 Persistence Rule (Across Rounds)

The system tracks a counter `H_r`:

- If:
  - a valid candidate exists this round, **and**
  - it is the same as last round’s candidate,

  then:
  \[
  H_r = H_{r-1} + 1
  \]

- Otherwise:
  \[
  H_r = 1 \quad \text{(if a new valid candidate appears)}
  \]
  or
  \[
  H_r = 0 \quad \text{(if no candidate passes } \alpha\text{)}
  \]

---

## 3.4 Commit Condition

Commit when:
\[
H_r \ge \beta
\]

Default:
- `β = 2`

In words:
> The **same proposal**, produced by **at least two agents**, must appear
> in **two consecutive rounds**.

**This IS**
- a test of **temporal influence**,
- a test of **convergence dynamics**,
- a test of **long-horizon manipulation**.
  
---

## 4. Experimental Scope (Final and Locked)

### What We Test

- 3 consensus families
- 2 interaction topologies (Star, Complete)
- 3 access regimes (A, B, C)
- Single-artifact + selected compound attacks

### What We Do Not Test

- Ring or expanding diffusion
- Adaptive leader policies
- Multiple equivalence metrics
- Multiple quorum thresholds
- Agentic vote counting
- Protocol switching

---

## 5. Why These Families Are Mechanistically Distinct

| Family | What Decides Commitment |
|------|--------------------------|
| Vote-Based | Immediate numerical agreement |
| BFT-Style | Trusted nomination + supermajority |
| Persistence-Based | Repeated agreement over time |

Each family exposes a **different attack surface**:
- numerical manipulation,
- trust/quorum manipulation,
- temporal manipulation.

Together, they span the relevant design space **without parameter explosion**.

**This protocol layer is final.**
