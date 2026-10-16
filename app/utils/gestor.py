"""Pure permission and hierarchy helpers for the gestor interface."""

from collections import deque

READ_ONLY_PERMISSION = "Solo Lectura"
EDIT_PERMISSION = "Lectura y Escritura"


def descendant_participation_ids(root_ids, hierarchy_edges):
    """Return reachable descendants while preventing cycles and excluding roots."""
    roots = set(root_ids)
    children_by_parent = {}
    for parent_id, child_id in hierarchy_edges:
        children_by_parent.setdefault(parent_id, []).append(child_id)

    descendants = set()
    visited = set(roots)
    queue = deque(roots)
    while queue:
        parent_id = queue.popleft()
        for child_id in children_by_parent.get(parent_id, []):
            if child_id in visited:
                continue
            visited.add(child_id)
            if child_id not in roots:
                descendants.add(child_id)
            queue.append(child_id)
    return descendants


def effective_permission(
    participation_id,
    persona_id,
    direct_permissions,
    parents_by_child,
    participation_persona_ids,
):
    """Resolve direct permission or nearest assigned ancestor; deny by default."""
    if persona_id in direct_permissions:
        return (
            EDIT_PERMISSION
            if direct_permissions[persona_id] == EDIT_PERMISSION
            else READ_ONLY_PERMISSION
        )

    queue = deque(
        (parent_id, 1)
        for parent_id in parents_by_child.get(participation_id, [])
    )
    visited = set()
    nearest_distance = None
    inherited_permissions = []

    while queue:
        ancestor_id, distance = queue.popleft()
        if nearest_distance is not None and distance > nearest_distance:
            break
        if ancestor_id in visited:
            continue
        visited.add(ancestor_id)

        ancestor_persona_id = participation_persona_ids.get(ancestor_id)
        if ancestor_persona_id in direct_permissions:
            nearest_distance = distance if nearest_distance is None else nearest_distance
            inherited_permissions.append(direct_permissions[ancestor_persona_id])
            continue

        for parent_id in parents_by_child.get(ancestor_id, []):
            queue.append((parent_id, distance + 1))

    if not inherited_permissions:
        return READ_ONLY_PERMISSION
    if all(permission == EDIT_PERMISSION for permission in inherited_permissions):
        return EDIT_PERMISSION
    return READ_ONLY_PERMISSION
