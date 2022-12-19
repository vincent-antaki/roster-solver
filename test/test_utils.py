from roster_solver.utils import bidict


def test_bidict():
    data = {"a": [1], "b": [2, 3, 4], "c": [5]}
    a = bidict(data)
    assert a == data
    assert a.inverse == {1: ["a"], 2: ["b"], 3: ["b"], 4: ["b"], 5: ["c"]}
    a.add_item("c", 3)
    assert a == {"a": [1], "b": [2, 3, 4], "c": [5, 3]}
    assert a.inverse == {1: ["a"], 2: ["b"], 3: ["b", "c"], 4: ["b"], 5: ["c"]}
