# CI/CD Quality Policy

**Purpose:** Define which quality gates run, their severity, and auto-fix permissions by branch/tag context.  
**Scope:** Policy resolution, gate selection, and reporting (not gate implementation).  

---

## Files

- **Default policy:** `cicd/config/quality-policy.default.json`
- **Override policy:** `cicd/config/quality-policy.override.json`
- **Resolver script:** `cicd/scripts/resolve-quality-policy.ps1`
- **Policy report artifact:** `policy-report` (JSON + markdown summary)

---

## How It Works

1. Pipeline runs `resolve-quality-policy.ps1`.
2. Default policy is loaded, then override policy is merged.
3. The best matching context is selected using build reason, branch, or tag.
4. The resolved gate settings are exported as pipeline variables.
5. A policy report is published as a build artifact and summary.

---

## Policy Schema (Overview)

```json
{
  "schemaVersion": 1,
  "defaultContext": "default-branch",
  "defaults": {
    "gates": {
      "BuildSolution": { "enabled": true, "severity": "error", "autoFix": "none" }
    }
  },
  "contexts": [
    {
      "name": "branch-main",
      "match": { "branch": "refs/heads/main" },
      "overrides": {
        "gates": {
          "Benchmarks": { "enabled": true }
        }
      }
    }
  ]
}
```

### Match Fields

- `reason`: Build reason (e.g., `PullRequest`)
- `branch`: Exact `refs/heads/...`
- `branchPrefix`: Prefix match (e.g., `refs/heads/release/`)
- `branchRegex`: Regex match for branch
- `tagPrefix`: Tag prefix (e.g., `release-`)
- `tagRegex`: Regex match for tag

---

## Severity Mapping

Gate severities map to pipeline outcomes:

- **error**: `##vso[task.logissue type=error]` and fail the gate
- **warning**: `##vso[task.logissue type=warning]` and continue
- **info**: log only (no failure)

---

## Override Policy Guidance

Override policy should contain only differences from defaults:

```json
{
  "schemaVersion": 1,
  "contexts": [
    {
      "name": "branch-develop",
      "overrides": {
        "gates": {
          "MutationTesting": { "enabled": false }
        }
      }
    }
  ]
}
```

---

## Policy Report Artifact

The resolver publishes:

- `policy-report.json` - machine-readable resolved policy
- `policy-report.md` - pipeline summary

Use these to confirm the selected context and gate settings.
