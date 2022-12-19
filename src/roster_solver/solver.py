"""CP-SAT based scheduler.

Hard constraints (always enforced):
    1. Each event is staffed with exactly ``nworkers_needed`` workers.
    2. Each event meets its per-skill minimums.
    3. No worker is double-booked within the same time slot.

Availability and location willingness are enforced *by construction*: an
assignment variable is only created for a (event, worker) pair the worker can
actually serve.

Soft objectives ("inconvenience" terms) are combined into a single weighted sum
``z`` that is minimised. Their default weights (see
:data:`roster_solver.structures.DEFAULT_COEFFICIENTS`) encode the importance
order: same_group > priority > same_location > {proportional_split,
neighbourhood}. Set a coefficient to 0 to disable a term.
"""

from typing import Dict, List, Optional, Tuple

from ortools.sat.python import cp_model

from roster_solver.structures import (
    DEFAULT_COEFFICIENTS,
    Event,
    Person,
    Solution,
    events_by_group_id,
    events_by_location,
)
from roster_solver.utils import groupby_unsorted


class CpSatScheduler:
    def __init__(self, events: List[Event], workers: List[Person]):
        self.events = events
        self.workers = workers
        self._workers_map: Dict[str, Person] = {w.id: w for w in workers}
        self._events_map: Dict[str, Event] = {e.id: e for e in events}

        self.model: Optional[cp_model.CpModel] = None
        # (event_id, worker_id) -> BoolVar
        self.assign: Dict[Tuple[str, str], cp_model.IntVar] = {}
        self.status: Optional[int] = None
        self.solver: Optional[cp_model.CpSolver] = None
        # term name -> linear expression, for post-solve reporting.
        self._objective_terms: Dict[str, object] = {}

    # --- model building ------------------------------------------------------

    def _build_variables(self):
        self.assign = {}
        for e in self.events:
            for w in self.workers:
                if w.is_available(e.date) and w.can_reach(e.location):
                    self.assign[(e.id, w.id)] = self.model.new_bool_var(
                        f"assign[{w.id}|{e.id}]"
                    )

    def _vars_for_event(self, event: Event) -> List[cp_model.IntVar]:
        return [
            self.assign[(event.id, w.id)]
            for w in self.workers
            if (event.id, w.id) in self.assign
        ]

    def _vars_for_worker(self, worker: Person) -> List[cp_model.IntVar]:
        return [
            self.assign[(e.id, worker.id)]
            for e in self.events
            if (e.id, worker.id) in self.assign
        ]

    def _add_constraint_team_size(self):
        for e in self.events:
            self.model.add(sum(self._vars_for_event(e)) == e.nworkers_needed)

    def _add_constraint_skill_minimums(self):
        for e in self.events:
            for skill, nrequired in e.get_required_skills().items():
                qualified = [
                    self.assign[(e.id, w.id)]
                    for w in self.workers
                    if (e.id, w.id) in self.assign and w.has_skill(skill)
                ]
                self.model.add(sum(qualified) >= nrequired)

    def _add_constraint_no_double_booking(self):
        for _slot, events_in_slot in groupby_unsorted(
            self.events, key=lambda e: e.time_slot
        ):
            events_in_slot = list(events_in_slot)
            for w in self.workers:
                conflicting = [
                    self.assign[(e.id, w.id)]
                    for e in events_in_slot
                    if (e.id, w.id) in self.assign
                ]
                if len(conflicting) > 1:
                    self.model.add_at_most_one(conflicting)

    # --- objective (soft "inconvenience" terms) ------------------------------

    def _team_consistency_penalty(self, groups) -> List:
        """Penalise a worker being in some-but-not-all events of a group.

        For each group of events and each event pair:

        - if the worker can serve *both* events, add ``y >= |x_i - x_j|`` (only
          lower bounds are needed since we minimise);
        - if the worker can serve only *one* of the two (partial availability /
          reachability), the missing side is a fixed 0, so ``|x - 0| = x``: being
          scheduled on the event they *can* serve breaks the team and is penalised
          directly.

        Used by both same-group and same-location.
        """
        penalties: List = []
        for key, group_events in groups.items():
            for i in range(len(group_events)):
                for j in range(i + 1, len(group_events)):
                    e_i, e_j = group_events[i], group_events[j]
                    for w in self.workers:
                        xi = self.assign.get((e_i.id, w.id))
                        xj = self.assign.get((e_j.id, w.id))
                        if xi is None and xj is None:
                            continue
                        if xi is None:
                            # Worker cannot serve e_i; scheduling e_j breaks the team.
                            penalties.append(xj)
                        elif xj is None:
                            penalties.append(xi)
                        else:
                            y = self.model.new_bool_var(f"diff[{w.id}|{key}|{i},{j}]")
                            self.model.add(y >= xi - xj)
                            self.model.add(y >= xj - xi)
                            penalties.append(y)
        return penalties

    def _pen_same_group(self) -> List[cp_model.IntVar]:
        return self._team_consistency_penalty(events_by_group_id(self.events))

    def _pen_same_location(self) -> List[cp_model.IntVar]:
        return self._team_consistency_penalty(events_by_location(self.events))

    def _pen_neighbourhood(self):
        """Penalise assigning a worker outside their residence neighbourhood."""
        terms = []
        for (event_id, worker_id), var in self.assign.items():
            w = self._workers_map[worker_id]
            e = self._events_map[event_id]
            if w.neighbourhood != e.location.neighbourhood:
                terms.append(var)
        return terms

    def _pen_priority(self):
        """Penalise scheduling lower-priority workers.

        Cost per assignment is ``max_level - priority_level`` so that, all else
        equal, higher-priority workers are preferred.
        """
        if not self.workers:
            return []
        max_level = max(w.priority_level for w in self.workers)
        terms = []
        for (event_id, worker_id), var in self.assign.items():
            w = self._workers_map[worker_id]
            weight = max_level - w.priority_level
            if weight:
                terms.append(weight * var)
        return terms

    def _pen_proportional_split(self) -> List[cp_model.IntVar]:
        """Penalise deviation from a fair, availability-weighted workload split.

        Within each priority level, worker ``w`` should ideally do a share of the
        level's total shifts proportional to their availability "mass". We add
        ``dev_w >= |mass * n_w - navail_w * total|`` (integer-scaled to avoid
        fractions) and sum the deviations.
        """
        penalties: List[cp_model.IntVar] = []
        for level, level_workers in groupby_unsorted(
            self.workers, key=lambda w: w.priority_level
        ):
            level_workers = list(level_workers)
            mass = sum(w.get_n_available_dates() for w in level_workers)
            if mass == 0:
                continue
            n_vars = {w.id: self._vars_for_worker(w) for w in level_workers}
            total = sum((v for vs in n_vars.values() for v in vs))
            for w in level_workers:
                n_w = sum(n_vars[w.id])
                expr = mass * n_w - w.get_n_available_dates() * total
                dev = self.model.new_int_var(0, mass * len(self.events), f"dev[{w.id}]")
                self.model.add(dev >= expr)
                self.model.add(dev >= -expr)
                penalties.append(dev)
        return penalties

    def _add_objective(self, coefficients: Dict[str, int]):
        """Build and register the weighted inconvenience objective ``z``."""
        builders = {
            "same_group": self._pen_same_group,
            "priority": self._pen_priority,
            "same_location": self._pen_same_location,
            "proportional_split": self._pen_proportional_split,
            "neighbourhood": self._pen_neighbourhood,
        }

        self._objective_terms = {}
        z_terms = []
        for name, build in builders.items():
            coef = coefficients.get(name, 0)
            if not coef:
                continue
            term = sum(build())
            self._objective_terms[name] = term
            z_terms.append(coef * term)

        if z_terms:
            self.model.minimize(sum(z_terms))

    # --- solving -------------------------------------------------------------

    def solve(
        self,
        coefficients: Optional[Dict[str, int]] = None,
        max_seconds: float = 30.0,
    ) -> Optional[Solution]:
        if coefficients is None:
            coefficients = DEFAULT_COEFFICIENTS

        self.model = cp_model.CpModel()

        self._build_variables()
        self._add_constraint_team_size()
        self._add_constraint_skill_minimums()
        self._add_constraint_no_double_booking()
        self._add_objective(coefficients)

        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = max_seconds
        self.status = self.solver.solve(self.model)

        if self.status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return self._extract_solution()
        return None

    def is_feasible(self) -> bool:
        return self.status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def status_name(self) -> str:
        if self.solver is None or self.status is None:
            return "NOT_SOLVED"
        return self.solver.status_name(self.status)

    def _extract_solution(self) -> Solution:
        solution = Solution()
        for (event_id, worker_id), var in self.assign.items():
            if self.solver.value(var):
                solution.schedule_worker(worker_id, event_id)
        return solution

    def objective_value(self) -> Optional[float]:
        """Total inconvenience ``z`` of the current solution, if any."""
        if not self.is_feasible():
            return None
        return self.solver.objective_value

    def objective_breakdown(self) -> Dict[str, int]:
        """Per-term (unweighted) penalty values for the current solution."""
        if not self.is_feasible():
            return {}
        return {
            name: (term if isinstance(term, int) else int(self.solver.value(term)))
            for name, term in self._objective_terms.items()
        }


def _example_problem():
    """A small, self-contained, anonymised example for the CLI demo."""
    from datetime import date

    from roster_solver.structures import Event, Location, Person

    ALL = {"mech", "first_aid", "leader"}
    site = Location("site_1", "district_a")
    days = {date(2023, 4, d) for d in (12, 13, 14, 15)}

    workers = [
        Person(f"worker_{i:02d}", ALL, priority_level=1, neighbourhood="district_a",
               availabilities=days)
        for i in range(1, 7)
    ]
    events = [
        Event("group_a", site, date(2023, 4, 12), "am", 5),
        Event("group_a", site, date(2023, 4, 12), "pm", 5),
        Event("group_b", site, date(2023, 4, 13), "am", 5),
        Event("group_b", site, date(2023, 4, 14), "am", 5),
    ]
    return events, workers


if __name__ == "__main__":
    events, workers = _example_problem()
    scheduler = CpSatScheduler(events, workers)
    sol = scheduler.solve()
    if sol is None:
        print(f"No feasible schedule found (status={scheduler.status_name()}).")
    else:
        print(sol.to_json(events))
