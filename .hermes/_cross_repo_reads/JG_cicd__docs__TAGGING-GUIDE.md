# Git Tagging Guide for CI/CD Releases

**Version:** 4.0.0  
**Last Updated:** 2025-12-04  
**Applies To:** eneve.domain  
**Implementation Status:** ✅ Fully Operational (60/60 Gold Standard)

---

## ✅ Implementation Status

**What Works Today (eneve.domain):**
- ✅ Tag parsing and validation
- ✅ Version extraction from tags
- ✅ Package creation with tag versions
- ✅ SBOM generation
- ✅ All quality gates (security, coverage, documentation)
- ✅ Artifact publishing to Azure DevOps
- ✅ **Automated publishing to test feed (RC packages)**
- ✅ **Automated publishing to production feed (releases)**

**Current Workflow:**
1. Create tag (`test-1.0.0-rc1` or `release-1.0.0`)
2. Pipeline runs all quality gates
3. Package and SBOM created
4. **Package automatically published to appropriate feed**
5. Package ready for consumption

**Status:** 60/60 (A++) - Fully Operational ✅

For detailed status, see [PIPELINE-STATUS.md](PIPELINE-STATUS.md).  
For Git branching workflow, see [BRANCHING-GUIDE.md](BRANCHING-GUIDE.md).

---

## Table of Contents

1. [Overview](#overview)
2. [Tag Format Specification](#tag-format-specification)
3. [Tag Types](#tag-types)
4. [RC Workflow Overview](#rc-workflow-overview)
5. [Semantic Versioning](#semantic-versioning)
6. [Tag Management Commands](#tag-management-commands)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)

---

## Overview

Tags trigger versioned CI/CD pipelines and determine package versions. They follow strict naming conventions that control:
- Package version numbers
- Deployment environment (test vs production)
- Pre-release status (RC, alpha, beta)

**Key Principles:**
- Tags are immutable - never reuse or force-push
- Tags drive automated pipeline execution
- Tag type determines publishing destination

**Prerequisites:** Understand Git branching first - see [BRANCHING-GUIDE.md](BRANCHING-GUIDE.md)

---

## Tag Format Specification

### Format

```
[type]-[version][-suffix]
```

### Components

| Component | Required | Description | Examples |
|-----------|----------|-------------|----------|
| **type** | ✅ Yes | Deployment target | `release`, `test`, `coverage`, `security` |
| **version** | ✅ Yes | Semantic version (X.Y.Z) or YYYYMMDD | `1.0.0`, `2.1.5`, `20251204` |
| **suffix** | ❌ No | Pre-release identifier or description | `rc1`, `rc2`, `beta`, `alpha`, `monthly-audit` |

### Examples

```bash
release-1.0.0         # Production GA release
release-1.0.1         # Production patch
test-1.0.0-rc1        # Release candidate 1
test-1.0.0-rc2        # Release candidate 2 (after fixes)
test-2.0.0-alpha      # Alpha build
coverage-1.0.0        # Coverage analysis only
security-20251204     # Security audit
```

---

## Tag Types

### `release-*` (Production Releases)

**Purpose:** Production-ready releases  
**Branches:** `main` only  
**Pipeline Actions:**
- ✅ Run full 5-stage pipeline
- ✅ Security scanning
- ✅ Coverage threshold **80%**
- ✅ Generate SBOM
- ✅ Publish to production feed automatically

**When to Use:**
- After successful RC testing
- Merged to `main` branch
- Ready for production deployment

**Examples:**
```bash
release-1.0.0         # Major release
release-1.2.0         # Minor release
release-1.2.1         # Patch release
```

---

### `test-*` (Test Environment Releases)

**Purpose:** Release candidates and pre-production testing  
**Branches:** `release/*`, `hotfix/*`  
**Pipeline Actions:**
- ✅ Run full 5-stage pipeline
- ✅ Security scanning
- ✅ Coverage threshold **70%**
- ✅ Generate SBOM
- ✅ Publish to test feed automatically

**When to Use:**
- Before promoting to production
- Integration testing
- UAT validation

**Examples:**
```bash
test-1.0.0-rc1        # Release candidate 1
test-1.0.0-rc2        # RC 2 (after bug fixes)
test-1.0.1-rc1        # Patch release candidate
test-2.0.0-alpha      # Alpha/experimental
```

---

### `coverage-*` (Coverage Analysis Only)

**Purpose:** Run tests and coverage without publishing  
**Branches:** Any  
**Pipeline Actions:**
- ✅ Build and test
- ✅ Security scanning
- ✅ Coverage analysis
- ❌ NO package publishing (by design)

**When to Use:**
- Verify coverage on feature branches
- Test pipeline without publishing
- Coverage experiments

**Examples:**
```bash
coverage-1.0.0        # Coverage analysis
```

---

### `security-*` (Security Audit Only)

**Purpose:** On-demand security vulnerability scanning  
**Branches:** Any  
**Pipeline Actions:**
- ✅ Build and validate
- ✅ Security scanning (with color output)
- ⏭️ NO coverage analysis
- ⏭️ NO package creation
- ⏭️ NO documentation report

**When to Use:**
- Monthly security audits
- Before major releases
- After dependency updates
- Compliance checks
- Quick vulnerability assessment

**Examples:**
```bash
security-20251204                    # Daily audit
security-20251204-pre-release       # Pre-release check
security-20251204-monthly-audit     # Monthly compliance
```

**Tag Format:** `security-YYYYMMDD[-description]`

**Future Enhancement:** n8n webhook integration planned for automated vulnerability notifications

---

## RC Workflow Overview

### Release Candidate Process

**Goal:** Test thoroughly before production release

```
1. Create RC Tag
   ↓
2. Pipeline Runs (all quality gates)
   ↓
3. Test Package
   ↓
4a. Issues Found? → Fix → Create RC2 (go to step 2)
4b. Tests Pass? → Continue
   ↓
5. Promote to Production (release-* tag)
```

### Complete RC Example

```bash
# Step 1: Create RC1 on release branch
git checkout release/1.2
git tag -a test-1.2.0-rc1 -m "RC1 for version 1.2.0"
git push origin test-1.2.0-rc1

# Pipeline runs, package created as 1.2.0-rc1

# Step 2: Test the RC package
# - Integration tests
# - Manual testing
# - UAT validation

# Step 3a: If issues found
git commit -m "fix: bug found in RC1"
git tag -a test-1.2.0-rc2 -m "RC2 - Fixed critical bug"
git push origin test-1.2.0-rc2

# Test RC2... repeat until clean

# Step 3b: When RC passes all tests
# Merge to main (see BRANCHING-GUIDE.md)
git checkout main
git merge release/1.2 --no-ff -m "Release 1.2.0"
git push origin main

# Step 4: Tag production release
git tag -a release-1.2.0 -m "Production release 1.2.0"
git push origin release-1.2.0

# Production pipeline runs, publishes to production feed
```

**For complete branch workflows:** See [BRANCHING-GUIDE.md](BRANCHING-GUIDE.md)

---

## Semantic Versioning

### Format: `MAJOR.MINOR.PATCH`

```
1.2.3
│ │ │
│ │ └─ PATCH: Bug fixes, patches
│ └─── MINOR: New features (backward compatible)
└───── MAJOR: Breaking changes
```

### When to Increment

#### MAJOR Version (X.0.0)
**Increment when:**
- Breaking API changes
- Incompatible dependency updates
- Major architectural changes
- Removal of deprecated features

**Examples:** `1.0.0` → `2.0.0`

#### MINOR Version (X.Y.0)
**Increment when:**
- New features added (backward compatible)
- Enhancements to existing features
- New optional dependencies
- Deprecation notices (not removal)

**Examples:** `1.2.0` → `1.3.0`

#### PATCH Version (X.Y.Z)
**Increment when:**
- Bug fixes
- Security patches
- Performance improvements (no feature changes)
- Documentation updates
- Internal refactoring (no external changes)

**Examples:** `1.2.0` → `1.2.1`

### Version-Branch Relationship

**Key Concept:** Release branches use `MAJOR.MINOR`, tags use `MAJOR.MINOR.PATCH`

```
release/1.2   <- Branch for all 1.2.x releases
  │
  ├─ test-1.2.0-rc1
  ├─ test-1.2.0-rc2
  ├─ release-1.2.0      <- GA on main
  │
  ├─ test-1.2.1-rc1
  └─ release-1.2.1      <- Patch on main
```

One `release/X.Y` branch supports all `X.Y.Z` patch releases.

---

## Tag Management Commands

### List Tags

```bash
# All tags
git tag

# Filter by pattern
git tag -l "release-*"      # Production releases
git tag -l "test-1.2.*"     # All RCs for 1.2.x
git tag -l "coverage-*"     # Coverage tags

# Show tag details
git show release-1.0.0
```

### Create Tags

```bash
# Annotated tag (REQUIRED)
git tag -a test-1.0.0-rc1 -m "Release Candidate 1 for version 1.0.0"

# Push tag (triggers pipeline)
git push origin test-1.0.0-rc1

# Create and push in one command
git tag -a release-1.0.0 -m "Production release 1.0.0" && git push origin release-1.0.0
```

**Always use `-a` for annotated tags** - lightweight tags are not supported by the pipeline.

### Delete Tags

```bash
# Delete local tag
git tag -d test-1.0.0-rc1

# Delete remote tag
git push origin --delete test-1.0.0-rc1

# Delete both
git tag -d test-1.0.0-rc1 && git push origin --delete test-1.0.0-rc1
```

---

## Branch-Tag Rules

### Which Tags on Which Branches

| Branch Type | Allowed Tags | Blocked Tags |
|-------------|--------------|--------------|
| `main` | ✅ `release-*`, `security-*` | ❌ `test-*`, `coverage-*` |
| `release/*` | ✅ `test-*`, `coverage-*`, `security-*` | ❌ `release-*` |
| `develop` | ✅ `security-*` | ❌ Other tags |
| `feature/*` | ✅ `security-*` | ❌ Other tags |
| `hotfix/*` | ✅ `test-*`, `security-*` | ❌ `release-*` |

**Enforcement:** Not yet automated - manual discipline required

---

## Troubleshooting

### Problem: "Tag already exists"

**Cause:** Trying to recreate existing tag

**Solution:** Increment RC number
```bash
# Don't delete and recreate test-1.0.0-rc1
# Instead, create rc2
git tag -a test-1.0.0-rc2 -m "Release Candidate 2"
git push origin test-1.0.0-rc2
```

### Problem: Pipeline doesn't trigger

**Check:**
1. Tag format: `[type]-[X.Y.Z][-suffix]`
2. Tag is annotated (not lightweight)
3. Tag pushed to remote
4. Azure DevOps tag triggers enabled

**Verify:**
```bash
git tag -l            # Should show your tag
git ls-remote --tags  # Should show on remote
```

### Problem: "Invalid tag format" error

**Valid formats:**
- `release-1.0.0`
- `test-1.0.0-rc1`
- `coverage-2.1.3`
- `security-20251204`
- `security-20251204-monthly-audit`

**Invalid formats:**
- `v1.0.0` (missing type)
- `release-1.0` (incomplete version - need X.Y.Z)
- `test_1.0.0` (underscores not allowed)
- `1.0.0` (missing type)
- `security-invalid` (security tags need YYYYMMDD format)

**Fix:**
```bash
# Delete wrong tag
git tag -d wrong-tag-name
git push origin --delete wrong-tag-name

# Create correct tag
git tag -a release-1.0.0 -m "Production release"
git push origin release-1.0.0
```

### Problem: Tagged wrong branch

**Scenario:** Created `release-*` tag on `release/` branch instead of `main`

**Solution:**
```bash
# Delete tag from wrong branch
git tag -d release-1.0.0
git push origin --delete release-1.0.0

# Merge to main first
git checkout main
git merge release/1.2 --no-ff
git push origin main

# Tag correctly on main
git tag -a release-1.0.0 -m "Production release"
git push origin release-1.0.0
```

### Problem: Need to skip RC workflow

**Not Recommended** - but for hotfixes:

```bash
# Hotfix can tag test-* for quick validation
git checkout hotfix/EPP-999
git tag -a test-1.0.1-rc1 -m "Hotfix RC"
git push origin test-1.0.1-rc1

# After fast testing, promote immediately
git checkout main
git merge hotfix/EPP-999 --no-ff
git push origin main
git tag -a release-1.0.1 -m "Hotfix release"
git push origin release-1.0.1
```

---

## Best Practices

### 1. Always Use Annotated Tags

```bash
# ✅ Good (annotated)
git tag -a release-1.0.0 -m "Production release 1.0.0"

# ❌ Bad (lightweight - won't work)
git tag release-1.0.0
```

### 2. Always Test with RC First

```bash
# ✅ Good workflow
git tag test-1.0.0-rc1    # Test first
# ... testing ...
git tag release-1.0.0     # Then production

# ❌ Bad (skipping RC)
git tag release-1.0.0     # Direct to production
```

### 3. Never Reuse Tag Names

Tags are immutable. If RC1 fails, create RC2.

```bash
# ✅ Good
git tag test-1.0.0-rc1
# Issue found
git tag test-1.0.0-rc2

# ❌ Bad
git tag -d test-1.0.0-rc1
git tag test-1.0.0-rc1  # Different commit!
```

### 4. Tag After Branch Merge

```bash
# ✅ Good (tag after merge to main)
git checkout main
git merge release/1.2 --no-ff
git push origin main
git tag -a release-1.2.0 -m "Release 1.2.0"
git push origin release-1.2.0

# ❌ Bad (tag before merge)
git checkout release/1.2
git tag -a release-1.2.0  # Wrong branch!
```

### 5. Use Meaningful Tag Messages

```bash
# ✅ Good
git tag -a release-1.0.0 -m "Production release 1.0.0 - User authentication and reporting"

# ❌ Bad
git tag -a release-1.0.0 -m "v1.0.0"
```

---

## Quick Reference

### Tag Format

```
[type]-[MAJOR].[MINOR].[PATCH][-suffix]
[type]-[YYYYMMDD][-description]

Examples:
  release-1.2.0       # Production
  test-1.2.0-rc1      # Release candidate
  test-1.2.0-rc2      # After fixes
  coverage-1.2.0      # Coverage only
  security-20251204   # Security audit
```

### Common Commands

```bash
# Create RC tag (on release/X.Y branch)
git tag -a test-1.2.0-rc1 -m "RC1 for 1.2.0"
git push origin test-1.2.0-rc1

# Create production tag (on main branch)
git tag -a release-1.2.0 -m "Production release 1.2.0"
git push origin release-1.2.0

# List tags
git tag -l                  # All
git tag -l "release-*"      # Production only
git tag -l "test-1.2.*"     # RCs for 1.2.x
git tag -l "security-*"     # Security audits

# Delete tag
git tag -d test-1.2.0-rc1
git push origin --delete test-1.2.0-rc1
```

### Version Incrementing

```
Breaking change  → MAJOR.0.0     (e.g., 1.2.3 → 2.0.0)
New feature      → X.MINOR.0     (e.g., 1.2.3 → 1.3.0)
Bug fix          → X.Y.PATCH     (e.g., 1.2.3 → 1.2.4)
```

### RC Workflow

```
release/1.2 branch
    ↓
test-1.2.0-rc1 (test)
    ↓
Issues? → Fix → test-1.2.0-rc2 (test again)
    ↓
Clean? → Merge to main
    ↓
release-1.2.0 (production)
```

---

## Related Documentation

**Essential Guides:**
- **[BRANCHING-GUIDE.md](BRANCHING-GUIDE.md)** - Git branching workflow (read first!)
- **[QUICK-REFERENCE.md](QUICK-REFERENCE.md)** - Daily commands
- **[PIPELINE-STATUS.md](PIPELINE-STATUS.md)** - Current pipeline capabilities
- **[README.md](README.md)** - Documentation index

**CI/CD Configuration:**
- `../azure-pipelines.yml` - Actual pipeline configuration

---

## Implementation Notes

**Current Status: 59/60 (A+)**

### ✅ Fully Operational
- Tag parsing and validation
- Version extraction and package versioning
- All quality gates (build, security, coverage, documentation)
- SBOM generation
- Artifact publishing to Azure DevOps

### ⚠️ Requires Configuration (1-2 hours)
- Internal test feed for RC packages
- Production feed for releases
- Pipeline YAML updates to enable publishing

### 📋 To Reach 60/60
1. Configure NuGet feeds
2. Update pipeline YAML publishing tasks
3. Test RC workflow end-to-end
4. Update documentation

See [PIPELINE-STATUS.md](PIPELINE-STATUS.md) for detailed roadmap.

---

**Document Version:** 3.0.0  
**Last Updated:** 2025-12-04  
**Changes:** Refactored to focus on tagging only, branching moved to BRANCHING-GUIDE.md  
**Maintained By:** DevOps Team
