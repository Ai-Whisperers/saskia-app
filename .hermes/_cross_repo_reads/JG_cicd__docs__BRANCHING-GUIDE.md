# Git Branching Strategy Guide

**Version:** 1.0.0  
**Last Updated:** 2025-12-04  
**Applies To:** eneve.domain, eneve.ebase.foundation, eneve.ebase.datamigrator

---

## Table of Contents

1. [Overview](#overview)
2. [Branch Structure](#branch-structure)
3. [Branch Lifecycle](#branch-lifecycle)
4. [Common Workflows](#common-workflows)
5. [Branch Naming Conventions](#branch-naming-conventions)
6. [Branch Protection](#branch-protection)
7. [Best Practices](#best-practices)

---

## Overview

Our repositories use a **main/develop branching model** with structured supporting branches for features, fixes, releases, and hotfixes. This strategy enables parallel development, controlled releases, and long-term maintenance.

**Key Principles:**
- `main` = production-ready code
- `develop` = integration branch for next release
- Supporting branches = temporary, deleted after merge
- Release branches = long-lived for patch support

**For tag-based versioning:** See [TAGGING-GUIDE.md](TAGGING-GUIDE.md)

---

## Branch Structure

### Primary Branches (Permanent)

#### `main`
**Purpose:** Production-ready code  
**Lifespan:** Permanent  
**Protected:** Yes  
**Merges From:** `release/*`, `hotfix/*`  
**Merges To:** `develop` (after hotfix)

**Rules:**
- ✅ Always deployable to production
- ✅ Only receives merges (no direct commits)
- ✅ Every commit represents a release
- ✅ Tagged with `release-*` tags only

#### `develop`
**Purpose:** Integration branch for next release  
**Lifespan:** Permanent  
**Protected:** Yes  
**Merges From:** `feature/*`, `fix/*`, `release/*`, `hotfix/*`  
**Merges To:** `release/*`
**CI/CD:** Automatic builds on commit

**Rules:**
- ✅ Latest development changes
- ✅ Must always build successfully
- ✅ May be unstable but buildable
- ❌ Never tagged

---

### Supporting Branches (Temporary)

#### `feature/*`
**Purpose:** New features and enhancements  
**Source:** `develop`  
**Target:** `develop`  
**Lifespan:** Days to weeks  
**Naming:** `feature/[TICKET]-[description]`
**CI/CD:** No automatic builds on commit (validation via PR)

**Examples:**
- `feature/EPP-123-user-authentication`
- `feature/EPP-456-add-reporting-dashboard`

**Lifecycle:**
```bash
# Create
git checkout develop
git checkout -b feature/EPP-123-new-feature

# Develop...
git commit -m "feat: implement feature"

# Merge back
git checkout develop
git merge feature/EPP-123-new-feature --no-ff
git branch -d feature/EPP-123-new-feature
git push origin --delete feature/EPP-123-new-feature
```

---

#### `fix/*`
**Purpose:** Bug fixes for develop branch  
**Source:** `develop`  
**Target:** `develop`  
**Lifespan:** Hours to days  
**Naming:** `fix/[TICKET]-[description]`

**Examples:**
- `fix/EPP-789-validation-error`
- `fix/EPP-101-memory-leak`

**Lifecycle:**
```bash
# Create
git checkout develop
git checkout -b fix/EPP-789-bug-fix

# Fix...
git commit -m "fix: resolve bug"

# Merge back
git checkout develop
git merge fix/EPP-789-bug-fix --no-ff
git branch -d fix/EPP-789-bug-fix
```

---

#### `release/*`
**Purpose:** Release preparation and stabilization  
**Source:** `develop`  
**Target:** `main` (then back to `develop`)  
**Lifespan:** Long-lived (kept for patch releases)  
**Naming:** `release/[MAJOR].[MINOR]`
**CI/CD:** Automatic builds on commit

**Examples:**
- `release/1.0` (for all 1.0.x releases)
- `release/1.2` (for all 1.2.x releases)
- `release/2.0` (for all 2.0.x releases)

**Key Concept:** One `release/X.Y` branch supports all `X.Y.Z` patch releases.

**When to Create:**
- ✅ Ready to start RC testing for new MINOR/MAJOR version
- ✅ Features in `develop` complete and stable
- ✅ Planning integration/UAT testing

**When NOT to Create:**
- ❌ For patch releases (use existing `release/X.Y`)
- ❌ For hotfixes (use `hotfix/*`)

**Lifecycle:**
```bash
# 1. Create from develop
git checkout develop
git pull origin develop
git checkout -b release/1.2
git push origin release/1.2

# 2. Stabilize (allow bug fixes directly on branch)
git commit -m "fix: issue found in testing"

# 3. Merge to main when ready
git checkout main
git merge release/1.2 --no-ff -m "Release 1.2.0"
git push origin main

# 4. Merge back to develop
git checkout develop
git merge release/1.2 --no-ff
git push origin develop

# 5. KEEP BRANCH (for future patches)
# Do NOT delete - used for 1.2.1, 1.2.2, etc.
```

---

#### `hotfix/*`
**Purpose:** Emergency fixes for production  
**Source:** `main`  
**Target:** `main` (then to `release/*` and `develop`)  
**Lifespan:** Hours  
**Naming:** `hotfix/[TICKET]-[description]`

**Examples:**
- `hotfix/EPP-999-critical-security`
- `hotfix/EPP-888-production-crash`

**When to Use:**
- ✅ Critical production bug requiring immediate fix
- ✅ Security vulnerability discovered
- ✅ Data corruption issue

**Lifecycle:**
```bash
# 1. Create from main
git checkout main
git pull origin main
git checkout -b hotfix/EPP-999-critical-fix

# 2. Fix
git commit -m "fix: critical production issue"

# 3. Merge to main
git checkout main
git merge hotfix/EPP-999-critical-fix --no-ff
git push origin main

# 4. Merge to release branch (if active)
git checkout release/1.2
git merge hotfix/EPP-999-critical-fix --no-ff
git push origin release/1.2

# 5. Merge to develop
git checkout develop
git merge hotfix/EPP-999-critical-fix --no-ff
git push origin develop

# 6. Delete branch
git branch -d hotfix/EPP-999-critical-fix
git push origin --delete hotfix/EPP-999-critical-fix
```

---

## Branch Lifecycle

### Feature Development Flow

```
develop
  ├─→ feature/EPP-123 (create)
  │     ├─ commits...
  │     └─ PR review
  └─← merge feature/EPP-123 (delete after merge)
```

### Release Flow

```
develop (many features merged)
  └─→ release/1.2 (create for 1.2.0)
        ├─ bug fixes
        ├─ testing
        └─→ main (merge for 1.2.0)
              └─→ develop (merge back)
        
        (later, same branch)
        ├─ patch fixes
        └─→ main (merge for 1.2.1)
              └─→ develop (merge back)
```

### Hotfix Flow

```
main (production issue)
  └─→ hotfix/EPP-999 (create)
        ├─ critical fix
        └─→ main (merge)
              ├─→ release/1.2 (merge)
              └─→ develop (merge)
```

---

## Common Workflows

### Workflow 1: Standard Feature Development

```bash
# Day 1: Start feature
git checkout develop
git pull origin develop
git checkout -b feature/EPP-123-new-feature

# Days 2-N: Develop
git add .
git commit -m "feat: implement part 1"
git commit -m "feat: implement part 2"
git push origin feature/EPP-123-new-feature

# Final day: Merge
# Create PR: feature/EPP-123 → develop
# After approval:
git checkout develop
git pull origin develop
git merge feature/EPP-123-new-feature --no-ff
git push origin develop
git branch -d feature/EPP-123-new-feature
git push origin --delete feature/EPP-123-new-feature
```

### Workflow 2: Release Preparation

```bash
# Week 1: Create release branch
git checkout develop
git pull origin develop
git checkout -b release/1.3
git push origin release/1.3

# Week 2-3: Test and fix on release branch
git checkout release/1.3
git commit -m "fix: bug found in testing"
git push origin release/1.3

# After testing complete: Promote to production
git checkout main
git pull origin main
git merge release/1.3 --no-ff -m "Release version 1.3.0"
git push origin main

# Merge fixes back to develop
git checkout develop
git pull origin develop
git merge release/1.3 --no-ff
git push origin develop

# KEEP release/1.3 for future patches
```

### Workflow 3: Patch Release

```bash
# Use existing release branch
git checkout release/1.3
git pull origin release/1.3

# Fix bug
git commit -m "fix: critical bug in production"
git push origin release/1.3

# Promote to production
git checkout main
git merge release/1.3 --no-ff -m "Patch release 1.3.1"
git push origin main

# Merge to develop
git checkout develop
git merge release/1.3 --no-ff
git push origin develop
```

### Workflow 4: Emergency Hotfix

```bash
# Create hotfix from main
git checkout main
git pull origin main
git checkout -b hotfix/EPP-999-critical

# Fix immediately
git commit -m "fix: critical security vulnerability"

# Merge to main
git checkout main
git merge hotfix/EPP-999-critical --no-ff
git push origin main

# Merge to all active branches
git checkout release/1.3
git merge hotfix/EPP-999-critical --no-ff
git push origin release/1.3

git checkout develop
git merge hotfix/EPP-999-critical --no-ff
git push origin develop

# Delete hotfix branch
git branch -d hotfix/EPP-999-critical
git push origin --delete hotfix/EPP-999-critical
```

---

## Branch Naming Conventions

### Format

```
[type]/[TICKET]-[description]
```

### Components

| Component | Required | Description | Example |
|-----------|----------|-------------|---------|
| **type** | ✅ Yes | Branch type | `feature`, `fix`, `hotfix` |
| **TICKET** | ✅ Yes | Jira ticket ID | `EPP-123`, `PROJ-456` |
| **description** | ✅ Yes | Short kebab-case description | `add-user-auth`, `fix-validation` |

### Naming Rules

**✅ Good Names:**
- `feature/EPP-123-user-authentication`
- `fix/EPP-456-validation-error`
- `hotfix/EPP-999-critical-security`
- `release/1.2`

**❌ Bad Names:**
- `my-feature` (no type, no ticket)
- `feature-EPP-123` (wrong separator)
- `feature/EPP123-auth` (missing hyphen in ticket)
- `feature/EPP-123` (no description)
- `feature/EPP-123_user_auth` (underscores not allowed)

### Special Cases

**Release branches:**
```
release/[MAJOR].[MINOR]
```
- `release/1.0`
- `release/2.0`
- `release/1.3`

**No patch version** in branch name - one branch supports all patches.

---

## Branch Protection

### Main Branch Protection

**Azure DevOps Policies:**
```yaml
Branch: main
Policies:
  - Require pull request: true
  - Minimum reviewers: 2
  - Allow requestors to approve: false
  - Reset votes on push: true
  - Require linked work items: true
  - Block force push: true
  - Block branch deletion: true
  - Allow only squash merge: false (use --no-ff)
  - Build validation: Required
  - Status checks: All must pass
```

**Who Can Merge:**
- Release managers
- DevOps team
- Team leads (approved)

**Merge Sources:**
- ✅ `release/*` branches only
- ✅ `hotfix/*` branches only
- ❌ Never `develop`
- ❌ Never `feature/*`

---

### Develop Branch Protection

**Azure DevOps Policies:**
```yaml
Branch: develop
Policies:
  - Require pull request: true
  - Minimum reviewers: 1
  - Allow requestors to approve: true
  - Reset votes on push: false
  - Require linked work items: recommended
  - Block force push: true
  - Block branch deletion: true
  - Build validation: Required
  - Status checks: Build + Tests must pass
```

**Who Can Merge:**
- All developers (via PR)

**Merge Sources:**
- ✅ `feature/*`
- ✅ `fix/*`
- ✅ `release/*` (merge back)
- ✅ `hotfix/*` (merge back)

---

### Release Branch Protection

**Azure DevOps Policies:**
```yaml
Branch: release/*
Policies:
  - Require pull request: false (allow direct commits)
  - Block force push: true
  - Block branch deletion: true (keep for patches)
  - Build validation: Required
  - Direct commits allowed: true (for bug fixes)
```

**Who Can Commit:**
- Release managers
- QA team (bug fixes)
- Team leads

**Special Rules:**
- Allow direct commits (no PR required for bug fixes)
- Never delete (needed for patch releases)
- Must merge to main before promoting

---

## Best Practices

### 1. Always Use --no-ff for Merges

```bash
# ✅ Good: Preserves branch history
git merge feature/EPP-123 --no-ff

# ❌ Bad: Loses branch context
git merge feature/EPP-123 --ff
```

### 2. Delete Feature Branches After Merge

```bash
# After merge to develop
git branch -d feature/EPP-123
git push origin --delete feature/EPP-123
```

### 3. Keep Release Branches

```bash
# DO NOT DELETE after first release
# release/1.2 is used for 1.2.0, 1.2.1, 1.2.2, etc.
```

### 4. Pull Before Creating Branches

```bash
# ✅ Good
git checkout develop
git pull origin develop
git checkout -b feature/EPP-123

# ❌ Bad (may be out of date)
git checkout develop
git checkout -b feature/EPP-123
```

### 5. Commit Message Conventions

**Format:** `[type]: [description]`

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `style:` Code style (formatting)
- `refactor:` Code refactoring
- `test:` Adding tests
- `chore:` Maintenance

**Examples:**
```bash
git commit -m "feat: add user authentication"
git commit -m "fix: resolve validation error"
git commit -m "docs: update API documentation"
```

### 6. Keep Branches Up to Date

```bash
# For long-running feature branches
git checkout feature/EPP-123
git merge develop  # Regularly sync with develop
```

### 7. Use Descriptive Branch Names

```bash
# ✅ Good
feature/EPP-123-user-authentication
fix/EPP-456-null-reference-error

# ❌ Bad
feature/EPP-123
my-branch
```

---

## Integration with Tagging

### Branch-Tag Relationship

| Branch Type | Allowed Tags | Tag Examples |
|-------------|--------------|--------------|
| `main` | ✅ `release-*` only | `release-1.0.0`, `release-1.0.1` |
| `release/*` | ✅ `test-*`, `coverage-*` | `test-1.0.0-rc1`, `coverage-1.0.0` |
| `develop` | ❌ None | No tags allowed |
| `feature/*` | ❌ None | No tags allowed |
| `fix/*` | ❌ None | No tags allowed |
| `hotfix/*` | ✅ `test-*` (optional) | `test-1.0.1-rc1` |

**For complete tagging guide:** See [TAGGING-GUIDE.md](TAGGING-GUIDE.md)

---

## Troubleshooting

### Problem: Merge Conflict

**Solution:**
```bash
# During merge
git merge feature/EPP-123 --no-ff
# CONFLICT in file.cs

# Resolve manually
# Edit file.cs to resolve conflicts

git add file.cs
git commit -m "Merge feature/EPP-123 - resolved conflicts"
```

### Problem: Accidentally Committed to Wrong Branch

**Solution:**
```bash
# If not pushed yet
git log  # Find commit hash
git checkout correct-branch
git cherry-pick [commit-hash]
git checkout wrong-branch
git reset --hard HEAD~1
```

### Problem: Need to Abandon Feature

**Solution:**
```bash
# Delete local branch
git checkout develop
git branch -D feature/EPP-123

# Delete remote branch
git push origin --delete feature/EPP-123
```

### Problem: Release Branch Diverged from Develop

**Solution:**
```bash
# After release, always merge back to develop
git checkout develop
git merge release/1.2 --no-ff
git push origin develop
```

---

## Quick Reference

### Common Commands

```bash
# Create feature branch
git checkout develop && git pull
git checkout -b feature/EPP-123-description

# Create release branch
git checkout develop && git pull
git checkout -b release/1.2

# Create hotfix branch
git checkout main && git pull
git checkout -b hotfix/EPP-999-description

# Merge feature to develop
git checkout develop
git merge feature/EPP-123 --no-ff

# Merge release to main
git checkout main
git merge release/1.2 --no-ff

# Delete merged branch
git branch -d feature/EPP-123
git push origin --delete feature/EPP-123
```

### Branch Lifespan

```
main         ═══════════════════════════════ (permanent)
develop      ═══════════════════════════════ (permanent)
release/1.2  ──────────────────────────────→ (long-lived)
feature/*    ───────→                        (temporary)
fix/*        ─→                              (temporary)
hotfix/*     ──→                             (temporary)
```

---

## Related Documentation

**Core Documentation:**
- **[README.md](README.md)** - Documentation index
- **[TAGGING-GUIDE.md](TAGGING-GUIDE.md)** - Tag-based versioning and RC workflow
- **[QUICK-REFERENCE.md](QUICK-REFERENCE.md)** - Daily use commands

**Pipeline Configuration:**
- `../azure-pipelines.yml` - Pipeline triggers and quality gates

---

**Document Version:** 1.0.0  
**Last Updated:** 2025-12-04  
**Maintained By:** DevOps Team

