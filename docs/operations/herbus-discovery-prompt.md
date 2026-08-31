# HEREBUS discovery prompt for Saskia's PC

> **For Saskia** (and OpenCode on her machine). Reads the local filesystem, finds files that matter for the HEREBUS engagement, writes a manifest, never copies content anywhere without explicit per-file approval.

**Goal:** Produce a structured inventory of **only the files relevant to the HEREBUS / Saskia Weiss Vander engagement** on this PC, so the team can plan the v1 catalog import without manual directory tours.

**Strict scope:** Any file NOT classified as relevant is **ignored** — no copy, no excerpt, no path logged in the manifest. This is enforced by the filter, not by trust.

**Repository context:**

- `Ai-Whisperers/saskia` — engagement repo (this is where the new RMS app will live)
- `Ai-Whisperers/saskia-personal-context` — family + foodbiz data, currently public-by-decision; OPSEC rules in `AGENTS.md` apply
- `IvanWeissVanDerPol/Saskia` — old Flask prototype, archived 2025-07, do NOT touch

---

## What counts as "relevant"

A file is **relevant** if it falls into **exactly one** of these categories:

| Category | Examples | Why |
|---|---|---|
| **HEREBUS workbooks (canonical)** | `HEREBUS_FoodBiz.xlsx`, `HEREBUS_Suppliers.xlsx`, `HEREBUS_Analisis.xlsx`, `HEREBUS_Comparacion_Proveedores.xlsx`, `RECETARIO_EN_BLANCO.xlsx` | The v1 catalog import (dev plan Task 6) |
| **Other .xlsx with foodbiz data** | Any Excel file whose filename or first-sheet name contains any of: `recipe`, `receta`, `inventario`, `inventory`, `compra`, `pedido`, `venta`, `proveedor`, `supplier`, `costo`, `cost`, `margen`, `margin`, `foodbiz`, `herebus`, `panaderia`, `panadería`, `bakery`, `pastel`, `ingredients`, `ingredientes`, `stock`, `menu`, `menú`, `catalogo`, `catálogo` | Possibly v1 catalog pieces we don't know about |
| **Recipe-related text files** | `.md`, `.txt`, `.docx`, `.csv` whose filename contains any of: `recipe`, `receta`, `ingrediente`, `ingredient`, `cantidad`, `quantity`, `rinde`, `yield`, `porcion`, `porción`, `muffin`, `cheesecake`, `stroop`, `ontbijtkoek`, `frikandel`, `ketjap`, `hojaldre`, `appeltaart`, `tompoezen`, `oliebollen`, `babka` | Recipe notes, drafts, exports |
| **HEREBUS-related Python files** | `.py` files with `foodbiz`, `herebus`, `panaderia`, `bakery`, `recipe`, `receta`, `inventory`, `inventario` in filename or top-of-file docstring | Possible spreadsheet builders she or Ivan wrote |
| **Supplier / pricing data** | Any file with `.csv` extension AND header containing: `supplier`, `proveedor`, `price`, `precio`, `ingredient`, `ingrediente`, `cost`, `costo`, `bulk` | Supplier catalog, price history |
| **Google Drive sync leftovers** | `.gsheet` files in `~/Library/Application Support/Google Drive File Stream/` (Mac) or `%LocalAppData%\Google\DriveFS\` (Windows) containing foodbiz-named files | Local cache of Drive Excels she worked on offline |
| **WhatsApp catalog exports** | `.txt`/`.csv` files exported from WhatsApp Business catalog feature with foodbiz product names | Catalog data |

**Anything not matching one of these categories is OUT OF SCOPE and is ignored entirely** — including but not limited to:

- Personal photos (Photos library, Downloads, Desktop screenshots)
- Browser cache / history / cookies
- WhatsApp Web cache (message contents, contacts, media)
- Email (any client: Mail.app, Outlook, Thunderbird, Gmail offline)
- Banking apps, medical records, Kiki's files
- Random downloads (PDFs, ZIPs, installers)
- Project files for other clients or work
- Source code for unrelated projects
- Browser bookmarks / saved passwords / keychain exports
- Cache from any LLM, AI agent, IDE

---

## Output format

Write the manifest to `~/herbus-discovery-manifest.json` (overwrite if exists). Schema:

```json
{
  "generated_at": "<ISO 8601 timestamp>",
  "operator": "<the human who ran this — typically Saskia>",
  "machine": {
    "os": "<macos | windows | linux>",
    "hostname": "<machine hostname>",
    "username": "<operator username>"
  },
  "engagement_context": {
    "repos": {
      "engagement": "https://github.com/Ai-Whisperers/saskia",
      "personal_context": "https://github.com/Ai-Whisperers/saskia-personal-context"
    },
    "dev_plan_doc": "docs/plans/2026-08-31-rms-fase-1-dev-plan.md",
    "scope_locked": "RMS local on this PC, FastAPI + SQLite + openpyxl, 70h quote"
  },
  "summary": {
    "total_relevant_files": 0,
    "total_relevant_bytes": 0,
    "by_category": {
      "herbus_workbooks_canonical": 0,
      "xlsx_with_foodbiz_data": 0,
      "recipe_text_files": 0,
      "python_files": 0,
      "supplier_pricing": 0,
      "drive_sync_leftovers": 0,
      "whatsapp_catalog_exports": 0
    }
  },
  "files": [
    {
      "path": "/absolute/path/to/file.xlsx",
      "size_bytes": 88821,
      "last_modified": "<ISO 8601>",
      "category": "herbus_workbooks_canonical",
      "matched_keywords": ["herebus"],
      "first_sheet_or_first_line": "<truncated to 200 chars, no full content>",
      "is_in_known_repo_path": true | false,
      "notes": "<free text, optional>"
    }
  ],
  "ignored": {
    "rule": "Files not matching any category above were not opened, not counted, not logged.",
    "directories_skipped_entirely": [
      "/Users/saskia/Library/Application Support/Google/Chrome/",
      "/Users/saskia/.ssh/",
      "/Users/saskia/Library/Mail/",
      "<etc.>"
    ]
  }
}
```

**`first_sheet_or_first_line`** field: For xlsx files, list the names of the sheets (not their content). For text/csv files, capture only the first line truncated to 200 chars. **No full content ever leaves this machine unless explicitly approved per file below.**

---

## Procedure

### Step 1: Pre-flight (read-only environment checks)

Run these BEFORE scanning anything. Report results in the manifest's `machine` field.

```bash
# OS detection
uname -s  # Darwin | Linux | MINGW64_NT-...

# Hostname and username
hostname
whoami

# Date/time (for the timestamp)
date -u +"%Y-%m-%dT%H:%M:%SZ"
```

### Step 2: Build the skip-list (directories to never traverse)

Add these to `directories_skipped_entirely` in the manifest. They contain PII or noise.

**macOS:**
- `~/Library/` (entire tree)
- `~/.ssh/`, `~/.gnupg/`, `~/.aws/`, `~/.config/gh/`
- `~/Library/Mail/`, `~/Library/Calendars/`, `~/Library/Reminders/`
- `~/Library/Messages/`, `~/Library/Containers/com.apple.MobileSMS/`
- `~/Library/Application Support/Google/Chrome/`, `~/Library/Caches/Google/Chrome/`
- `~/Library/Application Support/Firefox/`
- `~/Library/Group Containers/`, `~/Library/Logs/`
- `~/Pictures/Photos Library.photoslibrary/` (entire Photos library)
- `~/Downloads/` — scan top-level only, do not recurse into folders (most of Downloads is installers/PDFs/ZIPs)
- `~/Desktop/` — scan top-level only

**Windows:**
- `%LocalAppData%\Google\Chrome\User Data\`
- `%AppData%\Mozilla\Firefox\Profiles\`
- `%UserProfile%\.ssh\`, `%UserProfile%\.aws\`, `%UserProfile%\.gnupg\`
- `%LocalAppData%\Microsoft\Outlook\`
- `%UserProfile%\Documents\My Music\`, `\My Pictures\`, `\My Videos\`
- `%UserProfile%\Downloads\` — top-level only
- `%UserProfile%\Desktop\` — top-level only

**Linux:** (less likely for this engagement, but for completeness)
- `~/.ssh/`, `~/.gnupg/`, `~/.aws/`, `~/.config/gh/`
- `~/.mozilla/`, `~/.config/google-chrome/`
- `~/Downloads/`, `~/Desktop/` — top-level only
- `~/.local/share/Trash/`

### Step 3: Scan recursively — but ONLY in approved roots

**Approved roots to scan recursively:**

- `~/Documents/` (entire tree)
- `~/Library/CloudStorage/` (Mac) or `%UserProfile%\OneDrive\`, `%UserProfile%\Dropbox\` (Windows) — entire tree
- Any Google Drive File Stream mount point: `~/Library/CloudStorage/GoogleDrive-*/My Drive/` on Mac, or `G:\My Drive\` on Windows
- `~/Projects/` if it exists
- `~/repos/` if it exists
- Any folder explicitly named `HEREBUS`, `foodbiz`, `panaderia`, `Saskia Bakery`, `saskia-personal-context`, `Saskia`, `Bakery`, `panadería`

**Approved roots to scan top-level only (no recursion):**

- `~/Downloads/`
- `~/Desktop/`

### Step 4: Apply the relevance filter

For each file encountered, decide if it matches one of the seven categories above. Use this decision procedure:

```
1. Is the file path under a directory in `directories_skipped_entirely`?
   YES → skip entirely, do not log

2. Is the file path under `~/Downloads/` or `~/Desktop/`?
   YES → only consider the top-level file, do not recurse

3. Does the file extension match the categories?
   .xlsx, .xlsm, .xls → check categories 1, 2, 5
   .md, .txt, .docx, .csv → check categories 3, 5, 7
   .py → check category 4
   .gsheet → check category 6

4. Does the FILENAME contain any keyword from the relevant categories?
   e.g., filename = "Stroop Waffle receta final.xlsx"
        → contains "receta" → category 3 candidate

5. If .xlsx: read just the sheet names (openpyxl is fine for this — it doesn't load cell content if you only call sheetnames).
   Does any sheet name match keywords? → category 2 candidate

6. If .csv/.txt: read ONLY the first line. Does it match the supplier-pricing keyword set?
   YES → category 5 candidate
   NO → category 3 candidate if recipe-related, otherwise ignore

7. If .py: read ONLY the first 50 lines or the docstring. Does the docstring/module name match foodbiz keywords?
   YES → category 4 candidate
   NO → ignore

8. If .gsheet: it's a Google Drive sync stub. The real file is on Drive. Log the stub path with size 0 and category 6. The team will fetch the real file via Drive API.

9. If still no match: IGNORE. Do not log in manifest. Do not record path.
```

### Step 5: For each MATCHING file, capture metadata ONLY

For each file that passes the filter, capture:

- Absolute path
- Size in bytes
- Last-modified timestamp (ISO 8601)
- Matched category
- Which keyword(s) matched
- For xlsx: list of sheet names (NOT cell content)
- For csv/txt: first line only, truncated to 200 chars (NOT full file)
- Whether the path is already inside a known repo (e.g., `saskia-personal-context`)

**NEVER** for any matching file:

- Read full content
- Print contents to stdout
- Copy the file anywhere
- Upload to any service
- Include file contents in the manifest

### Step 6: Write the manifest

Write the final JSON to `~/herbus-discovery-manifest.json`.

Also print a one-screen summary to stdout:

```
=== HEREBUS discovery summary ===
Total relevant files: N
Total size:           ~M MB (across all matching files)

By category:
  herbus_workbooks_canonical:    X
  xlsx_with_foodbiz_data:       X
  recipe_text_files:             X
  python_files:                  X
  supplier_pricing:              X
  drive_sync_leftovers:          X
  whatsapp_catalog_exports:      X

Manifest written to: ~/herbus-discovery-manifest.json

Next step (operator decision, NOT this script):
  - Review the manifest
  - For each file you choose to share, send it explicitly to the team
    (upload to Drive, share via WhatsApp, or commit via PR)
  - The script does NOT auto-share anything.
```

### Step 7: Exit cleanly

Exit 0 if the manifest was written. Exit 1 if any step failed.

---

## Hard constraints — DO NOT VIOLATE

These are non-negotiable. If any step below seems necessary to "complete the task", **stop and ask the operator instead**.

### Constraint 1: No file content leaves the machine

The manifest contains metadata + first-line/sheet-name only. **No file content is ever written to the manifest, the stdout, the logs, or any network destination.**

If a relevant file's content needs to be examined (e.g., to confirm the relevance classification), the operator must do that manually after seeing the manifest. The script never does it.

### Constraint 2: No file is auto-shared, auto-committed, or auto-uploaded

The manifest is local output. The script does not:

- `git add` anything
- `curl` to any URL
- `rsync` anywhere
- Copy to a "shared" folder without explicit per-file approval

If the operator wants to share a file from the manifest, they do it manually after review.

### Constraint 3: No out-of-scope directories are traversed

The skip-list in Step 2 is exhaustive. If you encounter a path that smells like PII but isn't on the skip-list (e.g., a folder named `Family` in Documents), **stop and ask the operator** before adding it to the manifest.

### Constraint 4: The filter is conservative, not permissive

When in doubt about whether a file matches a category, **default to IGNORE**. The team can always re-run with a broader filter if the manifest looks too sparse. It's much harder to recover from accidentally leaking a non-relevant file than to re-run a discovery scan.

### Constraint 5: No execution of file contents

Even though `.py` files might be in scope, **never execute them** during the scan. Read only the first 50 lines (docstring). If a file looks dangerous (base64 blobs, network calls in first 50 lines), still log it as a candidate but flag it in the `notes` field for human review.

### Constraint 6: Treat this as audit-grade

The output of this script will be reviewed by the operator and possibly by Ivan. If you encounter any decision point where you're not sure, log it in a `_warnings` array at the top of the manifest and let the human decide. **Never silently make a "judgment call" that affects what's in the manifest.**

---

## Sample `~/herbus-discovery-manifest.json` (expected shape)

```json
{
  "generated_at": "2026-09-15T14:32:11Z",
  "operator": "saskia",
  "machine": {
    "os": "darwin",
    "hostname": "saskia-macbook.local",
    "username": "saskia"
  },
  "engagement_context": {
    "repos": {
      "engagement": "https://github.com/Ai-Whisperers/saskia",
      "personal_context": "https://github.com/Ai-Whisperers/saskia-personal-context"
    },
    "dev_plan_doc": "docs/plans/2026-08-31-rms-fase-1-dev-plan.md",
    "scope_locked": "RMS local on this PC, FastAPI + SQLite + openpyxl, 70h quote"
  },
  "_warnings": [],
  "summary": {
    "total_relevant_files": 12,
    "total_relevant_bytes": 458211,
    "by_category": {
      "herbus_workbooks_canonical": 5,
      "xlsx_with_foodbiz_data": 2,
      "recipe_text_files": 3,
      "python_files": 1,
      "supplier_pricing": 1,
      "drive_sync_leftovers": 0,
      "whatsapp_catalog_exports": 0
    }
  },
  "files": [
    {
      "path": "/Users/saskia/Documents/HEREBUS/data/HEREBUS_FoodBiz.xlsx",
      "size_bytes": 88821,
      "last_modified": "2026-08-15T10:23:45Z",
      "category": "herbus_workbooks_canonical",
      "matched_keywords": ["herebus"],
      "first_sheet_or_first_line": "sheets: [Instructions, Inventory, Recipe_Template, ...]",
      "is_in_known_repo_path": false,
      "notes": "Likely current working copy, newer than saskia-personal-context version"
    },
    {
      "path": "/Users/saskia/Library/CloudStorage/GoogleDrive-saski@gmail.com/My Drive/FoodBiz/Compras julio.csv",
      "size_bytes": 4521,
      "last_modified": "2026-07-30T16:00:00Z",
      "category": "supplier_pricing",
      "matched_keywords": ["compras"],
      "first_sheet_or_first_line": "fecha,proveedor,ingrediente,cantidad,precio_unitario,total",
      "is_in_known_repo_path": false,
      "notes": "July shopping data, may inform ingredient prices for the v1 costing"
    }
  ],
  "ignored": {
    "rule": "Files not matching any category above were not opened, not counted, not logged.",
    "directories_skipped_entirely": [
      "/Users/saskia/Library/",
      "/Users/saskia/Library/Application Support/Google/Chrome/",
      "/Users/saskia/.ssh/",
      "/Users/saskia/.aws/",
      "/Users/saskia/Library/Mail/",
      "/Users/saskia/Library/Containers/com.apple.MobileSMS/",
      "/Users/saskia/Library/Messages/",
      "/Users/saskia/Library/Application Support/Firefox/",
      "/Users/saskia/Library/Caches/",
      "/Users/saskia/Pictures/Photos Library.photoslibrary/"
    ]
  }
}
```

---

## How to use this manifest (for the operator, NOT for the script)

After the manifest is written:

1. **Read `~/herbus-discovery-manifest.json` yourself** before sharing anything.
2. **For each file in `files[]`**, decide explicitly:
   - ✅ "Yes, share this with the team" — manually copy / upload / commit
   - ❌ "No, even though the filter matched, I don't want to share this" — leave it; tell the team "this exists but I'm not sharing it"
   - ❓ "Not sure" — leave it; discuss with the team
3. **For each ✅ file**, the team decides where it goes:
   - If it's a HEREBUS workbook that's newer than `saskia-personal-context` → opens a new commit on the personal-context repo (operator OK required, per AGENTS.md rule #6)
   - If it's a new recipe or supplier note → commit to the engagement repo under `docs/intake/`
   - If it's a Python script we didn't know about → commit to `saskia-personal-context/04_foodbiz-management-system/python/` with provenance noted
4. **Nothing happens automatically.** This is a discovery tool, not a sync tool.

---

## When to run this

Three valid timings:

| Timing | Why | Who initiates |
|---|---|---|
| **Before signoff** (volunteer time) | Helps team understand scope; surfaces files we don't know exist; saves quoting surprise | Saskia, at her discretion |
| **At kickoff** (Day 0 of 70h quote, after first cuota + Drive + PC) | Becomes Task 0.5 of dev plan — a 30-min sub-step before Task 1 starts | Saskia + team |
| **Mid-build** (during Task 6, Excel import) | Discovers relevant files outside the Drive folder she shared; prevents incomplete v1 catalog | Saskia, during Task 6 |

**Don't run this and walk away.** The manifest is a starting point for conversation, not a substitute for one. The team should look at the manifest, ask "did we miss anything?", and only then proceed.

---

## Companion script (optional)

If the operator prefers to run this as a script rather than via OpenCode chat, the same logic is implementable as a Python script. Suggested file name:

`~/herbus-discovery.py`

Skeleton:

```python
#!/usr/bin/env python3
"""HEREBUS discovery — see HERBUS-DISCOVERY-PROMPT.md for full spec.

Run with: python3 ~/herbus-discovery.py
Output:   ~/herbus-discovery-manifest.json
"""
# ... see prompt for procedure ...
```

The OpenCode chat-based prompt above is preferred for v1 because:
- The operator can correct the agent's interpretations inline ("no, that folder is Kiki's, skip it")
- The category matching is fuzzy enough that chat-based review beats batch script
- The audit trail (OpenCode session log) is automatically preserved

Once the categories are stable, the script form can be extracted for repeat runs.

---

## What this prompt is NOT

- ❌ **Not** an auto-sync to the repo. Nothing happens automatically.
- ❌ **Not** a backup tool. Backups are a separate concern.
- ❌ **Not** a content reader. The script reads metadata + sheet names + first line only.
- ❌ **Not** a PII scanner. We deliberately IGNORE everything that isn't HEREBUS-relevant.
- ❌ **Not** a substitute for the dev plan. The dev plan is what gets built; this just finds the inputs.
- ❌ **Not** a free scoping exercise billed to the 70h quote. If run pre-signoff, it's volunteer time; if run mid-build, it's part of Task 0.5 or Task 6.

---

## Failure modes & recovery

| Symptom | Likely cause | Fix |
|---|---|---|
| Manifest says 0 relevant files | Filter too strict, OR files are in non-approved roots | Operator inspects `directories_skipped_entirely`, asks to extend approved roots, re-runs |
| OpenCode refuses to run (PermissionError on Mac) | macOS TCC blocking directory access | Operator grants Full Disk Access to the terminal/IDE in System Settings → Privacy & Security |
| Manifest includes a path that's clearly wrong (e.g., Kiki's folder) | Filter matched on a substring like "receta" in a filename that isn't foodbiz | Operator removes from `files[]`, tells team to ignore; future runs tighten the keyword list |
| Manifest is enormous (1000+ files) | Recursing into a wrong root (e.g., `node_modules`) | Add `node_modules/`, `.venv/`, `__pycache__/`, `.git/` to skip-list; re-run |
| Manifest misses a file the operator expected | File is in a non-approved root or has no filename/sheet/header match | Operator moves file to an approved root, then re-runs |
| Time-of-day check fails (e.g., on Windows without `date -u`) | Platform-specific command | Use Python `datetime.utcnow().isoformat()` instead |

---

## Quick-start commands (for Saskia)

After pasting this prompt into OpenCode on her PC:

```bash
# 1. Set up the output directory and verify OpenCode is configured
mkdir -p ~/
ls ~/.opencode 2>/dev/null && echo "opencode configured" || echo "needs setup"

# 2. Paste the prompt above into OpenCode TUI
#    (the agent will walk through Steps 1-7)

# 3. After the agent finishes:
cat ~/herbus-discovery-manifest.json | python3 -m json.tool | less

# 4. Decide per-file what to share
#    (no automation; explicit operator decision per file)

# 5. Send the manifest (NOT the files) to the team via WhatsApp
#    so we can review the inventory before deciding what to ingest
```

---

*Document version: 2026-09 (draft 1)*
*Engagement: Ai-Whisperers/saskia (Saskia Weiss Vander, food/bakery, Paraguay)*
*OPSEC contract: saskia-personal-context AGENTS.md rules apply — no new PII committed without explicit operator OK*
*Built for: pre-signoff discovery / kickoff Task 0.5 / mid-build Task 6 inventory*
