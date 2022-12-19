"""Core data structures for the event-scheduling problem.

This module unifies (and fixes) the two divergent models that previously lived
in ``structures.py`` and ``old/main.py``.

Key design choices (v1):
    - Worker skills are a ``set[str]`` validated against a known-skills registry
      (:data:`SKILLS`) rather than a fixed set of boolean flags.
    - Skill requirements per event are data-driven (:data:`REQUIRED_SKILLS_PER_EVENT`)
      and can be overridden per :class:`Event`.
    - ``Location`` carries optional ``coords`` so distance-based objectives can be
      added later without a schema change (unused in v1).
"""

# Standard lib imports
import datetime
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Union

from roster_solver.utils import bidict

# --- Constants ---------------------------------------------------------------

#: Known-skills registry. Values used across events/workers should live here.
SKILLS: Set[str] = {"mech", "first_aid", "leader"}

#: Default minimum number of workers with a given skill required at each event.
#: An :class:`Event` may override this via ``required_skills``.
REQUIRED_SKILLS_PER_EVENT: Dict[str, int] = {"mech": 2, "first_aid": 2, "leader": 1}

#: Fallback "mass" used when a worker is available for *any* date.
MAX_DATE_AVAILABLE: int = 45

#: Default weights for the soft-objective (inconvenience) terms, ordered by
#: importance: same_group > priority > same_location > {proportional_split,
#: neighbourhood} (the last two are tied). The large gaps approximate a
#: lexicographic priority; set a coefficient to 0 to disable a term.
DEFAULT_COEFFICIENTS: Dict[str, int] = {
    "same_group": 100_000,
    "priority": 10_000,
    "same_location": 1_000,
    "proportional_split": 1,
    "neighbourhood": 1,
}


# --- Data classes ------------------------------------------------------------


@dataclass(frozen=True)
class Location:
    """A place where events happen.

    ``coords`` is optional and unused in v1; it exists so distance-based
    optimisation can be introduced later without changing the schema.
    """

    name: str
    neighbourhood: str
    coords: Optional[Tuple[float, float]] = None

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return f"{self.name}({self.neighbourhood})"


@dataclass
class Event:
    """A single scheduled activity requiring a team of workers."""

    group_id: str
    location: Location
    date: datetime.date
    during: str  # 'am' | 'pm'
    nworkers_needed: int
    #: Optional per-event skill minimums; falls back to the global default.
    required_skills: Optional[Dict[str, int]] = None

    id: str = field(init=False)

    def __post_init__(self):
        assert self.during in ("am", "pm"), f"invalid 'during': {self.during!r}"
        self.id = f"{self.date}:{self.during}:{self.location.name}:{self.group_id}"

    @property
    def time_slot(self) -> Tuple[datetime.date, str]:
        """The (date, during) pair used to detect double-booking conflicts."""
        return (self.date, self.during)

    def get_required_skills(self) -> Dict[str, int]:
        return self.required_skills if self.required_skills is not None else REQUIRED_SKILLS_PER_EVENT

    def __hash__(self):
        return hash(self.id)


@dataclass
class Person:
    """A worker that can be assigned to events."""

    id: str
    skills: Set[str]
    priority_level: int
    neighbourhood: str
    #: ``True`` means willing to go anywhere, else the set of reachable locations.
    can_go: Union[bool, Set[Location]] = True
    #: ``True`` means always available, else the set of available dates.
    availabilities: Union[bool, Set[datetime.date]] = True

    def __post_init__(self):
        self.skills = set(self.skills)
        unknown = self.skills - SKILLS
        assert not unknown, f"unknown skill(s) for {self.id!r}: {unknown}"
        if self.can_go is not True:
            self.can_go = set(self.can_go)
        if self.availabilities is not True:
            self.availabilities = set(self.availabilities)

    def has_skill(self, skill: str) -> bool:
        return skill in self.skills

    def is_available(self, date: datetime.date) -> bool:
        return self.availabilities is True or date in self.availabilities

    def can_reach(self, location: Location) -> bool:
        return self.can_go is True or location in self.can_go

    def get_n_available_dates(self) -> int:
        if self.availabilities is True:
            return MAX_DATE_AVAILABLE
        return len(self.availabilities)

    def __hash__(self):
        return hash(self.id)


class Solution:
    """A schedule: a bidirectional mapping between workers and events."""

    def __init__(self):
        self.worker_schedule_map = bidict()

    def add_schedule(self, events: List[Event], scheduling: List[List[Person]]):
        assert len(events) == len(scheduling)
        for event, team in zip(events, scheduling):
            for worker in team:
                self.schedule_worker(worker.id, event.id)
        return self

    def schedule_worker(self, worker, event):
        self.worker_schedule_map.add_item(worker, event)

    def is_worker_scheduled(self, worker, event) -> bool:
        return event in self.worker_schedule_map.get(worker, [])

    def get_workers_for_event(self, event) -> List[str]:
        if isinstance(event, Event):
            event = event.id
        return self.worker_schedule_map.inverse.get(event, [])

    def get_events_for_worker(self, worker) -> List[str]:
        if isinstance(worker, Person):
            worker = worker.id
        return self.worker_schedule_map.get(worker, [])

    def to_dict(self, events: List[Event]) -> Dict:
        """Return a JSON-serialisable view of the schedule.

        ``events`` is required to enrich each entry with its date, time slot and
        location. Entries are ordered chronologically (am before pm).
        """

        def sort_key(e: Event):
            return e.date.toordinal() + (0.5 if e.during == "pm" else 0.0)

        scheduled = [
            {
                "event_id": e.id,
                "group_id": e.group_id,
                "date": e.date.isoformat(),
                "during": e.during,
                "location": {
                    "name": e.location.name,
                    "neighbourhood": e.location.neighbourhood,
                },
                "nworkers_needed": e.nworkers_needed,
                "workers": sorted(self.get_workers_for_event(e)),
            }
            for e in sorted(events, key=sort_key)
        ]
        return {"events": scheduled}

    def to_json(self, events: List[Event], indent: int = 2) -> str:
        """Return the schedule as a pretty-printed JSON string."""
        return json.dumps(self.to_dict(events), indent=indent, ensure_ascii=False)


# --- Grouping helpers --------------------------------------------------------


def events_by_group_id(events: List[Event]) -> Dict[str, List[Event]]:
    """Group events by their ``group_id`` (a "class")."""
    groups: Dict[str, List[Event]] = {}
    for e in events:
        groups.setdefault(e.group_id, []).append(e)
    return groups


def events_by_location(events: List[Event]) -> Dict[Location, List[Event]]:
    """Group events by their :class:`Location` (a "school")."""
    groups: Dict[Location, List[Event]] = {}
    for e in events:
        groups.setdefault(e.location, []).append(e)
    return groups
