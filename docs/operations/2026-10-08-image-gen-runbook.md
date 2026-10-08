# La Vaquita Holandesa — AI Image Generation Runbook

**For the operator (Iván) and any future image-regen cycle.**
This is the actual operational procedure for generating the product + ingredient images using MiniMax image-01, given that the VM is CPU-only and the only authenticated image-gen endpoint is the MiniMax OAuth path.

## TL;DR

```bash
# 1. Build the items list (22 product bases + 94 ingredients = 116 images to gen)
.venv/bin/python data/build_image_prompts.py

# 2. Test on 1 item (the stroopwafel, the A/B test from the template)
.venv/bin/python data/generate_images.py --only-slug stroop_wafel --candidates 2

# 3. Inspect candidates, pick the best
ls -la data/images/candidates/stroop_wafel__cand*.jpg
# View them with vision_analyze or open in browser

# 4. If you want a different look, edit the prompt in
#    data/build_image_prompts.py (NEGATIVE constant + CATEGORY_STYLES) and
#    re-run step 1 + 2. Iterate until stroopwafel looks right.

# 5. Once happy: run all 22 products
.venv/bin/python data/generate_images.py --type product --candidates 2 --sleep 1.0

# 6. Then all 94 ingredients
.venv/bin/python data/generate_images.py --type ingredient --candidates 1 --sleep 1.0

# 7. Review & pick the best candidate per item (manual OR a future QC helper)
#    For now, cand1 is the default pick.

# 8. Publish to final locations
.venv/bin/python data/publish_images.py --type product --pick 1
.venv/bin/python data/publish_images.py --type ingredient --pick 1
```

## What gets generated

| Type | Count | File | Notes |
|---|---|---|---|
| **Product base** | 22 | `app/static/products/<slug>.jpg` | One per recipe in the seed |
| **Recipe (alias)** | 22 | `app/static/recipes/receta-<slug>.jpg` | Same image, copied. Per user: recipes and products share the same photo. |
| **Product variants** | 9 | (none — no image) | `docena_stroopwafels`, `cheesecake_entera`, etc. — reuse the base image, not regenerated |
| **Ingredient** | 94 | `app/static/ingredients/<slug>.jpg` | 1:1 square, 1024×1024 |
| **TOTAL FILES WRITTEN** | 138 | | 22×2 product+recipe copies + 94 ingredients |

## Why these numbers

The sazon seed has:
- **22 recipes** (one per baked good)
- **31 products** (22 single-piece products + 9 package variants like "docena stroopwafels" or "caja bombones")
- **94 ingredients** (Spanish names from the workbook)

Per user direction ("recipes and products should use the same image"), we generate ONE image per recipe base (22 images), and each one is written to both:
- `app/static/products/<recipe_slug>.jpg` (for the catalog/menu)
- `app/static/recipes/receta-<recipe_slug>.jpg` (for the recipe detail page)

The 9 package-variant products don't get their own image — they reuse the same `<recipe_slug>.jpg` already in the products folder.

## Model choice (and why MiniMax image-01)

| Model | Verdict | Why |
|---|---|---|
| **MiniMax image-01 (OAuth)** | ✅ **Chosen** | The OAuth token at `/opt/data/auth.json` authenticates against `https://api.minimax.io/v1/image_generation` and returns good-quality food images. ~24s per image. ~1500-char prompt limit. |
| Z.ai GLM-Image | ❌ Rejected | Account balance is zero (HTTP 429). |
| OpenRouter (Gemini image models) | ❌ Rejected | Requires $1+ credit (HTTP 402). |
| Comfy Cloud | ❌ Rejected | No key configured; VM is CPU-only anyway. |
| OpenAI / Stability / Replicate / Google direct | ❌ Rejected | No keys. |

The mini-test confirmed the OAuth path produces La Vaquita-style images on the first try (see `data/images/candidates/stroop_wafel__cand1.jpg` — perfect aesthetic match).

## Cost & time

- **22 products** × 2 candidates × 24s ≈ **18 min** + 1s sleep ≈ **20 min**
- **94 ingredients** × 1 candidate × 24s ≈ **38 min** + 1s sleep ≈ **40 min**
- **Total time**: ~1 hour end-to-end (one batch)
- **Cost**: 138 generated images = ~$0.30 in MiniMax credit (estimate; exact amount TBD)

## What can go wrong (and how to recover)

### 1. `invalid params, prompt length must be less than 1500`
The MiniMax API caps prompts at 1500 chars. `build_image_prompts.py` already trims, but if a future item's name pushes the prompt over, you'll see this error. Fix: edit the build script, drop a redundant clause, regenerate.

### 2. `minimax error: login fail` or `Insufficient balance`
Token expired or balance drained. Re-auth via OAuth (or top up the account). The script reads the token fresh from `/opt/data/auth.json` on every run, so a re-auth is automatic.

### 3. Image URL returns 403 / expired
The image URLs from MiniMax expire in 24 hours. The script downloads immediately. If you see a download failure, re-run `generate_images.py` (idempotent — already-downloaded candidates are skipped).

### 4. Bad candidate (looks wrong)
- Generate more: `--candidates 4` (or higher) on that one slug
- Or tweak the prompt in `build_image_prompts.py` and regenerate
- Then publish the best: `publish_images.py --only-slug <slug> --pick N`

### 5. The stroopwafel "A/B test" fails
Per the template §8.3: "Generate the stroopwafel product image FIRST. If it doesn't read as 'homemade Dutch bakery next door', adjust the brief and retry before generating the other 129." If the stroopwafel doesn't look right, DON'T batch all 116. Tweak the prompt in `build_image_prompts.py` (try tightening NEGATIVE, or changing CATEGORY_STYLES for "cookie") and re-run.

## File layout

```
data/
  build_image_prompts.py   # 1) build the 116 per-item prompts from items.json
  generate_images.py       # 2) call MiniMax, download to candidates/
  publish_images.py        # 3) copy best candidate to final paths
  images/
    items.json             # master list: 22 product bases + 9 variants + 94 ingredients
    prompts.jsonl          # 116 prompts (regenerated by build_image_prompts.py)
    candidates/            # working dir for downloaded images
      <slug>__cand1.jpg    # candidate 1
      <slug>__cand2.jpg    # candidate 2
      ...
    run_log.jsonl          # per-item generation log (status, size, time)
  herebus.xlsx             # source workbook (Saskia's data)
  herebus_seed_canonical.json  # extracted seed data
  extract_canonical.py     # workbook → JSON
  build_seed_pieces.py     # JSON → sazon.py pieces
  apply_seed_patches.py    # pieces → sazon.py edits
```

## Resuming after a partial run

Both `generate_images.py` and `publish_images.py` are idempotent:
- `generate_images.py` skips any item that already has a candidate file
- `publish_images.py` skips any item whose final path exists (unless `--force`)

So if step 5 fails after generating 8/22 products, just re-run the same command and it'll pick up at item 9.

## Future QC improvements (deferred)

The current pipeline has no automatic QC. The plan is to:
1. Generate 3 candidates per item
2. Use a vision model to score each on 5 criteria: matches aesthetic? correct subject? no people? good texture? no AI gloss?
3. Auto-pick the best one
4. Save the score to `data/images/qc_log.jsonl`

Until then, manual review. The candidates are clearly named (`<slug>__cand<N>.jpg`) and small enough (~300KB) to browse in bulk.

## Future model swap (if MiniMax changes)

`generate_images.py` has a single `_call_minimax_image()` function. To add a new model, add a sibling function for that provider's API shape and dispatch based on an env var (e.g. `IMAGE_PROVIDER=comfy_cloud` or `IMAGE_PROVIDER=minimax`). The rest of the pipeline is provider-agnostic.
