"""Ensure parallel CI jobs collectively execute the complete test suite."""

from types import SimpleNamespace

import pytest

from backend.tests.conftest import partition_test_items


@pytest.mark.parametrize("total", [1, 2, 3, 7])
def test_shards_cover_all_tests_once_and_keep_stable_assignments(total):
    items = [SimpleNamespace(nodeid=f"tests/test_feature_{i // 10}.py::test_case[{i}]")
             for i in range(100)]
    assignments = {}
    for index in range(1, total + 1):
        selected, deselected = partition_test_items(items, index, total)
        assert len(selected) + len(deselected) == len(items)
        assert not {item.nodeid for item in selected} & {item.nodeid for item in deselected}
        reordered, _ = partition_test_items(list(reversed(items)), index, total)
        assert {item.nodeid for item in reordered} == {item.nodeid for item in selected}
        for item in selected:
            assert item.nodeid not in assignments
            assignments[item.nodeid] = index
    assert set(assignments) == {item.nodeid for item in items}


@pytest.mark.parametrize("index,total", [(0, 3), (4, 3), (1, 0), (-1, 3)])
def test_invalid_shards_fail_instead_of_silently_skipping_tests(index, total):
    with pytest.raises(ValueError, match="shard"):
        partition_test_items([], index, total)
