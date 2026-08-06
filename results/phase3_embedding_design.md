# Phase 3 embedding design (ResNet50 extract I/O)

**Task:** T030 · **Role:** cv · **Date:** 2026-08-06  
**Status:** **LOCKED** 2026-08-06 (D29) — Wave B `embed.py` / T036 unlocked  
**Inputs:** D13, D26, D27, D29; `config.py` (`BACKBONE=resnet50`, `BACKBONE_WEIGHTS=IMAGENET1K_V2`); `data/preprocessed/preprocess_v1/manifest.json`; `results/phase2_preprocess_design.md` §1.3; `results/qc_preprocess_v1/geometry_note.md`  
**Wave B implement:** T036

---

## Verdict (read this first)

| Topic | Recommendation |
|---|---|
| Backbone | **ResNet50** + **`IMAGENET1K_V2`** (D13) — eval, frozen, **no finetune** |
| Input | Prefer Branch C cache `cnn/{object_number}.pt` (`3×224×224` ImageNet-normalized). Fallback: recompute **identical** `CNN_TRANSFORM` from Branch H PNG |
| Output | 2048-d global pool vector per work; join on `object_number` |
| VRAM | **`batch_size=1`** on RTX 3050 4 GB; `torch.no_grad()`; CUDA if available |
| Not doing | DINOv2 / alternate backbones; multi-crop; LoRA/finetune; Features Branch H consumption |
| Gate | Design only until human lock → then T036 |

---

## 1. Model contract (D13)

| Knob | Locked value |
|---|---|
| Architecture | `torchvision.models.resnet50` |
| Weights | `ResNet50_Weights.IMAGENET1K_V2` (same string as `config.BACKBONE_WEIGHTS` / preprocess manifest) |
| Mode | `.eval()`; all `requires_grad=False` |
| Embedding layer | Drop classifier (`fc`); take **AdaptiveAvgPool2d** output → flatten → **`float32[2048]`** |
| Stochastic ops | None (no dropout active in eval for this trunk; no aug) |

**Forbidden until Stats proves ResNet50 failed (D13):** DINOv2, ViT swaps, layer-cake hybrids, any finetune / linear probe training on cohort pixels or labels.

---

## 2. Input path (Branch C)

### 2.1 Primary — load preprocess_v1 Branch C

```text
data/preprocessed/preprocess_v1/cnn/{object_number}.pt
```

- Shape: `float32` **`[3, 224, 224]`** (CHW), already `Resize(256)` + `CenterCrop(224)` + ImageNet mean/std (D26).
- Load: `torch.load(..., map_location="cpu", weights_only=True)` then `.unsqueeze(0)` → `[1, 3, 224, 224]` for the forward.
- Worklist = preprocess manifest `object_numbers` (N=25: cohort ∪ validation ∪ ambiguous). Skip `excluded`.
- Do **not** read Branch H PNGs for the embedding forward when `.pt` exists (Features owns H; C is embeddings-only — preprocess docstring / T023).

### 2.2 Fallback — recompute transform (same recipe only)

If a `.pt` is missing (or `--from-rgb` debug), decode Branch H PNG and apply the **same** ops as `preprocess.CNN_TRANSFORM`:

`Resize(256)` → `CenterCrop(224)` → `ToTensor()` → `Normalize(IMAGENET_MEAN, IMAGENET_STD)`

Constants must match `manifest.json` `cnn.*` / D26. Do not invent a second crop policy. Geometry honesty (D27): Branch H may be taller than long-edge 1500; center-crop still follows torchvision short-side resize — document in embed manifest, do not val-retune.

### 2.3 Preference

**Default Wave B:** load Branch C `.pt` only. Recompute is a recovery path, not a second recipe. If recompute is used for any ID, record `input_mode=recompute` in the per-run log.

---

## 3. Forward (implementation sketch — not run yet)

Pseudo-order for T036:

1. Build ResNet50 + `IMAGENET1K_V2`; replace `fc` with `nn.Identity()` (or hook pool output).
2. For each `object_number` in sorted worklist: load `[1,3,224,224]` → device → forward → CPU `float32[2048]`.
3. **`batch_size=1`** always (4 GB headroom; N=25 so wall time is irrelevant).
4. Assert finite, shape `(2048,)`; write artifact; append QC row.

No gradients, no AMP required for N=25 (optional later; not in v1).

---

## 4. Output layout + schema

Recipe id: **`embed_v1`** (bump directory if backbone/pool/weights change).

```text
data/embeddings/embed_v1/
  manifest.json
  vectors/
    {object_number}.pt     # float32 tensor shape [2048]
  matrix.pt                # dict: object_numbers (list[str]), X (float32 [N,2048])
```

| Artifact | Contents |
|---|---|
| `vectors/{id}.pt` | One embedding; convenient re-score / debug |
| `matrix.pt` | Row-aligned matrix for Stats T041+; `X[i]` ↔ `object_numbers[i]` |
| `manifest.json` | See below |

**Join key:** `object_number` (e.g. `SK-A-3934`) — same as SQLite `works`, `data/images/`, preprocess caches. Stats joins embeddings ↔ hand-built features ↔ splits on this key only.

**`manifest.json` (minimum):**

| Field | Example / rule |
|---|---|
| `recipe_id` | `embed_v1` |
| `backbone` | `resnet50` |
| `backbone_weights` | `IMAGENET1K_V2` |
| `dim` | `2048` |
| `pool` | `adaptive_avgpool` (pre-fc) |
| `batch_size` | `1` |
| `preprocess_recipe` | `preprocess_v1` |
| `input` | `branch_c_pt` (default) |
| `splits_included` | `["cohort","validation","ambiguous"]` |
| `object_numbers` | sorted list written (must match matrix rows) |
| `splits_by_id` | copy or join from preprocess / SQLite |
| `n` | 25 |
| `versions` | torch / torchvision |
| `design` | `results/phase3_embedding_design.md` |
| `geometry_note` | `results/qc_preprocess_v1/geometry_note.md` (D27 pointer) |
| `created_at` | UTC ISO |

**Overwrite:** `--force` replaces `embed_v1/`; recipe change → new `embed_v2/` (never silent mix).

**Not in v1:** writing embeddings into SQLite; PCA/whitening inside the extractor (Stats owns feature-space transforms in Phase 4, cohort-fit only).

---

## 5. Module + CLI (Wave B)

| Item | Plan |
|---|---|
| Module | `embed.py` (flat layout, D15) — separate from `preprocess.py` |
| Config | Read `config.BACKBONE`, `BACKBONE_WEIGHTS`, `DB_PATH`, paths |
| CLI | `python embed.py` · `python embed.py --force` |
| Device | CUDA if `torch.cuda.is_available()` else CPU; still `batch_size=1` |

---

## 6. QC (T036 companion)

Write under `results/qc_embed_v1/`:

| Artifact | Rule |
|---|---|
| `failures.csv` | Columns: `object_number`, `ok`, `stage`, `message` (load / forward / shape) |
| Completeness | `# vectors == n == len(matrix.object_numbers) == 25`; set equals preprocess scored IDs |
| Sanity | All finite; L2 norms in a sane band (log min/median/max; no threshold tuned on val) |
| Optional | Spot-check: recompute transform vs `.pt` cosine ≈ 1 for 1–2 IDs (debug only) |

Do **not** use validation/ambiguous embedding distances to pick layer, pool, or backbone (L6).

---

## 7. Leakage / split rules

| Rule | Action |
|---|---|
| Same ops all splits | Yes — identical weights + Branch C recipe |
| Fit on cohort pixels/labels | **No** — frozen ImageNet trunk only |
| Score val/ambiguous | Yes (extract vectors); **never** fit normals here (Phase 4 / Stats) |
| `excluded` | Absent from worklist |
| Val-looking retune | Forbidden (D27 / Phase 2 review) |

---

## 8. Deliberately will NOT do

- Finetune, linear probe train, contrastive train on Rijks images  
- DINOv2 / CLIP / custom backbones  
- Ten-crop, multi-scale, TTA  
- Batch > 1 on this GPU class without a measured need  
- Feeding Branch C to Features, or Branch H into ResNet without the locked CNN transform  
- Gradio / FastAPI  
- Starting T036 before human lock of this memo (+ Features O03 as orchestrator requires)

---

## 9. Hand-offs

| Peer | Needs from this design |
|---|---|
| **Features (T031/T032)** | Orthogonal: they use Branch H only; join on `object_number` |
| **Stats (T035/T041)** | `matrix.pt` + `object_numbers`; dim=2048; fit normals on **cohort rows only** |
| **Literature** | Pretrained ImageNet embed, no scratch train (D25 framing) |
| **Review (T037)** | Check recipe pin, N=25, no finetune, batch_size=1, join key |

---

## 10. Open for human lock

1. Approve §1–4 (ResNet50 / Branch C `.pt` / `embed_v1` layout / `batch_size=1`)?  
2. Confirm matrix artifact `matrix.pt` (dict) vs prefer `embeddings.npy` + `ids.json` — **default: `matrix.pt`** as above.  
3. Unlock T036 implement after Features T031 lock (orchestrator Wave B gate)?

**No forward pass in T030.** Implementation waits on explicit human approval.
