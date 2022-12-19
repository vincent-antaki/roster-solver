from datetime import date as dt

from roster_solver.solver import CpSatScheduler
from roster_solver.structures import Event, Location, Person

from helpers import assert_valid_schedule


class TestFeasibleScenarios:
    def test_simple(self, simple_scenario):
        events, workers = simple_scenario
        scheduler = CpSatScheduler(events, workers)
        sol = scheduler.solve()
        assert sol is not None
        assert_valid_schedule(scheduler, sol)

    def test_skill_constrained(self, skill_constrained_scenario):
        events, workers = skill_constrained_scenario
        scheduler = CpSatScheduler(events, workers)
        sol = scheduler.solve()
        assert sol is not None
        assert_valid_schedule(scheduler, sol)
        # The filler has no scarce skill; the 4 specialists must all be chosen.
        team = set(sol.get_workers_for_event(events[0]))
        assert team == {"worker_01", "worker_02", "worker_03", "worker_04"}

    def test_double_booking_partitions_team(self, double_booking_scenario):
        events, workers = double_booking_scenario
        scheduler = CpSatScheduler(events, workers)
        sol = scheduler.solve()
        assert sol is not None
        assert_valid_schedule(scheduler, sol)
        t1 = set(sol.get_workers_for_event(events[0]))
        t2 = set(sol.get_workers_for_event(events[1]))
        assert t1.isdisjoint(t2)


class TestInfeasibleScenarios:
    def test_missing_leader_skill(self, infeasible_scenario):
        events, workers = infeasible_scenario
        scheduler = CpSatScheduler(events, workers)
        sol = scheduler.solve()
        assert sol is None
        assert not scheduler.is_feasible()

    def test_not_enough_available_workers(self):
        # 5 needed but only 4 workers exist.
        loc = Location("site_1", "district_a")
        workers = [
            Person(f"worker_{i:02d}", {"mech", "first_aid", "leader"}, 1, "district_a")
            for i in range(1, 5)
        ]
        events = [Event("group_a", loc, dt(2023, 4, 12), "am", 5)]
        scheduler = CpSatScheduler(events, workers)
        assert scheduler.solve() is None


class TestConstraintsEnforced:
    def test_unavailable_worker_never_scheduled(self):
        loc = Location("site_1", "district_a")
        day = dt(2023, 4, 12)
        available = [
            Person(f"worker_{i:02d}", {"mech", "first_aid", "leader"}, 1, "district_a",
                   availabilities={day})
            for i in range(1, 5)
        ]
        # This worker is only available on a different day.
        unavailable = Person(
            "worker_ghost", {"mech", "first_aid", "leader"}, 1, "district_a",
            availabilities={dt(2023, 4, 13)},
        )
        events = [Event("group_a", loc, day, "am", 4)]
        scheduler = CpSatScheduler(events, available + [unavailable])
        sol = scheduler.solve()
        assert sol is not None
        assert "worker_ghost" not in sol.get_workers_for_event(events[0])


class TestObjectives:
    def test_same_group_keeps_consistent_teams(self, group_split_scenario):
        events, workers = group_split_scenario
        scheduler = CpSatScheduler(events, workers)
        sol = scheduler.solve(coefficients={"same_group": 1})
        assert sol is not None
        assert_valid_schedule(scheduler, sol)
        # Events (0,1)=group_a, (2,3)=group_b, (4,5)=group_c share a team.
        for i, j in [(0, 1), (2, 3), (4, 5)]:
            assert set(sol.get_workers_for_event(events[i])) == set(
                sol.get_workers_for_event(events[j])
            )

    def test_proportional_split_by_availability(self, group_split_scenario):
        events, workers = group_split_scenario
        scheduler = CpSatScheduler(events, workers)
        sol = scheduler.solve(coefficients={"proportional_split": 1})
        assert sol is not None
        # High-availability workers carry 4 shifts, the others 2.
        assert len(sol.get_events_for_worker("worker_01")) == 4
        assert len(sol.get_events_for_worker("worker_02")) == 4
        assert len(sol.get_events_for_worker("worker_03")) == 2
        assert len(sol.get_events_for_worker("worker_04")) == 2

    def test_partial_availability_worker_left_out(self, partial_availability_scenario):
        events, workers = partial_availability_scenario
        scheduler = CpSatScheduler(events, workers)
        sol = scheduler.solve(coefficients={"same_group": 1})
        assert sol is not None
        # Partially-available worker would break the team, so is avoided.
        assert sol.get_events_for_worker("partial") == []
        assert scheduler.objective_breakdown()["same_group"] == 0

    def test_partial_availability_incurs_penalty_when_forced(self):
        d1, d2 = dt(2023, 4, 12), dt(2023, 4, 13)
        # Each event must draw a day-locked worker, so the teams cannot match.
        workers = [
            Person("full_01", {"mech", "first_aid", "leader"}, 1, "district_a",
                   availabilities={d1, d2}),
            Person("only_d1", {"mech", "first_aid", "leader"}, 1, "district_a",
                   availabilities={d1}),
            Person("only_d2", {"mech", "first_aid", "leader"}, 1, "district_a",
                   availabilities={d2}),
        ]
        loc = Location("site_1", "district_a")
        events = [
            Event("group_a", loc, d1, "am", 2),
            Event("group_a", loc, d2, "am", 2),
        ]
        scheduler = CpSatScheduler(events, workers)
        sol = scheduler.solve(coefficients={"same_group": 1})
        assert sol is not None
        # only_d1 (on e1) and only_d2 (on e2) are each partially available => 2.
        assert scheduler.objective_breakdown()["same_group"] == 2

    def test_neighbourhood_prefers_local_workers(self, neighbourhood_scenario):
        events, workers = neighbourhood_scenario
        scheduler = CpSatScheduler(events, workers)
        sol = scheduler.solve(coefficients={"neighbourhood": 1})
        assert sol is not None
        team = sol.get_workers_for_event(events[0])
        assert all(wid.startswith("local_") for wid in team)

    def test_priority_leaves_out_low_level_worker(self, priority_scenario):
        events, workers = priority_scenario
        scheduler = CpSatScheduler(events, workers)
        sol = scheduler.solve(coefficients={"priority": 1})
        assert sol is not None
        assert "worker_low" not in sol.get_workers_for_event(events[0])

    def test_disabled_objective_has_no_z(self, simple_scenario):
        events, workers = simple_scenario
        scheduler = CpSatScheduler(events, workers)
        sol = scheduler.solve(coefficients={})  # all terms off
        assert sol is not None
        assert scheduler.objective_breakdown() == {}

    def test_breakdown_reports_enabled_terms(self, group_split_scenario):
        events, workers = group_split_scenario
        scheduler = CpSatScheduler(events, workers)
        sol = scheduler.solve()
        assert sol is not None
        breakdown = scheduler.objective_breakdown()
        assert set(breakdown) == set(
            ["same_group", "priority", "same_location",
             "proportional_split", "neighbourhood"]
        )
        # Consistent teams => zero same-group penalty.
        assert breakdown["same_group"] == 0


class TestSolutionSerialization:
    def test_to_dict_is_json_ready(self, simple_scenario):
        events, workers = simple_scenario
        scheduler = CpSatScheduler(events, workers)
        sol = scheduler.solve()
        assert sol is not None

        data = sol.to_dict(events)
        assert set(data.keys()) == {"events"}
        assert len(data["events"]) == len(events)

        first = data["events"][0]
        assert set(first.keys()) >= {
            "event_id", "group_id", "date", "during", "location",
            "nworkers_needed", "workers",
        }
        assert len(first["workers"]) == first["nworkers_needed"]

        # Ordered chronologically (am before pm on the same day).
        keys = [(e["date"], 0 if e["during"] == "am" else 1) for e in data["events"]]
        assert keys == sorted(keys)

    def test_to_json_roundtrips(self, simple_scenario):
        import json

        events, workers = simple_scenario
        scheduler = CpSatScheduler(events, workers)
        sol = scheduler.solve()
        assert sol is not None

        text = sol.to_json(events)
        assert json.loads(text) == sol.to_dict(events)
