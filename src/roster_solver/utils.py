
import collections

def groupby_unsorted(seq, key=lambda x: x):
    indexes = collections.defaultdict(list)
    for i, elem in enumerate(seq):
        indexes[key(elem)].append(i)
    for k, idxs in indexes.items():
        yield k, (seq[i] for i in idxs)


class bidict(dict):
    """
    Map[Any, List[Any]] and contains self.inverse which of the same type

    """
    def __init__(self, *args, **kwargs):
        super(bidict, self).__init__(*args, **kwargs)
        self.inverse = {}
        for key, value in self.items():
            for v in value:
                self.inverse.setdefault(v,[]).append(key)

    def __setitem__(self, key, value):
        assert type(value) is list
        del self[key]
        for v in value:
            self.add_item(key, v)

    def add_item(self, key, value):
        self.setdefault(key, []).append(value)
        self.inverse.setdefault(value, []).append(key)

    def __delitem__(self, key):
        if key in self:
            for v in self[key]:
                self.inverse[v].remove(key)
            super(bidict, self).__delitem__(key)
            #self.inverse.setdefault(self[key], []).remove(key)


if __name__ == "__main__":
    test = {'a':[1],'b':[2,3,4], 'c':[5]}
    a = bidict(test)
    assert a == {'a':[1],'b':[2,3,4], 'c':[5]}
    assert a.inverse == {1: ['a'], 2: ['b'], 3: ['b'], 4: ['b'], 5: ['c']}
    a.add_item('c', 3)
    assert a == {'a': [1], 'b': [2, 3, 4], 'c': [5, 3]}
    assert a.inverse == {1: ['a'], 2: ['b'], 3: ['b', 'c'], 4: ['b'], 5: ['c']}