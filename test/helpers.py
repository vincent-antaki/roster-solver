"""Shared assertion helpers for scheduler tests."""

from roster_solver.solver import CpSatScheduler
from roster_solver.structures import Solution


def assert_valid_schedule(scheduler: CpSatScheduler, solution: Solution):
    """Assert every hard constraint holds for the produced schedule."""
    workers_map = scheduler._workers_map

    # 1. Every event has exactly the required team size.
    for event in scheduler.events:
        worker_ids = solution.get_workers_for_event(event)
        assert len(worker_ids) == event.nworkers_needed, (
            f"event {event.id} has {len(worker_ids)} workers, "
            f"expected {event.nworkers_needed}"
        )

        # 2. Skill minimums are met.
        for skill, nrequired in event.get_required_skills().items():
            got = sum(1 for wid in worker_ids if workers_map[wid].has_skill(skill))
            assert got >= nrequired, (
                f"event {event.id} has {got} '{skill}' workers, expected >= {nrequired}"
            )

        # 3a. Only available & reachable workers are assigned.
        for wid in worker_ids:
            w = workers_map[wid]
            assert w.is_available(event.date), f"{wid} not available on {event.date}"
            assert w.can_reach(event.location), f"{wid} cannot reach {event.location}"

    # 3b. No worker is double-booked within a time slot.
    for w in scheduler.workers:
        slots = [
            e.time_slot
            for e in scheduler.events
            if solution.is_worker_scheduled(w.id, e.id)
        ]
        assert len(slots) == len(set(slots)), f"{w.id} is double-booked: {slots}"

