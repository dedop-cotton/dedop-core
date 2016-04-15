import csv
import numpy as np
from ast import literal_eval
from collections import OrderedDict

from dedop.proc.geo.lla2ecef import lla2ecef

class TestDataLoader:
    _default_delim = '\t'

    def __init__(self, filepath, delim=None):
        if delim is None:
            delim = self._default_delim

        self._values = OrderedDict()

        with open(filepath, 'rt') as csv_file:
            reader = csv.reader(csv_file, delimiter=delim)
            for row in reader:
                name, *values = filter(bool, row)

                vals = list(map(literal_eval, values))

                if len(vals) > 1:
                    vals = np.asarray(vals)
                elif vals:
                    vals = vals[0]
                else:
                    vals = None

                self._values[name] = vals

    def __getitem__(self, index):
        return self._values[index]

class MockObject(OrderedDict):
    @classmethod
    def load_file(cls, filepath, delim=None):
        loader = TestDataLoader(filepath, delim)
        fields = loader._values.keys()
        data = np.vstack([loader[f] for f in fields])

        n_objects = data.shape[1]
        for i in range(n_objects):
            d = OrderedDict()
            for name, val in zip(fields, data[:, i]):
                d[name] = val
            yield cls(d)

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError("Attribute '{}' not defined in test data".format(item))
