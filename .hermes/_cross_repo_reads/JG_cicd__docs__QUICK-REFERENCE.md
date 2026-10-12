# CI/CD Pipeline Quick Reference

**Repository:** eneve.domain  
**Pipeline:** 11-Stage Quality Gate Architecture with Advanced Features  
**Last Updated:** 2025-12-04  
**Status:** 68/60 Gold Standard Plus - Industry-Leading CI/CD

---

## Pipeline Stages

```
1. Build_and_Validate
   ├── 2. Security_Scan (parallel)
   ├── 3. Coverage_Analysis (parallel)
   └── 4. Advanced_Quality_Gates (parallel) **NEW**
           ↓
   5. Breaking_Change_Detection (main/release) **NEW**
   6. Release_Validation (release tags) **NEW**
           ↓
   7. Package_and_SBOM (main/develop/tags)
           ↓
   8. Enhanced_Coverage_Analysis **NEW**
           ↓
   9. Documentation_Report
           ↓
   10. Mutation_Testing (develop only, optional) **NEW**
           ↓
   11. Performance_Benchmarks (main/release, optional) **NEW**
```

---

## Quality Gates

| Gate | Threshold | Failure Action |
|------|-----------|----------------|
| **Build** | No errors | ❌ Fail |
| **Documentation** | All public APIs | ❌ Fail |
| **Security** | No Critical/High vulns | ❌ Fail |
| **Coverage** | 70%/75%/80% (branch) | ❌ Fail |
| **License Scan** | No GPL/AGPL/LGPL | ❌ Fail |
| **Package Metadata** | All required fields | ❌ Fail |
| **Breaking Changes** | No API breaks | ❌ Fail (main/release) |
| **Release Notes** | CHANGELOG updated | ❌ Fail (release tags) |
| **Enhanced Coverage** | 80% line, 70% branch | ❌ Fail |
| **SBOM** | Generation success | ❌ Fail |
| **Code Metrics** | Complexity < 15 | ⚠️ Warn |
| **Mutation Score** | > 75% | ⚠️ Warn |
| **Performance** | < 10% regression | ❌ Fail (main/release) |

---

## Coverage Thresholds by Branch

| Branch | Threshold | Why |
|--------|-----------|-----|
| `feature/*` | **70%** | Development flexibility |
| `develop` | **75%** | Integration quality |
| `main` | **80%** | Production standard |

---

## When Stages Run

### Feature Branches (`feature/*`)
- ✅ Build_and_Validate
- ✅ Security_Scan
- ✅ Coverage_Analysis (70% threshold)
- ⏭️ Package_and_SBOM (skipped)
- ✅ Documentation_Report

### Develop Branch
- ✅ Build_and_Validate
- ✅ Security_Scan
- ✅ Coverage_Analysis (75% threshold)
- ✅ Package_and_SBOM (creates packages + SBOM)
- ✅ Documentation_Report

### Main Branch
- ✅ Build_and_Validate
- ✅ Security_Scan
- ✅ Coverage_Analysis (80% threshold)
- ✅ Package_and_SBOM (creates packages + SBOM)
- ✅ Documentation_Report

### Tag Builds (Tag-Based Versioning)
- ✅ Build_and_Validate
- ✅ Security_Scan  
- ✅ Coverage_Analysis (based on tag type)
- ✅ Package_and_SBOM (with parsed tag version)
- ✅ Documentation_Report
- ✅ Publishing (automated to appropriate feed)

---

## Tag-Based Versioning Support

### Tag Format

```
[type]-[version][-suffix]
```

**Examples:**
- `release-1.0.0` - Production release
- `test-1.0.0-rc1` - Release candidate 1
- `coverage-1.0.0` - Coverage analysis only
- `security-20251204` - Security audit only

### Tag Types

| Tag Type | Purpose | Pipeline Behavior | Publishing |
|----------|---------|-------------------|------------|
| `release-*` | Production | All stages, 80% coverage | ✅ Production Feed |
| `test-*` | RC Testing | All stages, 70% coverage | ✅ Test Feed |
| `coverage-*` | Analysis | All stages, no publishing | N/A |
| `security-*` | Security Audit | Build + Security only | N/A |

### Tag Workflows

**Coverage Analysis Tag:**
```bash
git tag coverage-1.0.0
git push origin coverage-1.0.0
# ✅ Full pipeline runs
# ✅ Package created as artifact
# ❌ NOT published (by design)
```

**Release Candidate Tag:**
```bash
git tag test-1.0.0-rc1
git push origin test-1.0.0-rc1
# ✅ Full pipeline runs
# ✅ Package versioned as 1.0.0-rc1
# ✅ Automatically published to test feed (Eneve-TestPackages-Domain)
# ✅ Ready for integration testing
```

**Production Release Tag:**
```bash
git tag release-1.0.0
git push origin release-1.0.0
# ✅ Full pipeline runs (80% coverage required)
# ✅ Package versioned as 1.0.0
# ✅ Automatically published to production feed (Eneve-Packages-Domain)
# ✅ Available for consumption
```

**Security Audit Tag:**
```bash
git tag security-20251204
git push origin security-20251204
# ✅ Quick build
# ✅ Full security scan with color output
# ⏭️ Skips coverage, packaging, docs
# ⏱️ Fast: typically 2-3 minutes
```

**Note:** n8n webhook integration planned for automated vulnerability notifications

For complete tagging guide, see [TAGGING-GUIDE.md](TAGGING-GUIDE.md).

---

## Published Artifacts

| Artifact | Branches/Tags | Contents |
|----------|---------------|----------|
| `coverage-report` | All | HTML coverage report |
| `enhanced-coverage` | All | Deep coverage analysis |
| `documentation-report` | All | Doc coverage report |
| `license-report` | All | Dependency licenses |
| `code-metrics` | All | Complexity metrics |
| `api-compat` | main, release | Breaking change analysis |
| `mutation-report` | develop | Test effectiveness |
| `benchmarks` | main, release | Performance data |
| `packages` | main, develop, tags | NuGet packages |
| `sbom` | main, develop, tags | CycloneDX SBOM (JSON) |

---

## Common Scenarios

### ❌ Build Fails on Security
**Cause:** Critical or High severity vulnerability detected

**Fix:**
```powershell
# Check vulnerabilities locally
dotnet list package --vulnerable --include-transitive

# Update vulnerable packages
dotnet add package [PackageName] --version [SafeVersion]
```

### ❌ Build Fails on Coverage
**Cause:** Coverage below branch threshold

**Fix:**
```powershell
# Check current coverage
dotnet test --collect:"XPlat Code Coverage"

# Add missing tests
# Commit and push
```

**Temporary Override:** Lower threshold in pipeline YAML (not recommended)

### ❌ Build Fails on Documentation
**Cause:** Missing XML documentation on public APIs

**Fix:**
```csharp
/// <summary>
/// [Add description]
/// </summary>
public void MyMethod() { }
```

### ❌ License Scan Failure
**Cause:** Prohibited copyleft license detected (GPL/AGPL/LGPL)

**Fix:**
```powershell
# Check report artifact for offending package
# Find alternative with MIT/Apache-2.0 license
# Update Directory.Packages.props
```

### ❌ High Complexity Warning
**Cause:** Method complexity exceeds 15

**Fix:** Refactor complex methods into smaller units

### ❌ Missing Package Metadata
**Cause:** Required NuGet metadata fields missing

**Fix:** Add to Directory.Build.props or .csproj:
```xml
<PropertyGroup>
  <Authors>Your Name</Authors>
  <Description>Detailed description</Description>
  <PackageLicenseExpression>MIT</PackageLicenseExpression>
</PropertyGroup>
```

### ❌ Breaking Changes Detected
**Cause:** API incompatibility with previous version

**Fix:** 
1. If intentional: Increment major version
2. Update CHANGELOG.md with breaking changes
3. If unintentional: Revert changes

### ❌ Missing Release Notes
**Cause:** CHANGELOG.md not updated for release

**Fix:** Add entry to CHANGELOG.md:
```markdown
## [1.0.0] - 2025-12-04
### Added
- New feature
### Fixed
- Bug fix
```

### ❌ Tag Parsing Error
**Cause:** Invalid tag format

**Valid Formats:**
- `release-1.0.0`
- `test-1.0.0-rc1`
- `coverage-1.0.0`

**Invalid Formats:**
- `v1.0.0` (missing type)
- `release-1.0` (incomplete version)
- `test_1.0.0` (underscore not allowed)
- `security-invalid` (security tags need YYYYMMDD)

**Fix:** Delete tag and create with correct format
```bash
git tag -d incorrect-tag-name
git push origin --delete incorrect-tag-name
git tag -a correct-tag-name -m "Description"
git push origin correct-tag-name
```

---

## Local Testing Commands

### Core Pipeline Tests
```powershell
# Build with documentation warnings as errors
dotnet build --configuration Release /p:TreatWarningsAsErrors=true

# Run all tests with coverage
dotnet test --collect:"XPlat Code Coverage" --results-directory ./coverage

# Check for vulnerabilities
dotnet list package --vulnerable --include-transitive

# Validate documentation
.\cicd\scripts\validate-documentation.ps1 -Configuration Release
```

### Advanced Quality Checks
```powershell
# License scanning
.\cicd\scripts\scan-licenses.ps1

# Code metrics
.\cicd\scripts\calculate-code-metrics.ps1

# Package metadata validation
.\cicd\scripts\validate-package-metadata.ps1

# Breaking change detection
.\cicd\scripts\check-breaking-changes.ps1

# Release notes validation
$env:BUILD_SOURCEBRANCH = "refs/tags/release-1.0.0"
.\cicd\scripts\validate-release-notes.ps1

# Enhanced coverage analysis
.\cicd\scripts\enhanced-coverage-analysis.ps1

# Mutation testing (20-40 min)
.\cicd\scripts\run-mutation-tests.ps1

# Performance benchmarks (10-20 min)
.\cicd\scripts\run-benchmarks.ps1
```

---

## Tag Management Commands

### List All Tags
```bash
git tag                      # All tags
git tag -l "release-*"       # Production releases
git tag -l "test-*"          # Release candidates
git tag -l "security-*"      # Security audits
```

### Create Tags
```bash
# Annotated tag (RECOMMENDED)
git tag -a test-1.0.0-rc1 -m "Release Candidate 1"
git push origin test-1.0.0-rc1
```

### Delete Tags
```bash
# Local
git tag -d test-1.0.0-rc1

# Remote
git push origin --delete test-1.0.0-rc1
```

---

## Pipeline URLs

**Builds:** https://dev.azure.com/Energy21/NuGet%20Packages/_build  
**Artifacts:** Check completed build → Artifacts tab  
**Repository:** https://dev.azure.com/Energy21/NuGet%20Packages/_git/Eneve.Domain

---

## Getting Help

**Core Documentation:**
- **[PIPELINE-STATUS.md](PIPELINE-STATUS.md)** - Complete capabilities (68/60)
- **[TAGGING-GUIDE.md](TAGGING-GUIDE.md)** - Tag-based versioning guide
- **[BRANCHING-GUIDE.md](BRANCHING-GUIDE.md)** - Git workflow guide
- **[README.md](README.md)** - Documentation navigation

**Common Issues:**
1. **Coverage too low** → Add unit tests
2. **Vulnerabilities found** → Update packages
3. **Documentation missing** → Add XML comments
4. **License prohibited** → Find alternative package
5. **High complexity** → Refactor methods
6. **Missing metadata** → Update Directory.Build.props
7. **Breaking changes** → Increment major version
8. **Missing CHANGELOG** → Update release notes
9. **Tag parsing fails** → Verify format: `[type]-[X.Y.Z][-suffix]`

---

## Tips

✅ **DO:**
- Run tests locally before pushing
- Check coverage on feature branches
- Update vulnerable packages immediately
- Document all public APIs
- Use annotated tags (not lightweight tags)
- Follow tag naming convention exactly

❌ **DON'T:**
- Lower coverage thresholds without team discussion
- Ignore security warnings
- Skip documentation
- Push without local testing
- Reuse tag names (tags are immutable)
- Use incorrect tag formats

---

## Advanced Features

### 8 New Quality Gates

1. **License Scanning** (2 min) - Prevents legal issues
2. **Code Metrics** (3 min) - Tracks complexity
3. **Package Metadata** (1 min) - Validates NuGet quality
4. **Breaking Changes** (5 min) - Prevents API breaks
5. **Release Notes** (1 min) - Validates CHANGELOG
6. **Enhanced Coverage** (4 min) - Deep analysis
7. **Mutation Testing** (30 min) - Test effectiveness (optional)
8. **Performance Benchmarks** (15 min) - Regression detection (optional)

### Total Build Times

- **Feature Branch:** ~11 minutes (core gates)
- **Develop Branch:** ~41 minutes (+ mutation testing)
- **Main Branch:** ~31 minutes (+ breaking changes + benchmarks)
- **Release Tags:** ~32 minutes (+ release validation)

---

**Version:** 4.0.0  
**Status:** 68/60 Gold Standard Plus - Fully Operational  
**Advanced Features:** All 8 features operational

