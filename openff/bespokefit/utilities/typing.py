from typing import Any

import numpy as np


class ArrayMeta(type):
    def __getitem__(self, t):
        return type("Array", (Array,), {"__dtype__": t})


class Array(np.ndarray, metaclass=ArrayMeta):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate_type

    @classmethod
    def validate_type(cls, val):

        dtype = getattr(cls, "__dtype__", Any)

        if dtype is Any:
            return np.array(val)
        else:
            return np.array(val, dtype=dtype)
