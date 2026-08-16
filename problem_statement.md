# Event Scheduling Problem — Mathematical Formulation

## Real-World Context

A non-profit organises weekly bike-riding and road-safety training sessions at schools across a city. Each session (event) requires a team of workers with specific certifications. Workers have varying availability, location preferences, priority levels, and skill sets. The goal is to produce a weekly schedule satisfying all hard requirements while minimising a weighted inconvenience objective.

---

## Sets

| Symbol | Meaning |
|--------|---------|
| $E$ | Set of events |
| $L$ | Set of locations (schools) |
| $D$ | Set of time periods (dates × {am, pm}) |
| $P$ | Set of workers (people) |
| $S$ | Set of skills = {mech, first_aid, leader} |
| $G \subseteq E$ | Groups of events sharing a `group_id` (a "class") |

---

## Parameters

### Event Parameters

| Symbol | Domain | Meaning |
|--------|--------|---------|
| $loc_e \in L$ | — | Location of event $e$ |
| $d_e \in D$ | — | Time period of event $e$ |
| $group_e \in G$ | — | Group/class identifier of event $e$ |
| $N_e \in \mathbb{Z}_{>0}$ | — | Number of workers required at event $e$ |
| $R_{e,s} \in \mathbb{Z}_{\ge 0}$ | $\forall s \in S$ | Minimum workers with skill $s$ required at $e$ (default: mech=2, first_aid=2, leader=1) |

### Worker Parameters

| Symbol | Domain | Meaning |
|--------|--------|---------|
| $skill_{p,s} \in \{0,1\}$ | $\forall s \in S$ | 1 if worker $p$ has skill $s$ |
| $priority_p \in \mathbb{Z}_{\ge 0}$ | — | Priority level (higher = more senior) |
| $neigh_p \in \text{Neighbourhoods}$ | — | Worker's residence neighbourhood |
| $can\_go_{p,l} \in \{0,1\}$ | $\forall l \in L$ | 1 if worker $p$ is willing/able to travel to location $l$ |
| $avail_{p,d} \in \{0,1\}$ | $\forall d \in D$ | 1 if worker $p$ is available during time period $d$ |
| $mass_p \in \mathbb{Z}_{>0}$ | — | Number of available dates (availability "mass"; capped at 45 if fully available) |

---

## Decision Variables

| Variable | Domain | Meaning |
|----------|--------|---------|
| $x_{p,e} \in \{0,1\}$ | $\forall p \in P, e \in E$ | 1 if worker $p$ assigned to event $e$ (only created if $can\_go_{p,loc_e}=1 \land avail_{p,d_e}=1$) |
| $y^{group}_{p,e_i,e_j} \in \{0,1\}$ | $\forall p, \forall e_i,e_j \in G, i<j$ | 1 if worker $p$ assigned to exactly one of $\{e_i,e_j\}$ (team inconsistency penalty) |
| $y^{loc}_{p,e_i,e_j} \in \{0,1\}$ | $\forall p, \forall e_i,e_j \text{ at same location}, i<j$ | Same as above, for same-location consistency |
| $dev_p \in \mathbb{Z}_{\ge 0}$ | $\forall p \in P$ | Absolute deviation from availability-weighted fair share within priority level |

---

## Hard Constraints

### (C1) Exact Staffing
$$
\forall e \in E: \quad \sum_{p \in P} x_{p,e} = N_e
$$

### (C2) Skill Minimums
$$
\forall e \in E, \forall s \in S: \quad \sum_{p \in P} skill_{p,s} \cdot x_{p,e} \ge R_{e,s}
$$

### (C3) No Double-Booking
$$
\forall p \in P, \forall d \in D: \quad \sum_{e: d_e = d} x_{p,e} \le 1
$$

### (C4) Availability & Reachability (by variable construction)
Variables $x_{p,e}$ only exist when $can\_go_{p,loc_e}=1$ and $avail_{p,d_e}=1$.

---

## Soft Objective Terms (Minimise $z$)

All terms are combined into a single weighted sum:
$$
\min \; z = \sum_{k} w_k \cdot penalty_k
$$

Default weights (lexicographic approximation):
| Term | Weight | Description |
|------|--------|-------------|
| $w_{group}$ | 100,000 | Same team across all events of a group |
| $w_{priority}$ | 10,000 | Prefer higher-priority workers |
| $w_{loc}$ | 1,000 | Same team across events at same location |
| $w_{fair}$ | 1 | Availability-weighted workload fairness within priority level |
| $w_{neigh}$ | 1 | Prefer workers in event's neighbourhood |

Set any weight to 0 to disable that term.

### (O1) Same-Group Team Consistency
For each group $G$ and each pair of events $e_i, e_j \in G, i<j$:
- If worker $p$ can serve **both** events: $y^{group}_{p,e_i,e_j} \ge x_{p,e_i} - x_{p,e_j}$ and $y^{group}_{p,e_i,e_j} \ge x_{p,e_j} - x_{p,e_i}$ (i.e., $y \ge |x_i - x_j|$)
- If worker $p$ can serve **only one** (partial availability): the missing side is fixed 0, so $|x - 0| = x$ — being scheduled on the available event breaks consistency and is penalised directly.

$$
penalty_{group} = \sum_{G} \sum_{e_i,e_j \in G, i<j} \sum_{p \in P} y^{group}_{p,e_i,e_j}
$$

### (O2) Priority Preference
Higher-priority workers are preferred. Cost per assignment:
$$
cost_{p} = \max_{p' \in P} priority_{p'} - priority_p
$$
$$
penalty_{priority} = \sum_{p,e} cost_p \cdot x_{p,e}
$$

### (O3) Same-Location Team Consistency
Identical to (O1) but grouped by location instead of group_id.

$$
penalty_{loc} = \sum_{l \in L} \sum_{e_i,e_j \text{ at } l, i<j} \sum_{p \in P} y^{loc}_{p,e_i,e_j}
$$

### (O4) Proportional (Fair) Workload Split
Within each priority level $\ell$, worker $p$ should perform a share of the level's total shifts proportional to their availability mass $mass_p$.

Let $level(p) = \ell$. For each level $\ell$:
- $P_\ell = \{p : level(p) = \ell\}$
- $M_\ell = \sum_{p \in P_\ell} mass_p$ (total availability mass)
- $n_p = \sum_{e} x_{p,e}$ (shifts assigned to $p$)
- $T_\ell = \sum_{p \in P_\ell} n_p$ (total shifts for level $\ell$)

Ideal shifts for $p$: $\frac{mass_p}{M_\ell} \cdot T_\ell$.

Deviation (integer-scaled to avoid fractions):
$$
dev_p \ge mass_p \cdot n_p - M_\ell \cdot T_\ell \quad \text{(scaled by } M_\ell\text{)}
$$
$$
dev_p \ge -(mass_p \cdot n_p - M_\ell \cdot T_\ell)
$$

$$
penalty_{fair} = \sum_{p \in P} dev_p
$$

### (O5) Neighbourhood Preference
$$
penalty_{neigh} = \sum_{p,e} \mathbb{1}[neigh_p \ne neigh(loc_e)] \cdot x_{p,e}
$$

---

## Assumptions & Limitations

1. **Travel time**: Sufficient time exists between consecutive time slots; no travel constraints modelled.
2. **Maximum hours**: By nature of the input data, no worker can be overbooked beyond planned hours. If reused with different data, a max-hours constraint would be needed.
3. **Deterministic**: All parameters known in advance; no stochasticity.
4. **Single objective**: Lexicographic weights approximate strict priority ordering. True lexicographic optimisation would require hierarchical solving.

---

## Implementation Notes

- **Variable reduction**: Assignment variables $x_{p,e}$ created only for feasible (worker, event) pairs.
- **Solver**: Google OR-Tools CP-SAT (`ortools.sat.python.cp_model`).
- **Reproducibility**: `synthetic.make_problem(seed=...)` generates anonymised, feasible instances.
- **Outputs**: `Solution.to_json(events)` produces a chronological, JSON-serialisable schedule.