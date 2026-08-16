# Roster-Solver - an Event Schedule Solution

Assigns a pool of workers to a list of events (bike-riding and road safety training sessions) subject to a set of constraints, using Google OR-Tools **CP-SAT**.

See [`problem_statement.md`](problem_statement.md) for the full model.

## Data

Real data is not provided for obvious reason, but this codebase include 

## Model

### Hard constraints

1. Each event is staffed with exactly `nworkers_needed` workers.
2. Each event meets its per-skill minimums (default: 2 mech, 2 first_aid, 1 leader).
3. No worker is double-booked in the same time slot.

Availability and location willingness are enforced by construction (a worker is
only assignable to events they can actually serve). 

Disclaimer: By nature of the data being fed, it is impossible to overbook a worker. As such, no constraint enforcing a target or maximum number of hours is implemented. Using this codebase with different data would require adding this constraint / objective.

### Soft objectives (minimise inconvenience `z`)

All preferences are combined into a single weighted sum that is minimised. The
default weights encode their importance order (higher wins); pass your own via
`solve(coefficients=...)`, and set a weight to `0` to disable a term.

| Term | Default weight | Meaning |
|------|---------------:|---------|
| `same_group` | 100000 | Same team across events of one class (`group_id`); also penalises workers only *partially* available across the group's events |
| `priority` | 10000 | Prefer scheduling higher-`priority_level` workers |
| `same_location` | 1000 | Same team across events at one location (school); partial availability penalised as above |
| `proportional_split` | 1 | Fair, availability-weighted workload within a level |
| `neighbourhood` | 1 | Prefer workers residing in the event's neighbourhood |

After solving, `CpSatScheduler.objective_value()` returns `z` and
`objective_breakdown()` returns the per-term (unweighted) penalties.

## Codebase

### Layout

```
src/roster_solver/
  structures.py   # Location, Event, Person, Solution + constants
  solver.py       # CpSatScheduler
  synthetic.py    # seeded generator of anonymised (events, workers) problems
  plots.py        # pure dict-in / Figure-out plotting helpers
  utils.py        # bidict, groupby_unsorted
notebooks/
  visualisations.ipynb   # run solver experiments, call plots, save figures/
test/             # pytest suite (scenarios live in test/conftest.py fixtures)
```

## Visualisations

`notebooks/visualisations.ipynb` explores the solver through four figures
(regenerated headlessly with):

```
PYTHONPATH=src uv run python -m nbconvert --to notebook --execute notebooks/visualisations.ipynb --inplace
```

1. **Roster grid** — worker × time-slot heatmap of a solved schedule
   (team consistency, no double-booking).
2. **Scaling** — wall time and model size vs total staffing demand; where
   CP-SAT stops proving optimality within a time budget.
3. **Gap decay** — incumbent vs proven bound over one long solve (balanced
   weights), showing CP-SAT's "good solution fast, then tighten" behaviour.
4. **Fairness** — workload distribution with and without the
   `proportional_split` objective term.

The plotting code is deliberately solver-free: `synthetic.make_problem`
provides reproducible scenarios, the notebook runs the solver and assembles
plain dicts, and `roster_solver.plots` renders them to `figures/*.png`.

### How to run

Start by setuping your environment with `uv sync`. Then, run trivial example with:

```
PYTHONPATH=src:. uv run python -m roster_solver.solver
```


### Test

(`pytest` already sets the path via `pyproject.toml`, so tests need no `PYTHONPATH`.)

```
uv run pytest
```

## Analysis

TODO
