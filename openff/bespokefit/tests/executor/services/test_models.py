import operator

import pytest

from openff.bespokefit.executor.services.models import Link


@pytest.mark.parametrize(
    "link_a, op, link_b, expected",
    [
        (
            Link(id="a", self="localhost:8000/a"),
            operator.lt,
            Link(id="b", self="localhost:8000/b"),
            True,
        ),
        (
            Link(id="a", self="localhost:8000/a"),
            operator.gt,
            Link(id="b", self="localhost:8000/b"),
            False,
        ),
        (
            Link(id="a", self="localhost:8000/a"),
            operator.eq,
            Link(id="a", self="localhost:8000/a"),
            True,
        ),
        (
            Link(id="a", self="localhost:8000/a"),
            operator.eq,
            Link(id="b", self="localhost:8000/b"),
            False,
        ),
        (
            Link(id="a", self="localhost:8000/a"),
            operator.ne,
            Link(id="a", self="localhost:8000/a"),
            False,
        ),
        (
            Link(id="a", self="localhost:8000/a"),
            operator.ne,
            Link(id="b", self="localhost:8000/b"),
            True,
        ),
    ],
)
def test_link_comparison(link_a, op, link_b, expected):
    assert op(link_a, link_b) == expected


def test_link_hash():

    link_a = Link(id="a", self="localhost:8000/a")
    link_b = Link(id="b", self="localhost:8000/b")

    assert hash(link_a) != hash(link_b)
    assert hash(link_a) == hash(link_a)
