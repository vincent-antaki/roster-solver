"""Deterministic synthetic problem generator.

Real roster data is intentionally not shipped with this repository (see the
README), so the visualisations and demos need anonymised, reproducible
problems to run on. ``make_problem`` builds a complete ``(events, workers)``
pair from a handful of knobs and a seed.

Feasibility is verified before returning (unless ``ensure_feasible=False``):
the problem is solved once with all soft objectives disabled and regenerated
with a fresh seed if no schedule exists, so callers can rely on the result
being solvable.
"""

from __future__ import annotations

import datetime as _dt
import random
from typing import Dict, List, Sequence, Tuple

from roster_solver.structures import Event, Location, Person, SKILLS

#: First date in the synthetic calendar; slots then fill consecutive days.
BASE_DATE = _dt.date(2023, 4, 10)

#: Two half-day slots per day.
SLOTS_PER_DAY = 2
DURATIONS = ("am", "pm")

#: Maximum regeneration attempts before giving up on a feasible problem.
MAX_FEASIBLE_ATTEMPTS = 30

#: Time budget for the feasibility pre-check solve.
FEASIBLE_CHECK_SECONDS = 5.0


def slot_label(index: int) -> Tuple[_dt.date, str]:
    """Return the (date, during) pair for a global slot index."""
    day = BASE_DATE + _dt.timedelta(days=index // SLOTS_PER_DAY)
    return day, DURATIONS[index % SLOTS_PER_DAY]


def make_problem(
    n_workers: int,
    n_events: int,
    workers_per_event: int = 5,
    *,
    skill_density: float = 0.7,
    availability_density: float = 0.85,
    reachability_density: float = 0.9,
    group_sizes: Sequence[int] = (2, 3, 4),
    n_neighbourhoods: int = 3,
    n_locations: int = 4,
    n_levels: int = 3,
    seed: int = 0,
    ensure_feasible: bool = True,
) -> Tuple[List[Event], List[Person]]:
    """Build a seeded, feasible (events, workers) scheduling problem.

    Events are grouped into "classes" (``group_id``) that span consecutive
    time slots; several groups share each location so the same-group and
    same-location objectives are distinct. Each event needs
    ``workers_per_event`` workers and inherits the default per-skill minimums.

    Availability, reachability and skills are drawn per worker from the given
    densities, so the problem gets tighter as any density drops. When
    ``ensure_feasible`` is set, the problem is re-generated with a new seed
    until the solver (with all soft objectives disabled) finds a schedule.
    """
    if n_events < 1:
        raise ValueError("n_events must be >= 1")
    if n_workers < 1:
        raise ValueError("n_workers must be >= 1")
    if workers_per_event < 1:
        raise ValueError("workers_per_event must be >= 1")

    params = dict(
        n_workers=n_workers,
        n_events=n_events,
        workers_per_event=workers_per_event,
        skill_density=skill_density,
        availability_density=availability_density,
        reachability_density=reachability_density,
        group_sizes=tuple(group_sizes),
        n_neighbourhoods=n_neighbourhoods,
        n_locations=n_locations,
        n_levels=n_levels,
    )

    if not ensure_feasible:
        return _build(random.Random(seed), params)

    from roster_solver.solver import CpSatScheduler

    for attempt in range(MAX_FEASIBLE_ATTEMPTS):
        rng = random.Random(seed * 7919 + attempt)
        events, workers = _build(rng, params)
        scheduler = CpSatScheduler(events, workers)
        if scheduler.solve(coefficients={}, max_seconds=FEASIBLE_CHECK_SECONDS) is not None:
            return events, workers

    raise RuntimeError(
        f"could not generate a feasible problem with n_events={n_events}, "
        f"n_workers={n_workers} after {MAX_FEASIBLE_ATTEMPTS} attempts"
    )


def _build(rng: random.Random, params: Dict) -> Tuple[List[Event], List[Person]]:
    n_workers = params["n_workers"]
    n_events = params["n_events"]
    workers_per_event = params["workers_per_event"]
    n_neighbourhoods = params["n_neighbourhoods"]
    n_locations = params["n_locations"]
    n_levels = params["n_levels"]

    locations = [
        Location(f"site_{i:02d}", f"district_{i % n_neighbourhoods}")
        for i in range(n_locations)
    ]

    group_sizes = list(params["group_sizes"])
    groups = _partition_groups(n_events, group_sizes, rng)

    events: List[Event] = []
    slot = 0
    for gidx, size in enumerate(groups):
        location = locations[gidx % len(locations)]
        for _ in range(size):
            date, during = slot_label(slot)
            events.append(
                Event(f"group_{gidx:02d}", location, date, during, workers_per_event)
            )
            slot += 1

    all_dates = sorted({e.date for e in events})
    workers: List[Person] = []
    for w in range(n_workers):
        skills = {s for s in SKILLS if rng.random() < params["skill_density"]}
        if not skills:
            skills = {rng.choice(sorted(SKILLS))}

        reachable = [
            loc for loc in locations if rng.random() < params["reachability_density"]
        ]
        if not reachable:
            reachable = [rng.choice(locations)]

        available = {
            d for d in all_dates if rng.random() < params["availability_density"]
        }
        if not available:
            available = {rng.choice(all_dates)}

        workers.append(
            Person(
                f"worker_{w:03d}",
                skills,
                rng.randrange(n_levels),
                f"district_{rng.randrange(n_neighbourhoods)}",
                can_go=reachable,
                availabilities=available,
            )
        )

    return events, workers


def _partition_groups(
    n_events: int, sizes: List[int], rng: random.Random
) -> List[int]:
    """Split ``n_events`` into group sizes drawn from ``sizes``."""
    groups: List[int] = []
    remaining = n_events
    while remaining > 0:
        size = min(rng.choice(sizes), remaining)
        groups.append(size)
        remaining -= size
    return groups
