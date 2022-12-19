"""Shared, anonymised problem scenarios exposed as pytest fixtures.

Each fixture returns an ``(events, workers)`` tuple. Names are deliberately
synthetic (``worker_01``, ``district_a``, ``site_1``) to avoid leaking any real
roster data.
"""

from datetime import date as dt

import pytest

from roster_solver.structures import Event, Location, Person

# All three skills; convenient for "fully-trained" workers in fixtures.
ALL_SKILLS = {"mech", "first_aid", "leader"}

# A handful of generic locations across districts (name, neighbourhood).
LOCATIONS = [
    Location("site_1", "district_a"),
    Location("site_2", "district_b"),
    Location("site_3", "district_c"),
]


@pytest.fixture
def simple_scenario():
    """A comfortably feasible week: 6 events, 6 fully-trained workers."""
    availabilities = {dt(2023, 4, d) for d in (12, 13, 14, 15)}

    workers = [
        Person(f"worker_{i:02d}", ALL_SKILLS, priority_level=level,
               neighbourhood=district, availabilities=availabilities)
        for i, (level, district) in enumerate(
            [
                (1, "district_a"),
                (0, "district_a"),
                (1, "district_b"),
                (3, "district_b"),
                (3, "district_c"),
                (2, "district_c"),
            ],
            start=1,
        )
    ]

    events = [
        Event("group_a", LOCATIONS[0], dt(2023, 4, 12), "am", 5),
        Event("group_a", LOCATIONS[0], dt(2023, 4, 12), "pm", 5),
        Event("group_c", LOCATIONS[0], dt(2023, 4, 13), "am", 5),
        Event("group_b", LOCATIONS[2], dt(2023, 4, 14), "am", 5),
        Event("group_b", LOCATIONS[2], dt(2023, 4, 14), "pm", 5),
        Event("group_c", LOCATIONS[0], dt(2023, 4, 15), "am", 5),
    ]
    return events, workers


@pytest.fixture
def skill_constrained_scenario():
    """Feasible only if the skill minimums are respected.

    Exactly enough specialists exist to satisfy 2x mech, 2x first_aid, 1x leader
    on a single 4-worker event.
    """
    day = dt(2023, 4, 12)

    workers = [
        Person("worker_01", {"mech"}, 1, "district_a"),
        Person("worker_02", {"mech", "leader"}, 1, "district_a"),
        Person("worker_03", {"first_aid"}, 1, "district_a"),
        Person("worker_04", {"first_aid"}, 1, "district_a"),
        # A filler worker with no scarce skill, to prove selection is by skill.
        Person("worker_05", set(), 1, "district_a"),
    ]

    events = [Event("group_a", LOCATIONS[0], day, "am", 4)]
    return events, workers


@pytest.fixture
def infeasible_scenario():
    """No worker has the 'leader' skill, so the leader minimum cannot be met."""
    day = dt(2023, 4, 12)

    workers = [
        Person(f"worker_{i:02d}", {"mech", "first_aid"}, 1, "district_a")
        for i in range(1, 6)
    ]

    events = [Event("group_a", LOCATIONS[0], day, "am", 5)]
    return events, workers


@pytest.fixture
def double_booking_scenario():
    """Two events in the same time slot; teams must be disjoint.

    8 workers, two simultaneous events needing 4 each => full partition.
    """
    day = dt(2023, 4, 12)
    workers = [
        Person(f"worker_{i:02d}", ALL_SKILLS, 1, "district_a") for i in range(1, 9)
    ]
    events = [
        Event("group_a", LOCATIONS[0], day, "am", 4),
        Event("group_b", LOCATIONS[1], day, "am", 4),
    ]
    return events, workers


@pytest.fixture
def group_split_scenario():
    """Exercises same-group teams and proportional workload split together.

    Two workers are available all week; two only for the first two days. With
    availability-weighted fairness (mass 4/4/2/2), the high-availability pair
    should end up with 4 shifts each and the others 2 each -- while every class
    (group) keeps a consistent team.
    """
    avail_full = {dt(2023, 4, d) for d in (12, 13, 14, 15)}
    avail_partial = {dt(2023, 4, d) for d in (12, 13)}

    workers = [
        Person("worker_01", ALL_SKILLS, 1, "district_a", availabilities=avail_full),
        Person("worker_02", ALL_SKILLS, 1, "district_a", availabilities=avail_full),
        Person("worker_03", ALL_SKILLS, 1, "district_b", availabilities=avail_partial),
        Person("worker_04", ALL_SKILLS, 1, "district_b", availabilities=avail_partial),
    ]

    events = [
        Event("group_a", LOCATIONS[0], dt(2023, 4, 12), "am", 2),
        Event("group_a", LOCATIONS[0], dt(2023, 4, 12), "pm", 2),
        Event("group_b", LOCATIONS[0], dt(2023, 4, 13), "am", 2),
        Event("group_b", LOCATIONS[0], dt(2023, 4, 13), "pm", 2),
        Event("group_c", LOCATIONS[0], dt(2023, 4, 14), "am", 2),
        Event("group_c", LOCATIONS[0], dt(2023, 4, 14), "pm", 2),
    ]
    return events, workers


@pytest.fixture
def neighbourhood_scenario():
    """More candidates than needed; local (district_a) workers are preferable.

    One event in district_a needs 5 workers; 5 local and 5 non-local
    fully-trained workers are available.
    """
    day = dt(2023, 4, 12)
    locals_ = [
        Person(f"local_{i:02d}", ALL_SKILLS, 1, "district_a") for i in range(1, 6)
    ]
    non_locals = [
        Person(f"far_{i:02d}", ALL_SKILLS, 1, "district_b") for i in range(1, 6)
    ]
    events = [Event("group_a", LOCATIONS[0], day, "am", 5)]
    return events, locals_ + non_locals


@pytest.fixture
def partial_availability_scenario():
    """A group spanning two days; one worker is only available on the first.

    Two fully-available workers can staff both events consistently, so the
    partially-available worker should be left out to avoid breaking the team.
    """
    d1, d2 = dt(2023, 4, 12), dt(2023, 4, 13)
    workers = [
        Person("full_01", ALL_SKILLS, 1, "district_a", availabilities={d1, d2}),
        Person("full_02", ALL_SKILLS, 1, "district_a", availabilities={d1, d2}),
        Person("partial", ALL_SKILLS, 1, "district_a", availabilities={d1}),
    ]
    events = [
        Event("group_a", LOCATIONS[0], d1, "am", 2),
        Event("group_a", LOCATIONS[0], d2, "am", 2),
    ]
    return events, workers


@pytest.fixture
def priority_scenario():
    """A level-0 worker should be left out when higher-level workers suffice."""
    day = dt(2023, 4, 12)
    high = [
        Person(f"worker_{i:02d}", ALL_SKILLS, 1, "district_a") for i in range(1, 6)
    ]
    low = Person("worker_low", ALL_SKILLS, 0, "district_a")
    events = [Event("group_a", LOCATIONS[0], day, "am", 5)]
    return events, high + [low]
