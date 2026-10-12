# CI/CD Scripts

This directory contains PowerShell scripts used by the Azure DevOps pipeline. You can run these scripts locally to verify behavior or debug issues.

## ✨ Enhanced Error Messages with Cursor AI Integration

All validation scripts now provide **actionable, AI-assisted error messages** when failures occur. Instead of just telling you what's wrong, they tell you:

- ✅ **How to fix it automatically** using Cursor AI prompts
- ✅ **Exact commands to run** for manual fixes
- ✅ **Links to relevant documentation** and rules
- ✅ **Context-aware guidance** based on your specific error

When a script fails in the pipeline, look for the highlighted sections with solutions!

## Prerequisites

Before running any scripts, ensure you have the following installed:

1.  **PowerShell 7+** (recommended) or Windows PowerShell 5.1
2.  **.NET 9 SDK**
3.  **.NET 7 SDK** (required for `dotnet-project-licenses` compatibility in some environments, though the script handles roll-forward)
4.  **Required Global Tools**:
    *   `dotnet-project-licenses`: `dotnet tool install --global dotnet-project-licenses`
    *   `dotnet-reportgenerator-globaltool`: `dotnet tool install --global dotnet-reportgenerator-globaltool`
    *   `CycloneDX`: `dotnet tool install --global CycloneDX`

## Running Scripts Locally

All scripts support a `-OutputPath` parameter to specify where results should be saved.

### 1. Scan Licenses

Scans all NuGet dependencies for license compliance.

```powershell
# Run scan and save to ./local-reports/licenses
.\scan-licenses.ps1 -OutputPath "./local-reports/licenses"
```

**Note**: This script uses `dotnet-project-licenses`. If you encounter "NativeCommandError", it's likely due to PowerShell handling stderr output. The script has been patched to handle this, but ensure you have the latest version of the tool.

### 2. Calculate Code Metrics

Calculates Maintainability Index and Cyclomatic Complexity.

```powershell
# Run metrics analysis and save to ./local-reports/metrics
.\calculate-code-metrics.ps1 -OutputPath "./local-reports/metrics" -Configuration Debug
```

**Output**: Generates `metrics-summary.json` and XML reports for each project.

### 3. Check Breaking Changes (API Compatibility)

Compares the current code against the latest release to detect breaking changes.

```powershell
# Run compatibility check
.\check-breaking-changes.ps1 -OutputPath "./local-reports/compat"
```

### 4. Validate Package Metadata

Ensures all NuGet packages have required metadata (Authors, Description, License, etc.).

```powershell
# Validate metadata
.\validate-package-metadata.ps1
```

### 5. Validate Documentation

Checks for missing XML comments and documentation quality.

```powershell
# Validate documentation
.\validate-documentation.ps1
```

### 6. Verify XML Files

Ensures that the build actually produced the expected `.xml` documentation files.

```powershell
# Verify XML files exist
.\verify-xml-files.ps1
```

### 7. Validate Release Notes

Checks that CHANGELOG.md contains an entry for the current release version.

```powershell
# Validate CHANGELOG for specific version
.\validate-release-notes.ps1 -Version "1.0.0-rc1"
```

**Enhanced Error Handling**:
- Shows exact Cursor AI prompt to generate CHANGELOG entries
- Provides git commands to fix and re-tag releases
- Links to CHANGELOG generation prompts

### 8. Validate Tag Context

Ensures release tags are created on appropriate stable branches (main or release/*).

```powershell
# Validate tag context (usually called by pipeline)
.\validate-tag-context.ps1
```

**Enhanced Error Handling**:
- Explains proper branching workflow
- Shows how to delete incorrect tags
- Provides guidance for RC vs Production releases
- Links to branching strategy documentation

## 🤖 Cursor AI Integration

When any validation script fails, it will show enhanced error messages like:

```
═══════════════════════════════════════════════════════════════
  AUTOMATED SOLUTION: Use Cursor AI
═══════════════════════════════════════════════════════════════

Tell the AI:
  "Generate CHANGELOG entry for version 1.0.0-rc1 from git history"

The AI will:
  ✓ Analyze commits since last release
  ✓ Categorize into Added/Changed/Fixed/Breaking
  ✓ Generate properly formatted entry
  ✓ Include release tag link
```

### Scripts with AI Integration

| Script | AI Assistance For |
|--------|------------------|
| **validate-release-notes.ps1** | Generating CHANGELOG entries from git history |
| **validate-documentation.ps1** | Generating missing XML documentation comments |
| **check-breaking-changes.ps1** | Documenting breaking changes with migration guides |
| **validate-package-metadata.ps1** | Generating complete NuGet package metadata |
| **validate-tag-context.ps1** | Understanding proper release workflow and branching |

### How to Use AI Assistance

1. **Read the error message** - It contains specific AI prompts
2. **Open Cursor AI** in your repository
3. **Copy the suggested prompt** or describe the issue
4. **AI generates solution** - Review and apply
5. **Re-run the script** or push to validate

### Related Cursor Prompts

- **CHANGELOG Generation**: `.cursor/prompts/changelog/quick-changelog-update.md`
- **CHANGELOG from Git**: `.cursor/prompts/changelog/generate-changelog-from-git.md`

### Related Rules

- **Documentation Standards**: `.cursor/rules/documentation/documentation-standards-rule.mdc`
- **Tag-Based Versioning**: `.cursor/rules/cicd/tag-based-versioning-rule.mdc`
- **Branch Lifecycle**: `.cursor/rules/git/branch-lifecycle-rule.mdc`
- **Project Setup**: `.cursor/rules/setup/project-setup-rule.mdc`

## Troubleshooting

-   **"Script is not digitally signed"**: Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` before running the script.
-   **"Command not found"**: Ensure the required global tools are installed and `%USERPROFILE%\.dotnet\tools` is in your PATH.
-   **"NativeCommandError"**: This usually happens when a tool writes to stderr (even for info messages). The scripts try to handle this, but if you see it, it typically doesn't affect the actual output if the exit code is 0.
-   **"Validation failed in pipeline"**: Check the enhanced error message for specific AI prompts or manual fixes. The error output now includes actionable guidance.
-   **"Need help with error"**: Ask Cursor AI: "Help me fix this CI/CD validation error: [paste error message]"

