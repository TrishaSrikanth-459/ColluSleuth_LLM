**Consensus-Mechanism Instantiations**

---

## Notation (Local to This File)

- Round index: `r`
- Proposal set for round `r`: `P_r = {p_1^r, …, p_k^r}` (final proposal variants produced by proposers **by the end of the refinement phase of the same round**)
- Evaluator outputs for round `r`: `ES[r]` (scores/ranks/accept flags over proposals in `P_r`)
- Per-agent trust weights: `w_i` (from `RM[i]`)
- Candidate selected for possible commitment in round `r`: `p*^r`
- Byzantine agent id: `b`

---

## Shared Round Objects (All Families)

### A. Proposal Set Construction (within round `r`)
1. `k` proposers emit initial proposals `{p_i^r,0}`
2. Critique/refinement occurs **within the same round** producing final proposals `{p_i^r,final}`
3. Define `P_r := {p_i^r,final}` as the **frozen** proposal set for evaluation and decision in round `r`

### B. Evaluation Call (within round `r`)
- The evaluator(s) produce `ES[r]` over `P_r`
- `ES[r]` is treated as the **only** per-round evaluation object consumed by the decision logic (even if internally derived from other state)

> Family-specific differences begin at: how `p*^r` is chosen and what the commit predicate is.

---

## Family 1 — Vote-Based Aggregation
Includes:
1) **Majority voting (equal weight)**  
2) **Trust-weighted voting (trust substrate `w_i`)**

### 1.1 Majority Voting (Equal Weight)

#### 1.1.1 Round `r` Decision Procedure
**Input objects**
- `P_r` (frozen proposals)
- `ES[r]` (optional, depending on the variant; see below)

**Step 1 — Determine the ballot options**
- Ballot options are the proposals in `P_r`
- If `|P_r| > 2`, each voter selects exactly one proposal (plurality ballot)

**Step 2 — Voter rule (per agent voter `i`)**
- Each voter `i` outputs a vote `v_i^r ∈ P_r`
- Default voter mapping (deterministic):
  - If the protocol uses evaluation mediation: `v_i^r := argmax_{p∈
    
---

## Common Round-Level Objects (All Families)

At the end of the **interaction/refinement phase** of round `r`, the following objects are fixed:

- **Proposal set**  
  `P_r = {p_1^r, …, p_k^r}`  
  Final proposal variants produced *within round `r`*.

- **Evaluation State**  
  `ES[r]`, produced once per round over `P_r`.

All consensus families differ **only** in:
1. how `ES[r]` is interpreted,
2. how (or whether) trust weights `w_i` are used,
3. the condition under which a proposal is committed.

---

## Family A — Vote-Based Aggregation

This family commits based on **per-round voting outcomes**.  
Commitment can occur in **any round**.

### A.1 Majority Voting (Unweighted)

#### Inputs (Round `r`)
- Proposal set `P_r`
- Optional: `ES[r]` (used only to restrict admissible proposals)

#### Voting Procedure
1. Each non-proposer agent casts **one vote**:
   - Vote domain: `P_r`
   - Vote selection rule:
     - If evaluation-gated: vote must be for a proposal marked acceptable in `ES[r]`
     - Otherwise: unrestricted choice
2. Votes are counted with **equal weight**.

#### Commit Predicate
Let `count(p)` be the number of votes for proposal `p`.

Commit `p*^r` iff:
count(p*^r) > |V| / 2

where `V` is the set of voters in round `r`.

#### Non-Commit Outcome
- If no proposal satisfies the predicate:
  - Task continues to round `r+1`.

#### Trust Usage
- `RM` is **not consulted**.
- `RM` may still be updated post-round, but has no effect on commitment.

---

### A.2 Trust-Weighted Voting

Identical to majority voting except that votes are **weighted**.

#### Inputs (Round `r`)
- Proposal set `P_r`
- Evaluation State `ES[r]`
- Trust weights `{w_i}` from `RM`

#### Voting Procedure
1. Each voter `i` selects one proposal `v_i^r ∈ P_r`.
2. Each vote contributes weight `w_i`.

#### Commit Predicate
Let:
W(p) = Σ_{i : v_i^r = p} w_i
W_total = Σ_i w_i


Commit `p*^r` iff:
W(p*^r) ≥ τ · W_total

where `τ` is a fixed threshold (default `τ = 0.5`).

#### Non-Commit Outcome
- If no proposal meets the threshold:
  - Task continues.

#### Trust Usage
- `RM` directly affects commitment via vote weights.
- Influence accumulation attacks target `RM`.

---

## Family B — Weighted BFT-Style Commit Rules

This family implements **explicit quorum logic** inspired by Byzantine Fault Tolerance.

Commitment requires satisfying a **quorum predicate**, not just winning a vote.

### B.1 Leader-Based Proposal Selection

#### Inputs (Round `r`)
- Proposal set `P_r`
- Evaluation State `ES[r]`
- Trust weights `{w_i}`

#### Step 1 — Leader Selection
- A leader `ℓ_r` is chosen deterministically:
  - Fixed leader
  - Rotating leader
  - Highest-trust leader (`argmax_i w_i`)
- Leader selection rule is fixed per experiment.

#### Step 2 — Proposal Nomination
- Leader selects exactly one proposal:
p_lead^r ∈ P_r

Selection may depend on `ES[r]`.

---

### B.2 Prepare / Commit Voting

#### Prepare Phase
- Each replica `i` issues a prepare vote:
  - Accept or reject `p_lead^r`
- Vote weight: `w_i`

#### Commit Predicate
Let:
W_accept = Σ_{i accepts} w_i
W_total = Σ_i w_i


Commit `p_lead^r` iff:
W_accept ≥ Q

where `Q` is the quorum threshold (e.g., `Q = 2/3 · W_total`).

#### Failure Modes
- If quorum is not reached:
  - No commit
  - Task proceeds to next round
  - Leader may change in next round

#### Trust Usage
- Trust weights are **structural**, not advisory.
- Attacks target quorum formation via `RM`, `ES`, or leader influence.

---

## Family C — Persistence-Based Finalization

This family **never commits in a single round**.  
Commitment requires **temporal stability** across rounds.

### C.1 Stability Tracking

#### Inputs (Round `r`)
- Proposal set `P_r`
- Evaluation State `ES[r]`

#### Step 1 — Canonical Proposal Selection
- A deterministic selection function `S` is applied:
p*^r = S(P_r, ES[r])

Examples:
- Highest-ranked proposal
- Lexicographically smallest among top-scored
- Median-ranked proposal

This produces **one candidate per round**.

---

### C.2 Persistence Counter

Define:
- `H_r` = number of consecutive rounds up to `r` where `p*^r` is unchanged

Update rule:
if p*^r == p*^(r-1):
H_r = H_{r-1} + 1
else:
H_r = 1


---

### C.3 Commit Predicate

Commit `p*^r` iff:
H_r ≥ β

where `β` is the fixed stability horizon.

#### Non-Commit Outcome
- If stability breaks:
  - Counter resets
- If `β` is never reached:
  - Task ends by abort or timeout

#### Trust Usage
- Trust may affect:
  - Evaluation scores
  - Tie-breaking in `S`
- Trust does **not** directly trigger commitment.

---

## Summary: What Actually Differs Across Families

| Aspect | Vote-Based | Weighted BFT | Persistence-Based |
|---|---|---|---|
| Commit timing | Any round | Any round | Only after β rounds |
| Commit trigger | Vote threshold | Quorum threshold | Temporal stability |
| Uses trust weights | Optional | Mandatory | Indirect only |
| Leader role | None | Required | None |
| Primary attack target | RM / ES | RM / ES / leader | SM / ES / persistence |
