"""Conflict detection helpers."""


def has_version_conflict(read_updated: str, current_updated: str) -> bool:
    if not read_updated or not current_updated:
        return False
    return str(read_updated) != str(current_updated)
