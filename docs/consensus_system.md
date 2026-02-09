# consensus_system.md  
**Concrete Consensus Protocol Families under Writable Trust Substrates**

This document specifies **exactly how each consensus family operates**, end-to-end, including:
- execution order,
- decision rules,
- which memory artifacts are read and written,
- what constitutes commitment,
- and where the attack surface lies.

There is **no abstraction across families** beyond shared definitions.  
Each family is specified independently.

---

## Shared Definitions (Applies to All Families)

### Task vs. Round

- A **task** is one full execution of the system on a single input prompt.
- A task consists of multiple **rounds** `r = 1 … R`.
- At most **one commitment** may occur per task.

A **round** consists of:
1. Proposal generation
2. Interaction (optional)
3. Evaluation
4. State update
5. Decision rule execution

> **The decision rule is executed after every round.**  
> Commitment may occur in any round, but only once per task.

---

## Shared Memory Artifacts (Vocabulary)

| Artifact | Persistence | Directly used by decision rule |
|---|---|---|
| Interaction Memory (IM) | per task | no |
| Summary Memory (SM) | per round | no |
| Evaluation State (ES) | per round | **yes** |
| Reputation Memory (RM) | per task | no (indirect only) |

---

# 1. Vote-Based Aggregation Protocols

This family includes:
- **Majority voting**
- **Trust-weighted voting**

There is **no multi-round convergence requirement**.

---

## 1.1 Protocol Objective

Select a final output by aggregating independent agent judgments in a single round.

---

## 1.2 Round Structure

### Proposal Phase
- `k ≥ 2` agents independently generate candidate outputs.

### Interaction Phase (Optional)
- Agents may briefly critique proposals.
- No revisions are required.

### Evaluation Phase
- Each voting agent evaluates proposals.
- Produces a vote:
  - Majority voting: binary vote
  - Trust-weighted voting: weighted vote using `w_i`

### State Update
- Evaluation State (ES) is written.
- Reputation Memory (RM) may be updated.

### Decision Rule (Executed Immediately)
- Commit occurs in the same round.

---

## 1.3 Decision Rule

### Majority Voting
Commit proposal `j` if:
votes_j > N / 2


### Trust-Weighted Voting
Commit proposal `j` if:
Σ_i (w_i · vote_{i,j}) ≥ τ


No persistence across rounds is required.

---

## 1.4 Memory Usage

### Interaction Memory (IM)
- Stores proposals and votes.
- Not read by decision rule.

### Summary Memory (SM)
- Optional.
- Used only if evaluators rely on compressed context.

### Evaluation State (ES)
ES[r] = {(proposal j, vote_count_j [, weighted_sum_j])}

- **Primary decision substrate**
- Read directly by decision rule.

### Reputation Memory (RM)
- Stores trust weights `w_i`
- Used only to weight votes.

---

## 1.5 Attack Surface

| Artifact | Failure mode |
|---|---|
| ES | Direct vote manipulation |
| RM | Inflated influence |
| IM / SM | Indirect framing only |

---

# 2. Weighted BFT-Style Commit Rules

This family includes:
- blockchain-inspired voting
- explicit quorum thresholds
- Byzantine fault assumptions

---

## 2.1 Protocol Objective

Reach agreement despite up to `f` Byzantine agents using explicit quorum guarantees.

---

## 2.2 Round Structure

### Proposal Phase
- `k` proposers generate candidates.
- A **Leader** selects exactly one proposal.

### Interaction Phase
- Replicas validate the leader’s proposal.
- No persuasion; checks are protocol-defined.

### Evaluation Phase
- Each replica casts a vote:
  - prepare / commit style
- Votes are weighted by `w_i`.

### State Update
- Evaluation State (ES) written.
- Reputation Memory (RM) updated.

### Decision Rule
- Quorum condition evaluated.

---

## 2.3 Decision Rule

Commit proposal `p` if:
Σ_i (w_i · vote_i) ≥ quorum_threshold


Typical thresholds:
- `2f + 1` (unweighted)
- weighted equivalent

No persistence requirement across rounds.

---

## 2.4 Memory Usage

### Interaction Memory (IM)
- Stores leader proposal and replica votes.
- Audit only.

### Summary Memory (SM)
- Optional compression.
- Not used by quorum logic.

### Evaluation State (ES)
ES[r] = {(replica i, vote_i, weight_i)}

- **Direct input to quorum check**

### Reputation Memory (RM)
- Stores trust weights.
- Determines voting power and quorum satisfaction.

---

## 2.5 Attack Surface

| Artifact | Failure mode |
|---|---|
| ES | Quorum falsification |
| RM | Vote amplification |
| IM | Audit trail corruption |

---

# 3. Persistence-Based Finalization Protocols

This family includes:
- stability-horizon deliberation
- β-round persistence rules

---

## 3.1 Protocol Objective

Commit **only after agreement persists** across multiple rounds, reducing susceptibility to transient manipulation.

---

## 3.2 Round Structure

### Proposal Phase
- `k` agents independently propose candidates.

### Interaction Phase
- Agents critique and refine proposals.
- Proposals may change across rounds.

### Evaluation Phase
- Evaluators select a **current leading decision**.

### State Update
- Stability counters updated.
- Reputation Memory (optional) updated.

### Decision Rule
- Persistence condition evaluated.

---

## 3.3 Decision Rule

Commit proposal `p` if:
p is the leading decision for β consecutive rounds


If the leading decision changes, the counter resets.

---

## 3.4 Memory Usage

### Interaction Memory (IM)
- Stores deliberation history.

### Summary Memory (SM)
- **Critical artifact**
- Encodes the perceived current consensus.

### Evaluation State (ES)
ES[r] = {leading_decision, stability_counter}

- Directly read by decision rule.

### Reputation Memory (RM)
- Optional.
- May determine whose proposals are eligible to count.

---

## 3.5 Attack Surface

| Artifact | Failure mode |
|---|---|
| SM | False stability |
| ES | Counter manipulation |
| RM | Selective eligibility |
| IM | Framing only |

---

# 4. Cross-Family Comparison

| Property | Vote-Based | Weighted BFT | Persistence-Based |
|---|---|---|---|
| Multi-round required | No | No | **Yes** |
| Explicit quorum | No | **Yes** | Optional |
| Persistence check | No | No | **Yes** |
| RM critical | Optional | **Core** | Optional |
| SM critical | No | No | **Yes** |
| Primary failure mode | Vote skew | Quorum capture | False convergence |

---

## Final Note

Each protocol family:
- Uses **the same memory artifacts**
- Executes **different decision rules**
- Fails under **distinct trust-substrate attacks**

This separation is intentional and necessary for clean experimental attribution.
