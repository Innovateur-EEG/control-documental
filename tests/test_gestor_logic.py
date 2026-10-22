"""Regression tests for gestor hierarchy and permission resolution."""

from app.utils.gestor import (
    EDIT_PERMISSION,
    READ_ONLY_PERMISSION,
    descendant_participation_ids,
    effective_permission,
)


def test_descendants_are_deduplicated_and_cycles_do_not_loop():
    edges = [(1, 2), (2, 3), (3, 1), (2, 4), (1, 4)]
    assert descendant_participation_ids([1], edges) == {2, 3, 4}


def test_direct_permission_overrides_inherited_permission():
    assert effective_permission(
        participation_id=20,
        persona_id=200,
        direct_permissions={100: READ_ONLY_PERMISSION, 200: EDIT_PERMISSION},
        parents_by_child={20: [10]},
        participation_persona_ids={10: 100, 20: 200},
    ) == EDIT_PERMISSION


def test_edit_permission_is_inherited_through_multiple_levels():
    assert effective_permission(
        participation_id=30,
        persona_id=300,
        direct_permissions={100: EDIT_PERMISSION},
        parents_by_child={30: [20], 20: [10]},
        participation_persona_ids={10: 100, 20: 200, 30: 300},
    ) == EDIT_PERMISSION


def test_read_only_is_inherited_and_unknown_permissions_fail_closed():
    assert effective_permission(
        participation_id=20,
        persona_id=200,
        direct_permissions={100: READ_ONLY_PERMISSION},
        parents_by_child={20: [10]},
        participation_persona_ids={10: 100, 20: 200},
    ) == READ_ONLY_PERMISSION
    assert effective_permission(
        participation_id=20,
        persona_id=200,
        direct_permissions={100: "unexpected-value"},
        parents_by_child={20: [10]},
        participation_persona_ids={10: 100, 20: 200},
    ) == READ_ONLY_PERMISSION


def test_nearest_assigned_ancestor_takes_precedence():
    assert effective_permission(
        participation_id=30,
        persona_id=300,
        direct_permissions={100: EDIT_PERMISSION, 200: READ_ONLY_PERMISSION},
        parents_by_child={30: [20], 20: [10]},
        participation_persona_ids={10: 100, 20: 200, 30: 300},
    ) == READ_ONLY_PERMISSION


def test_missing_assignment_defaults_to_read_only():
    assert effective_permission(
        participation_id=20,
        persona_id=200,
        direct_permissions={},
        parents_by_child={20: [10]},
        participation_persona_ids={10: 100, 20: 200},
    ) == READ_ONLY_PERMISSION
