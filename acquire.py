"""
Phase 1 Wave B acquisition: search → resolve → IIIF → SQLite splits → inventory.

Usage (from repo root, mamba env CohortScope):
  python acquire.py              # full harvest
  python acquire.py --dry-run    # resolve + assign splits; no image download / no DB write
  python acquire.py --inventory  # regenerate results/inventory.* from existing DB
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

import config
import rijks_api

SPLITS = ("cohort", "validation", "ambiguous", "excluded")

# Circle / workshop / school hedge (D20 / T017 §1.1) — Rembrandt context required.
CIRCLE_WORKSHOP_PHRASES = (
    "circle of",
    "workshop of",
    "school of",
    "omgeving van",
    "atelier van",
    "school van",
    "follower",
    "studio",
    "navolger",
)

ATTRIBUTED_PHRASES = (
    "attributed to",
    "toegeschreven",
)

FIRM_REMBRANDT_MARKERS = (
    "rembrandt van rijn",
    "rijn, rembrandt van",
)

ANON_MARKERS = ("anonymous", "anoniem")

DDL = """
CREATE TABLE IF NOT EXISTS works (
  object_uri TEXT PRIMARY KEY,
  object_number TEXT NOT NULL UNIQUE,
  title TEXT,
  creators_json TEXT NOT NULL,
  creator_label_family TEXT NOT NULL,
  split TEXT NOT NULL CHECK (split IN ('cohort','validation','ambiguous','excluded')),
  split_reason TEXT NOT NULL,
  source_query_type TEXT NOT NULL,
  source_query TEXT NOT NULL,
  iiif_id TEXT,
  iiif_max_edge INTEGER NOT NULL,
  image_path TEXT,
  image_bytes INTEGER,
  filters_json TEXT NOT NULL,
  acquired_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_works_split ON works(split);
"""


@dataclass
class WorkRow:
    object_uri: str
    object_number: str
    title: str | None
    creators: list[str]
    creator_label_family: str
    split: str
    split_reason: str
    source_query_type: str
    source_query: str
    iiif_id: str | None = None
    iiif_max_edge: int = config.IIIF_MAX_EDGE
    image_path: str | None = None
    image_bytes: int | None = None
    filters: dict[str, str] = field(default_factory=dict)
    acquired_at: str = ""
    has_image: bool = False


def _joined_creators(creators: list[str]) -> str:
    return " | ".join(creators).lower()


def _has_rembrandt(text: str) -> bool:
    return "rembrandt" in text


def classify_creator_family(creators: list[str]) -> str:
    """Return firm | circle_workshop | attributed | other | missing."""
    if not creators:
        return "missing"
    low = _joined_creators(creators)

    # Attributed / circle need Rembrandt in the joined label text.
    circle_hit = any(p in low for p in CIRCLE_WORKSHOP_PHRASES) and _has_rembrandt(low)
    attrib_hit = any(p in low for p in ATTRIBUTED_PHRASES) and _has_rembrandt(low)

    if circle_hit:
        return "circle_workshop"
    if attrib_hit:
        return "attributed"

    firm_hit = any(m in low for m in FIRM_REMBRANDT_MARKERS)
    # Also accept bare "Rembrandt van Rijn (signed...)" etc. covered by markers.
    if firm_hit and not circle_hit and not attrib_hit:
        return "firm"

    return "other"


def _is_anonymous_only(creators: list[str]) -> bool:
    if not creators:
        return True
    low = _joined_creators(creators)
    if _has_rembrandt(low):
        return False
    return all(any(a in c.lower() for a in ANON_MARKERS) for c in creators)


def _is_named_other_artist(creators: list[str]) -> bool:
    """Probe false positive: other master, no Rembrandt-hedge KEEP."""
    family = classify_creator_family(creators)
    if family in {"circle_workshop", "attributed", "firm"}:
        return False
    if _is_anonymous_only(creators):
        return True
    # Named person without Rembrandt hedge
    low = _joined_creators(creators)
    if not _has_rembrandt(low) and creators:
        return True
    return False


def materials_look_non_oil(materials: list[str]) -> bool:
    """P05: if materials are known and clearly non-oil, exclude."""
    if not materials:
        return False
    joined = " | ".join(materials).lower()
    oil_ok = any(x in joined for x in ("oil paint", "olieverf", "oil"))
    if oil_ok:
        return False
    # Explicit non-oil signals when oil absent
    non_oil = ("watercolor", "watercolour", "aquarelle", "tempera", "ink", "chalk", "pastel")
    return any(x in joined for x in non_oil)


def assign_split(
    *,
    creators: list[str],
    source_query_type: str,
    has_image: bool,
    materials: list[str] | None = None,
) -> tuple[str, str, str]:
    """Return (split, split_reason, creator_label_family). D20 / T017 §1.2."""
    family = classify_creator_family(creators)

    if materials and materials_look_non_oil(materials):
        return "excluded", "non_oil_material", family

    if not has_image:
        return "excluded", "missing_image", family

    # Description-probe false positives
    if source_query_type == "description":
        if _is_anonymous_only(creators):
            return "excluded", "anonymous", family
        if _is_named_other_artist(creators):
            return "excluded", "other_artist", family
        # Firm Rembrandt only via probe prose, no hedge → excluded
        if family == "firm":
            return "excluded", "probe_false_positive", family

    if family == "circle_workshop":
        return "validation", "circle_keep", family

    if family == "attributed":
        return "ambiguous", "attributed_o05", family

    if family == "firm" and source_query_type == "creator":
        return "cohort", "firm_main_search", family

    return "excluded", "fail_closed", family


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def init_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(DDL)
    return conn


def upsert_work(conn: sqlite3.Connection, row: WorkRow) -> None:
    conn.execute(
        """
        INSERT INTO works (
          object_uri, object_number, title, creators_json, creator_label_family,
          split, split_reason, source_query_type, source_query,
          iiif_id, iiif_max_edge, image_path, image_bytes, filters_json, acquired_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(object_uri) DO UPDATE SET
          object_number=excluded.object_number,
          title=excluded.title,
          creators_json=excluded.creators_json,
          creator_label_family=excluded.creator_label_family,
          split=excluded.split,
          split_reason=excluded.split_reason,
          source_query_type=excluded.source_query_type,
          source_query=excluded.source_query,
          iiif_id=excluded.iiif_id,
          iiif_max_edge=excluded.iiif_max_edge,
          image_path=excluded.image_path,
          image_bytes=excluded.image_bytes,
          filters_json=excluded.filters_json,
          acquired_at=excluded.acquired_at
        """,
        (
            row.object_uri,
            row.object_number,
            row.title,
            json.dumps(row.creators, ensure_ascii=False),
            row.creator_label_family,
            row.split,
            row.split_reason,
            row.source_query_type,
            row.source_query,
            row.iiif_id,
            row.iiif_max_edge,
            row.image_path,
            row.image_bytes,
            json.dumps(row.filters, ensure_ascii=False),
            row.acquired_at,
        ),
    )


def process_uri(
    uri: str,
    *,
    source_query_type: str,
    source_query: str,
    filters: dict[str, str],
    seen_uris: set[str],
    seen_object_numbers: set[str],
    dry_run: bool,
) -> WorkRow | None:
    if uri in seen_uris:
        return None

    try:
        record = rijks_api.resolve(uri)
    except requests.RequestException as exc:
        print(f"  SKIP resolve failed {uri}: {exc}")
        return None

    obj_no = rijks_api.extract_object_number(record) or uri.rsplit("/", 1)[-1]
    if obj_no in seen_object_numbers:
        print(f"  SKIP duplicate object_number={obj_no}")
        seen_uris.add(uri)
        return None

    title = rijks_api.extract_title(record)
    creators = rijks_api.extract_creators(record)
    materials = rijks_api.extract_materials(record)

    iiif_id: str | None = None
    image_path: str | None = None
    image_bytes: int | None = None
    has_image = False

    try:
        iiif_id = rijks_api.get_iiif_identifier(uri)
    except requests.RequestException as exc:
        print(f"  WARN IIIF resolve failed {obj_no}: {exc}")
        iiif_id = None

    if iiif_id and not dry_run:
        dest = config.IMAGES_DIR / f"{obj_no}.jpg"
        try:
            image_bytes = rijks_api.download_iiif(iiif_id, dest)
            # Store repo-relative path with forward slashes
            image_path = f"data/images/{obj_no}.jpg"
            has_image = True
        except (requests.RequestException, OSError) as exc:
            print(f"  WARN download failed {obj_no}: {exc}")
            has_image = False
    elif iiif_id and dry_run:
        has_image = True  # assume download would succeed for split assignment
        image_path = f"data/images/{obj_no}.jpg"
    else:
        has_image = False

    split, reason, family = assign_split(
        creators=creators,
        source_query_type=source_query_type,
        has_image=has_image,
        materials=materials,
    )

    # If we marked as needing an image for scoring but download failed, force excluded
    if not has_image and split != "excluded":
        split, reason = "excluded", "missing_image"

    seen_uris.add(uri)
    seen_object_numbers.add(obj_no)

    row = WorkRow(
        object_uri=uri,
        object_number=obj_no,
        title=title,
        creators=creators,
        creator_label_family=family,
        split=split,
        split_reason=reason,
        source_query_type=source_query_type,
        source_query=source_query,
        iiif_id=iiif_id,
        iiif_max_edge=config.IIIF_MAX_EDGE,
        image_path=image_path if has_image else None,
        image_bytes=image_bytes,
        filters=dict(filters),
        acquired_at=utc_now(),
        has_image=has_image,
    )
    print(
        f"  [{split:10}] {obj_no:12} | {family:16} | {reason:22} | {title}"
    )
    return row


def harvest(dry_run: bool = False) -> list[WorkRow]:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[WorkRow] = []
    seen_uris: set[str] = set()
    seen_object_numbers: set[str] = set()

    # --- Main creator search (D10 + P02) ---
    main_filters = {**config.FILTERS, "creator": config.MAIN_CREATOR_QUERY}
    print(f"=== Main search: {main_filters} ===")
    main_ids = rijks_api.paginate_ids(main_filters)
    print(f"  found {len(main_ids)} uris")
    for uri in main_ids:
        row = process_uri(
            uri,
            source_query_type="creator",
            source_query=config.MAIN_CREATOR_QUERY,
            filters=main_filters,
            seen_uris=seen_uris,
            seen_object_numbers=seen_object_numbers,
            dry_run=dry_run,
        )
        if row:
            rows.append(row)

    # --- Description probes (D14 / P05: omit material) ---
    for desc in config.VALIDATION_DESCRIPTION_QUERIES:
        probe_filters = {
            "imageAvailable": "true",
            "type": "painting",
            "description": desc,
        }
        print(f"=== Description probe: {desc!r} ===")
        probe_ids = rijks_api.paginate_ids(probe_filters)
        print(f"  found {len(probe_ids)} uris")
        for uri in probe_ids:
            row = process_uri(
                uri,
                source_query_type="description",
                source_query=desc,
                filters=probe_filters,
                seen_uris=seen_uris,
                seen_object_numbers=seen_object_numbers,
                dry_run=dry_run,
            )
            if row:
                rows.append(row)

    return rows


def persist(rows: list[WorkRow]) -> None:
    # Fresh DB each full harvest so splits are authoritative
    if config.DB_PATH.exists():
        config.DB_PATH.unlink()
    conn = init_db(config.DB_PATH)
    try:
        for row in rows:
            upsert_work(conn, row)
        conn.commit()
    finally:
        conn.close()
    print(f"Wrote {config.DB_PATH} ({len(rows)} rows)")


def load_rows_from_db() -> list[dict[str, Any]]:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute("SELECT * FROM works ORDER BY split, object_number")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def write_inventory(db_rows: list[dict[str, Any]] | None = None) -> None:
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if db_rows is None:
        db_rows = load_rows_from_db()

    split_counts = Counter(r["split"] for r in db_rows)
    with_image = sum(1 for r in db_rows if r.get("image_path"))
    missing_image = sum(1 for r in db_rows if not r.get("image_path"))

    disk_bytes = 0
    for path in config.IMAGES_DIR.glob("*.jpg"):
        if path.name.startswith("smoke_"):
            continue
        disk_bytes += path.stat().st_size

    works_out = []
    for r in db_rows:
        creators = r["creators_json"]
        if isinstance(creators, str):
            creators = json.loads(creators)
        works_out.append(
            {
                "object_number": r["object_number"],
                "title": r["title"],
                "split": r["split"],
                "split_reason": r["split_reason"],
                "creator_label_family": r["creator_label_family"],
                "creators": creators,
                "source_query_type": r["source_query_type"],
                "source_query": r["source_query"],
                "image_path": r["image_path"],
                "iiif_id": r["iiif_id"],
            }
        )

    payload = {
        "generated_at": utc_now(),
        "filters": config.FILTERS,
        "iiif_max_edge": config.IIIF_MAX_EDGE,
        "db_path": str(config.DB_PATH.relative_to(config.ROOT)).replace("\\", "/"),
        "counts": {
            **{s: split_counts.get(s, 0) for s in SPLITS},
            "total": len(db_rows),
            "with_image": with_image,
            "missing_image": missing_image,
        },
        "disk_bytes_images": disk_bytes,
        "disk_budget_note": f"{disk_bytes:,} bytes of production images; budget < 5 GB",
        "expected_validation_n_note": (
            "Primary validation N is expected to be tiny (1–3). "
            "Do not claim AUC or large-sample rates (T017 §3). "
            "T043 success counts only split=validation; ambiguous is exploratory only (D21)."
        ),
        "works": works_out,
    }

    json_path = config.RESULTS_DIR / "inventory.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # Markdown
    lines: list[str] = []
    lines.append("# Cohortscope Phase 1 inventory")
    lines.append("")
    lines.append(f"Generated: `{payload['generated_at']}`")
    lines.append("")
    lines.append("## Counts by split")
    lines.append("")
    lines.append("| Split | N | Fit normals? | Score? | T043? |")
    lines.append("|---|---:|---|---|---|")
    lines.append(
        f"| cohort | {split_counts.get('cohort', 0)} | yes | yes | no |"
    )
    lines.append(
        f"| validation | {split_counts.get('validation', 0)} | no | yes | **yes** |"
    )
    lines.append(
        f"| ambiguous | {split_counts.get('ambiguous', 0)} | no | exploratory | no |"
    )
    lines.append(
        f"| excluded | {split_counts.get('excluded', 0)} | no | no | no |"
    )
    lines.append(f"| **total** | **{len(db_rows)}** | | | |")
    lines.append("")
    lines.append(
        f"Images on disk (excl. `smoke_*`): **{disk_bytes:,} bytes** "
        f"({with_image} rows with image_path; {missing_image} missing)."
    )
    lines.append("")
    lines.append("## Tiny validation N (read this)")
    lines.append("")
    lines.append(payload["expected_validation_n_note"])
    lines.append("")
    lines.append(
        "Split rules: `results/phase1_experimental_design.md` §1.2; "
        "schema: `results/phase1_acquisition_design.md`; locks D19–D22."
    )
    lines.append("")

    def _section(split: str, title: str) -> None:
        subset = [w for w in works_out if w["split"] == split]
        lines.append(f"## {title} (N={len(subset)})")
        lines.append("")
        if not subset:
            lines.append("*(none)*")
            lines.append("")
            return
        for w in subset:
            creators = ", ".join(w["creators"]) if w["creators"] else "(none)"
            lines.append(
                f"- **{w['object_number']}** — {w['title']}  \n"
                f"  reason=`{w['split_reason']}` · family=`{w['creator_label_family']}` · "
                f"source=`{w['source_query_type']}:{w['source_query']}`  \n"
                f"  creators: {creators}  \n"
                f"  image: `{w['image_path']}`"
            )
        lines.append("")

    _section("validation", "Validation keepers")
    _section("ambiguous", "Ambiguous (O05 / attributed)")
    _section("cohort", "Cohort (firm Rembrandt)")

    excl = [w for w in works_out if w["split"] == "excluded"]
    reason_counts = Counter(w["split_reason"] for w in excl)
    lines.append("## Excluded summary")
    lines.append("")
    if not excl:
        lines.append("*(none)*")
    else:
        lines.append("| Reason | N |")
        lines.append("|---|---:|")
        for reason, n in reason_counts.most_common():
            lines.append(f"| `{reason}` | {n} |")
        lines.append("")
        lines.append("### Excluded rows")
        lines.append("")
        for w in excl:
            creators = ", ".join(w["creators"]) if w["creators"] else "(none)"
            lines.append(
                f"- **{w['object_number']}** — {w['title']} · `{w['split_reason']}` · {creators}"
            )
    lines.append("")

    missing = [w for w in works_out if not w["image_path"]]
    lines.append("## Missing images")
    lines.append("")
    if not missing:
        lines.append("None.")
    else:
        for w in missing:
            lines.append(f"- {w['object_number']} ({w['split']})")
    lines.append("")

    md_path = config.RESULTS_DIR / "inventory.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")

    print("\n=== Split counts ===")
    for s in SPLITS:
        print(f"  {s:12} {split_counts.get(s, 0)}")
    print(f"  {'total':12} {len(db_rows)}")
    print(f"  validation N = {split_counts.get('validation', 0)} (expected tiny 1–3)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cohortscope Phase 1 acquisition")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve and assign splits; skip image download and DB write",
    )
    parser.add_argument(
        "--inventory",
        action="store_true",
        help="Regenerate results/inventory.* from existing SQLite only",
    )
    args = parser.parse_args(argv)

    if args.inventory:
        if not config.DB_PATH.exists():
            print(f"ERROR: no database at {config.DB_PATH}", file=sys.stderr)
            return 1
        write_inventory()
        return 0

    rows = harvest(dry_run=args.dry_run)
    if args.dry_run:
        print(f"\nDry-run complete: {len(rows)} rows (no DB / images written)")
        # Still emit a provisional inventory from in-memory rows
        db_like = [
            {
                "object_number": r.object_number,
                "title": r.title,
                "split": r.split,
                "split_reason": r.split_reason,
                "creator_label_family": r.creator_label_family,
                "creators_json": json.dumps(r.creators, ensure_ascii=False),
                "source_query_type": r.source_query_type,
                "source_query": r.source_query,
                "image_path": r.image_path if r.has_image else None,
                "iiif_id": r.iiif_id,
            }
            for r in rows
        ]
        # Do not overwrite production inventory on dry-run
        print("(dry-run) skipping inventory write")
        counts = Counter(r.split for r in rows)
        for s in SPLITS:
            print(f"  {s:12} {counts.get(s, 0)}")
        return 0

    persist(rows)
    write_inventory()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
