"""Measurement targets for the existing colour ranking, without altering HEX→HEX results.

* sRGB measurements (HEX, RGB8) are converted losslessly to HEX and ranked by
  the historical :func:`colour_distance.rank` — identical scores and order.
* CIELAB D65/2° measurements are compared *directly* to the Lab of each
  declared catalogue HEX with the same :func:`colour_distance.ciede2000`;
  never through a reconstructed HEX. Classification, index, tie order,
  six-decimal rounding and exclusions are the historical ones.
* Anything the policy blocks raises :class:`TargetBlocked`; no ΔE is computed.
"""
from __future__ import annotations

from . import colour_distance, colour_measurements as cm


class TargetBlocked(ValueError):
    def __init__(self, policy: dict):
        super().__init__(policy.get("reason", "blocked"))
        self.policy = policy


def target_from_measurement(measurement: dict, identifier: str | None = None) -> dict:
    """Validated query for the UI: ``kind``, ``hex`` or ``lab``, policy and a fresh cache."""
    measurement = cm.validate_measurement(measurement)
    policy = cm.comparison_policy(measurement)
    if policy["level"] == "blocked":
        raise TargetBlocked(policy)
    target = {"kind": "measurement", "id": identifier, "name": measurement["name"], "policy": policy,
              "digest": measurement["content_digest"], "cache": {}, "space": measurement["original"]["space"],
              "conditions": cm.describe_conditions(measurement), "conditions_data": dict(measurement["conditions"]),
              "values": cm.summary_values(measurement)}
    hex_value = cm.hex_of(measurement)
    if hex_value is not None:
        target["hex"] = hex_value
    else:
        target["lab"] = cm.lab_of(measurement)
    return target


def _rank_lab(lab, rows, *, limit=None, cache=None, index=None) -> dict:
    """Same loop, tie order and rounding as ``colour_distance.rank`` for a Lab target."""
    cache = {} if cache is None else cache
    ranked, excluded = [], {}
    for row in rows:
        facts = index.get(id(row)) if index is not None else None
        if facts is None:
            kind = colour_distance.classify(row)
            facts = (kind, colour_distance.parse_hex(row.get("hex")) if kind in ("ranked", "effect") else None,
                     colour_distance._tie_key(row))
        kind, h, tie = facts
        if kind not in ("ranked", "effect"):
            excluded[kind] = excluded.get(kind, 0) + 1
            continue
        distance = cache.get(h)
        if distance is None:
            try:
                distance = cache[h] = round(colour_distance.ciede2000(lab, colour_distance.hex_to_lab(h)), 6)
            except (OverflowError, ValueError) as exc:
                raise TargetBlocked({"level": "blocked", "reason": "magnitude"}) from exc
        ranked.append((distance, tie, row, kind == "effect"))
    ranked.sort(key=lambda item: (item[0], item[1]))
    items = [dict(row=row, delta=delta, effect=effect) for delta, _, row, effect in ranked]
    return {"target": None, "items": items[:limit] if limit else items, "total": len(items), "excluded": excluded}


def rank_measurement(target: dict, rows, *, limit=None, index=None) -> dict:
    """Rank catalogue rows for a measurement target built by :func:`target_from_measurement`.

    The cache is the target's own: a new target (different values or
    conditions) carries a new cache and never reuses old distances.
    """
    if target.get("policy", {}).get("level") != "indicative":
        raise TargetBlocked(target.get("policy") or {"level": "blocked", "reason": "policy"})
    if "hex" in target:
        return colour_distance.rank(target["hex"], rows, limit=limit, cache=target["cache"], index=index)
    return _rank_lab(target["lab"], rows, limit=limit, cache=target["cache"], index=index)


def query_matches(query: dict, target: dict) -> bool:
    """True when the active query *is* this acquisition: same identity and same values/conditions.

    Identity is the registry identifier (or, for an unsaved draft, the absence
    of one plus the same name); equal coordinates never make two acquisitions
    the same target.
    """
    if not query or query.get("kind") != "measurement" or query.get("digest") != target.get("digest"):
        return False
    return query.get("id") == target.get("id") and query.get("name") == target.get("name")


def reusable_cache(query: dict | None, target: dict) -> dict:
    """Distances already computed for the same values and conditions; identity is never reused."""
    if query and query.get("kind") == "measurement" and query.get("digest") == target.get("digest"):
        return query.get("cache") or {}
    return {}
