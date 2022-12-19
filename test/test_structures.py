from datetime import date as dt

import pytest

from roster_solver.structures import (
    Event,
    Location,
    Person,
    Solution,
    MAX_DATE_AVAILABLE,
    REQUIRED_SKILLS_PER_EVENT,
)

LOC = Location("school-a", "Rosemont")
LOC2 = Location("school-b", "Plateau")


class TestPerson:
    def test_rejects_unknown_skill(self):
        with pytest.raises(AssertionError):
            Person("x", {"telepathy"}, 1, "Rosemont")

    def test_available_everywhere_by_default(self):
        p = Person("x", {"mech"}, 1, "Rosemont")
        assert p.is_available(dt(2023, 4, 12))
        assert p.can_reach(LOC)

    def test_specific_availability_and_location(self):
        p = Person(
            "x", {"mech"}, 1, "Rosemont",
            can_go={LOC}, availabilities={dt(2023, 4, 12)},
        )
        assert p.is_available(dt(2023, 4, 12))
        assert not p.is_available(dt(2023, 4, 13))
        assert p.can_reach(LOC)
        assert not p.can_reach(LOC2)

    def test_has_skill(self):
        p = Person("x", {"mech", "leader"}, 1, "Rosemont")
        assert p.has_skill("mech")
        assert not p.has_skill("first_aid")

    def test_n_available_dates(self):
        assert Person("a", set(), 1, "R").get_n_available_dates() == MAX_DATE_AVAILABLE
        p = Person("b", set(), 1, "R", availabilities={dt(2023, 4, 12), dt(2023, 4, 13)})
        assert p.get_n_available_dates() == 2


class TestEvent:
    def test_rejects_bad_during(self):
        with pytest.raises(AssertionError):
            Event("a", LOC, dt(2023, 4, 12), "evening", 5)

    def test_id_and_time_slot(self):
        e = Event("a", LOC, dt(2023, 4, 12), "am", 5)
        assert e.id == "2023-04-12:am:school-a:a"
        assert e.time_slot == (dt(2023, 4, 12), "am")

    def test_required_skills_defaults_and_override(self):
        e = Event("a", LOC, dt(2023, 4, 12), "am", 5)
        assert e.get_required_skills() == REQUIRED_SKILLS_PER_EVENT
        e2 = Event("b", LOC, dt(2023, 4, 12), "am", 5, required_skills={"mech": 1})
        assert e2.get_required_skills() == {"mech": 1}


class TestSolution:
    def test_roundtrip(self):
        s = Solution()
        s.schedule_worker("w1", "e1")
        s.schedule_worker("w2", "e1")
        s.schedule_worker("w1", "e2")

        assert set(s.get_workers_for_event("e1")) == {"w1", "w2"}
        assert set(s.get_events_for_worker("w1")) == {"e1", "e2"}
        assert s.is_worker_scheduled("w1", "e2")
        assert not s.is_worker_scheduled("w2", "e2")
