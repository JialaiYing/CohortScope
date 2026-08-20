"""Shared Rijksmuseum Search / Linked Art / IIIF helpers for Cohortscope.

Acquisition CLI lives in `acquire.py`. (Phase 0 smoke script removed in T019.)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

import config

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "CohortScope/0.1 (research; acquire)"})


def get_json(url: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    r = SESSION.get(url, params=params, timeout=config.REQUEST_TIMEOUT_S)
    r.raise_for_status()
    return r.json()


def search(params: dict[str, str]) -> dict[str, Any]:
    return get_json(config.SEARCH_URL, params=params)


def resolve(uri: str) -> dict[str, Any]:
    data_uri = uri.replace("https://id.rijksmuseum.nl/", "https://data.rijksmuseum.nl/")
    return get_json(f"{data_uri}?_profile={config.RESOLVE_PROFILE}")


def extract_title(record: dict[str, Any]) -> str | None:
    for item in record.get("identified_by", []):
        if item.get("type") != "Name":
            continue
        for classification in item.get("classified_as", []):
            if classification.get("id") == "http://vocab.getty.edu/aat/300417200":
                return item.get("content")
    return None


def extract_object_number(record: dict[str, Any]) -> str | None:
    for item in record.get("identified_by", []):
        if item.get("type") != "Identifier":
            continue
        for classification in item.get("classified_as", []):
            if classification.get("id") == "https://id.rijksmuseum.nl/22015218":
                return item.get("content")
    return None


def _name_from_actor(actor: dict[str, Any]) -> str | None:
    en = None
    any_name = None
    for notation in actor.get("notation") or []:
        if not isinstance(notation, dict):
            continue
        val = notation.get("@value") or notation.get("content")
        if not val:
            continue
        any_name = val
        if notation.get("@language") == "en":
            en = val
            break
    if en or any_name:
        return en or any_name
    for item in actor.get("identified_by") or []:
        if item.get("type") == "Name" and item.get("content"):
            return item["content"]
    return None


def _resolve_person_name(person_uri: str) -> str | None:
    try:
        person = resolve(person_uri)
    except requests.RequestException:
        return None
    name = _name_from_actor(person)
    if name:
        return name
    for item in person.get("identified_by") or []:
        if item.get("type") == "Name" and item.get("content"):
            return item["content"]
    return None


def extract_creators(record: dict[str, Any]) -> list[str]:
    """Pull creator labels from Linked Art production records."""
    names: list[str] = []
    produced = record.get("produced_by") or {}
    parts = produced.get("part") or []
    if isinstance(parts, dict):
        parts = [parts]

    actors: list[dict[str, Any]] = []
    for part in parts:
        actors.extend(a for a in (part.get("carried_out_by") or []) if isinstance(a, dict))
        for assignment in part.get("assigned_by") or []:
            for assigned in assignment.get("assigned") or []:
                if not isinstance(assigned, dict):
                    continue
                if assigned.get("type") in {"Person", "Group"} or assigned.get("id"):
                    actors.append(assigned)
    actors.extend(a for a in (produced.get("carried_out_by") or []) if isinstance(a, dict))

    for actor in actors:
        if actor.get("id") and not actor.get("notation") and not actor.get("identified_by"):
            name = _resolve_person_name(actor["id"])
        else:
            name = _name_from_actor(actor)
        if name:
            names.append(name)

    for ref in produced.get("referred_to_by") or []:
        content = ref.get("content")
        if content:
            names.append(content)

    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def extract_materials(record: dict[str, Any]) -> list[str]:
    """Collect material / made_of labels when present (for P05 oil check)."""
    labels: list[str] = []
    for made in record.get("made_of") or []:
        if not isinstance(made, dict):
            continue
        for item in made.get("identified_by") or []:
            if item.get("type") == "Name" and item.get("content"):
                labels.append(item["content"])
        for notation in made.get("notation") or []:
            if isinstance(notation, dict):
                val = notation.get("@value") or notation.get("content")
                if val:
                    labels.append(val)
        # Sometimes only an id; resolve lightly
        mid = made.get("id")
        if mid and not labels:
            try:
                mat = resolve(mid)
            except requests.RequestException:
                continue
            for item in mat.get("identified_by") or []:
                if item.get("type") == "Name" and item.get("content"):
                    labels.append(item["content"])
    # Deduplicate preserving order
    seen: set[str] = set()
    out: list[str] = []
    for n in labels:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def first_uri(obj: Any, key: str) -> str | None:
    val = obj.get(key) if isinstance(obj, dict) else None
    if isinstance(val, list) and val:
        first = val[0]
        if isinstance(first, dict):
            return first.get("id")
        if isinstance(first, str):
            return first
    if isinstance(val, dict):
        return val.get("id")
    if isinstance(val, str):
        return val
    return None


def get_iiif_identifier(object_uri: str) -> str | None:
    """Object -> VisualItem -> DigitalObject -> IIIF access_point."""
    obj = resolve(object_uri)
    visual_uri = first_uri(obj, "shows")
    if not visual_uri:
        return None
    visual = resolve(visual_uri)
    digital_uri = first_uri(visual, "digitally_shown_by")
    if not digital_uri:
        return None
    digital = resolve(digital_uri)
    for item in digital.get("access_point") or []:
        url = item.get("id") if isinstance(item, dict) else None
        if url and "iiif.micr.io/" in url:
            return url.split("iiif.micr.io/")[1].split("/")[0]
    return None


def iiif_url(identifier: str, edge: int = config.IIIF_MAX_EDGE) -> str:
    return config.IIIF_IMAGE_TMPL.format(identifier=identifier, edge=edge)


# --- Physical + native geometry (Fix 1). --------------------------------------
# Texture features are implicitly measured in millimetres of canvas per pixel, so
# that quantity has to be recoverable for every work. The catalogued size is
# already present in the la-framed record we resolve anyway; only the native
# pixel size costs an extra request.

# Getty AAT / Rijksmuseum `notation` labels for the two dimensions we want.
_DIMENSION_LABELS = ("height", "width")


def extract_physical_cm(record: dict[str, Any]) -> dict[str, float]:
    """Catalogued height/width in centimetres from a resolved la-framed record.

    Returns {} when the museum publishes no usable dimension for the object;
    callers must treat a missing value as unknown, never as zero.
    """
    out: dict[str, float] = {}
    for dim in record.get("dimension") or []:
        value = dim.get("value")
        if value is None:
            continue
        for classified in dim.get("classified_as") or []:
            for note in classified.get("notation") or []:
                label = note.get("@value")
                if note.get("@language") == "en" and label in _DIMENSION_LABELS:
                    try:
                        out.setdefault(label, float(value))
                    except (TypeError, ValueError):
                        pass
    return out


def iiif_info(identifier: str) -> dict[str, Any]:
    """IIIF info.json — the full-resolution size the museum actually publishes."""
    return get_json(config.IIIF_INFO_TMPL.format(identifier=identifier))


def native_pixels(identifier: str) -> tuple[int, int]:
    info = iiif_info(identifier)
    return int(info["width"]), int(info["height"])


def paginate_ids(params: dict[str, str], max_pages: int = 20) -> list[str]:
    """Paginate search until exhausted or max_pages."""
    url: str | None = config.SEARCH_URL
    local_params: dict[str, str] | None = params
    ids: list[str] = []
    pages = 0
    while url and pages < max_pages:
        data = get_json(url, params=local_params)
        ids.extend(item["id"] for item in data.get("orderedItems") or [])
        pages += 1
        nxt = data.get("next") or {}
        url = nxt.get("id")
        local_params = None
    return ids


def download_iiif(
    identifier: str,
    dest: Path,
    edge: int = config.IIIF_MAX_EDGE,
    retries: int = 2,
) -> int:
    """Download IIIF JPEG to dest. Returns byte length. Raises on failure."""
    url = iiif_url(identifier, edge=edge)
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = SESSION.get(url, timeout=config.REQUEST_TIMEOUT_S)
            r.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)
            return len(r.content)
        except (requests.RequestException, OSError) as exc:
            last_err = exc
    assert last_err is not None
    raise last_err
