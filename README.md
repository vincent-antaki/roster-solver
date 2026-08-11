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

## Layout

```
src/roster_solver/
  structures.py   # Location, Event, Person, Solution + constants
  solver.py       # CpSatScheduler
  utils.py        # bidict, groupby_unsorted
test/             # pytest suite (scenarios live in test/conftest.py fixtures)
```

## Setup

```
uv sync
```

## Run the example

```
PYTHONPATH=src:. uv run python -m roster_solver.solver
```

(`pytest` already sets the path via `pyproject.toml`, so tests need no `PYTHONPATH`.)

## Test

```
uv run pytest
```
