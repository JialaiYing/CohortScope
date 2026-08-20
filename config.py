"""Locked project decisions for Cohortscope (Phase 0)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
IMAGES_DIR = DATA_DIR / "images"
META_DIR = DATA_DIR / "meta"

# Rijksmuseum Search API — no key required
SEARCH_URL = "https://data.rijksmuseum.nl/search/collection"
RESOLVE_PROFILE = "la-framed"
REQUEST_TIMEOUT_S = 30

# English filters verified live (Phase 0). Dutch equivalents match the same counts.
# Do NOT filter on technique in search: technique values are roles like "painter",
# not medium; material=oil paint already keeps the Rembrandt painting set intact.
FILTERS = {
    "imageAvailable": "true",
    "type": "painting",
    "material": "oil paint",
}

# Main cohort: creator search works (~24 oil paintings with digital images).
MAIN_CREATOR_QUERY = "Rembrandt van Rijn"

# Validation set: creator= search returns 0 for workshop/circle phrases.
# Acquire via description probes, then keep rows whose resolved labels look like
# circle/workshop/school/attributed — expect a very small set (roadmap risk).
VALIDATION_DESCRIPTION_QUERIES = (
    "workshop of Rembrandt",
    "circle of Rembrandt",
    "school of Rembrandt",
    "school van Rembrandt",
    "atelier van Rembrandt",
    "omgeving van Rembrandt",
)
VALIDATION_CREATOR_HINTS = (
    "workshop",
    "circle",
    "school",
    "follower",
    "studio",
    "omgeving",
    "atelier",
    "navolger",
    "attributed to",
    "toegeschreven",
)

# Pupil cohort (D32 / O06 — see results/phase7_pupil_validation_design.md).
# Surrogate negative class: painters who trained in Rembrandt's studio, catalogued
# under their own names. `creator=` search works for these (unlike the D14 hedge
# phrases). Tier 1 = documented pupils (primary analysis); Tier 2 = associates
# whose pupilage is disputed or absent (sensitivity only, never pooled).
PUPIL_TIER1_CREATORS = (
    "Gerrit Dou",
    "Govert Flinck",
    "Ferdinand Bol",
    "Carel Fabritius",
    "Samuel van Hoogstraten",
    "Nicolaes Maes",
    "Willem Drost",
    "Barent Fabritius",
    "Gerbrand van den Eeckhout",
    "Aert de Gelder",
)
PUPIL_TIER2_CREATORS = (
    "Jan Lievens",
    "Jacob Backer",
)

# IIIF: long-edge 1500px — Phase 0 sample was ~237 KB/image; ~30 images << 5 GB.
IIIF_MAX_EDGE = 1500
IIIF_IMAGE_TMPL = "https://iiif.micr.io/{identifier}/full/{edge},/0/default.jpg"
IIIF_INFO_TMPL = "https://iiif.micr.io/{identifier}/info.json"
# IIIF Image API region request: {x},{y},{w},{h} in native pixels, served at {tw},{th}.
IIIF_REGION_TMPL = (
    "https://iiif.micr.io/{identifier}/{x},{y},{w},{h}/{tw},{th}/0/default.jpg"
)

# Physically-normalized tiling — D34 / O07, locked in
# results/phase8_tiling_design.md before any tile was fetched. These are
# pre-registered values, not tunables: changing one changes which works are
# scored, so it requires a new recipe ID and a new pre-registration.
TILE_FLOOR_MM_PER_PX = 0.20   # O07, human decision 2026-08-19
TILE_SIZE_MM = 30.0           # canvas covered by one tile, both axes
TILE_EDGE_INSET = 0.05        # fraction of each edge dropped (frame / tacking margin)
TILES_PER_WORK = 20           # equal weight per work; bounded by the smallest work
# Determined, not chosen: 30.0 / 0.20 = 150 px.
TILE_SIZE_PX = int(round(TILE_SIZE_MM / TILE_FLOOR_MM_PER_PX))

# Visual embedding backbone (Days 5–7). ResNet50 fits 4 GB VRAM; swap later only if weak.
BACKBONE = "resnet50"
BACKBONE_WEIGHTS = "IMAGENET1K_V2"

# Storage locked D22 — SQLite works table (see results/phase1_acquisition_design.md)
DB_PATH = DATA_DIR / "cohortscope.sqlite"
