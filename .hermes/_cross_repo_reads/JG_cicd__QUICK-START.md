# CI/CD Pipeline Quick Start Guide

⏱️ **Setup Time:** 5-10 minutes

This guide will help you quickly set up and verify the CI/CD documentation pipeline.

---

## Prerequisites

- .NET 9.x SDK installed
- PowerShell (for Windows) or PowerShell Core (cross-platform)
- Azure DevOps account (for pipeline setup)

---

## Local Testing (Do This First!)

Before pushing to Azure DevOps, verify everything works locally:

### 1. Build the Solution

```powershell
dotnet build Eneve.Domain.sln --configuration Release
```

**Expected Result:** ✅ Build succeeds with no errors

### 2. Verify XML Files Exist

```powershell
.\cicd\scripts\verify-xml-files.ps1 -Configuration Release
```

**Expected Result:** ✅ All XML documentation files found

### 3. Validate Documentation Completeness

```powershell
.\cicd\scripts\validate-documentation.ps1 -Configuration Release
```

**Expected Result:** ✅ No documentation warnings (CS1591)

### 4. Generate Coverage Report

```powershell
.\cicd\scripts\generate-doc-report.ps1 -Configuration Release -OutputPath "./docs-report"
```

**Expected Result:** ✅ Report generated at `./docs-report/documentation-coverage-report.md`

### 5. Run All Tests

```powershell
dotnet test Eneve.Domain.sln --configuration Release --logger "console;verbosity=detailed"
```

**Expected Result:** ✅ All tests pass

---

## Common Issues & Fixes

### ❌ "XML file NOT FOUND"

**Problem:** Project not configured to generate XML documentation

**Fix:**
1. Open the `.csproj` file
2. Add inside `<PropertyGroup>`:
   ```xml
   <GenerateDocumentationFile>true</GenerateDocumentationFile>
   ```
3. Rebuild the project

### ❌ "Documentation warnings (CS1591)"

**Problem:** Public members are missing XML documentation comments

**Fix:**
1. Add XML comments to undocumented members:
   ```csharp
   /// <summary>
   /// Describes what this class/method/property does
   /// </summary>
   public class MyClass { }
   ```
2. See `docs/DOCUMENTATION-STANDARDS.md` for complete guidelines

### ❌ "PowerShell scripts won't run"

**Problem:** PowerShell execution policy blocks scripts

**Fix:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## Azure DevOps Setup

Once local testing passes, set up the pipeline in Azure DevOps:

### Step 1: Create Pipeline

1. Navigate to your Azure DevOps project
2. Go to **Pipelines** → **Create Pipeline**
3. Select your repository
4. Choose **Existing Azure Pipelines YAML file**
5. Select `/cicd/azure-pipelines.yml`
6. Click **Run**

### Step 2: Verify Pipeline Run

The pipeline should:
- ✅ Build all projects
- ✅ Verify XML files exist
- ✅ Run all unit tests
- ✅ Validate documentation completeness
- ✅ Publish test results and code coverage
- ✅ Generate documentation report
- ✅ Pack NuGet packages (on main/develop)

### Step 3: Review Artifacts

After a successful run, check:
- **Tests** tab: Unit test results
- **Code Coverage** tab: Coverage statistics
- **Artifacts**: NuGet packages and documentation report

---

## Branch Protection Setup (Optional but Recommended)

Require documentation validation before merging to `main`:

1. Go to **Repos** → **Branches**
2. Click on `main` branch → **Branch policies**
3. Enable **"Require a minimum number of reviewers"**
   - Minimum: 1 reviewer
4. Add **Build Validation**:
   - Build pipeline: Select your new pipeline
   - Trigger: Automatic
   - Policy requirement: Required
5. Click **Save**

**Result:** All PRs to `main` must pass documentation validation ✅

---

## Testing Changes Locally Before PR

Before creating a pull request:

```powershell
# Full local validation
dotnet build Eneve.Domain.sln --configuration Release
.\cicd\scripts\verify-xml-files.ps1
.\cicd\scripts\validate-documentation.ps1
dotnet test Eneve.Domain.sln --configuration Release
```

If all commands succeed, you're ready to commit and push! 🚀

---

## Common Scenarios

### Scenario 1: Adding a New Project

1. Add `<GenerateDocumentationFile>true</GenerateDocumentationFile>` to the `.csproj`
2. Document all public members
3. Run local validation scripts
4. Commit and push

### Scenario 2: Fixing Documentation Warnings

1. Run: `.\cicd\scripts\validate-documentation.ps1`
2. Note which members need documentation
3. Add XML comments to those members
4. Re-run validation script
5. Commit once validation passes

### Scenario 3: Reviewing Documentation Coverage

1. Run: `.\cicd\scripts\generate-doc-report.ps1`
2. Open: `./docs-report/documentation-coverage-report.md`
3. Review projects needing attention
4. Add missing documentation
5. Re-run report to verify improvements

---

## Next Steps

- 📖 Read the complete documentation: [README.md](README.md)
- 📋 Review standards: [docs/DOCUMENTATION-STANDARDS.md](../docs/DOCUMENTATION-STANDARDS.md)
- 🔧 Configure branch policies (see above)
- 🎯 Set up notifications for failed builds

---

## Need Help?

- **Pipeline failing?** Check the [Troubleshooting section](README.md#troubleshooting) in README.md
- **Documentation questions?** See `docs/DOCUMENTATION-STANDARDS.md`
- **Script issues?** Review script comments in `cicd/scripts/`

---

**Quick Start Version:** 1.0.0  
**Last Updated:** 2025-11-30

