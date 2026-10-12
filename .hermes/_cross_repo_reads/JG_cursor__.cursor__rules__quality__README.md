# Quality Standards Rules

## Overview

This directory contains the comprehensive quality standards rule framework for enforcing zero warnings/errors discipline and high-quality diagnostic messages across all development work.

## Philosophy

**Prevention over Remediation** - Catch issues before they enter version control.

**Zero Tolerance** - No warnings, no errors, no exceptions (unless documented).

**Helpful Diagnostics** - Every error is a teaching moment.

## Rules in This Framework

### Core Standards (Always Apply)

1. **`rule.quality.zero-warnings-errors.v1`**
   - **File**: `zero-warnings-zero-errors-rule.mdc`
   - **Purpose**: Enforces zero warnings and zero errors before every commit
   - **Key Features**:
     - Pre-commit validation workflow
     - Quality gate definitions (compile, lint, test, docs, format, security)
     - Implementation patterns (scripts, git hooks, IDE integration)
     - Tool-specific guidance (.NET, Python, JavaScript/TypeScript)
     - Validation script template

2. **`rule.quality.diagnostic-messages.v1`**
   - **File**: `diagnostic-messages-rule.mdc`
   - **Purpose**: Standards for high-quality diagnostic messages
   - **Key Features**:
     - Three-part message structure (WHAT + WHY + HOW)
     - Severity levels (ERROR, WARNING, INFO)
     - Message templates by type
     - Implementation patterns for scripts, exceptions, CLI tools
     - Diagnostic message catalog
     - Output formatting standards

### Agent Application Rules (On-Demand)

3. **`rule.quality.agent-application.v1`**
   - **File**: `agent-application-rule.mdc`
   - **Purpose**: Guides AI agents on when/how to apply quality standards
   - **Key Features**:
     - Explicit triggers and context clues
     - Common scenarios with agent actions
     - Integration with ticket, git, and CI/CD rules
     - Tool-specific guidance

4. **`rule.quality.diagnostic-messages.agent-application.v1`**
   - **File**: `diagnostic-messages-agent-application-rule.mdc`
   - **Purpose**: Guides AI agents on creating high-quality diagnostics
   - **Key Features**:
     - Message templates by context (PowerShell, C#, Python, Bash)
     - Common scenarios for creating/improving diagnostics
     - Quality checklist for agents
     - Testing approach for diagnostic messages

### Navigation Hub

5. **`rule.quality.index.v1`**
   - **File**: `quality-rules-index.mdc`
   - **Purpose**: Central navigation and overview of quality framework
   - **Key Features**:
     - Complete rule manifest with dependencies
     - Reading paths by role (developer, agent, reviewer)
     - Common scenarios and workflows
     - Integration points with other rule frameworks
     - Tool-specific quick reference

## Quick Start

### For Developers

**Before Every Commit**:
```bash
# Run validation (adapt to your project type)
./scripts/validate-pre-commit.{ps1|sh|py}

# Fix all issues (use auto-fix where available)
./scripts/validate-pre-commit.{ps1|sh|py} --auto-fix

# Confirm clean state
./scripts/validate-pre-commit.{ps1|sh|py}

# Only then commit
git commit
```

**Read**: `zero-warnings-zero-errors-rule.mdc` (15 min)

### For Script Writers

**When Creating Validation Scripts**:
1. Use structured diagnostic messages (WHAT + WHY + HOW + WHERE + HELP)
2. Provide auto-fix options where possible
3. Format output with colors and emojis
4. Include exact locations and specific solutions

**Read**: 
- `diagnostic-messages-rule.mdc` (20 min)
- `zero-warnings-zero-errors-rule.mdc` (15 min)

### For AI Agents

**When to Apply**:
- User preparing to commit code
- Validation scripts being created
- Error handling being implemented
- Quality issues being fixed

**Read**:
- `agent-application-rule.mdc`
- `diagnostic-messages-agent-application-rule.mdc`

## Rule Dependencies

```
quality-rules-index.mdc (Navigation Hub)
  |
  |--- zero-warnings-zero-errors-rule.mdc (Core Standard)
  |     └── Enforces quality discipline
  |
  |--- diagnostic-messages-rule.mdc (Core Standard)
  |     └── Defines message quality
  |
  |--- agent-application-rule.mdc (Agent Guidance)
  |     ├── requires: zero-warnings-zero-errors-rule
  |     └── requires: diagnostic-messages-rule
  |
  └--- diagnostic-messages-agent-application-rule.mdc (Agent Guidance)
        └── requires: diagnostic-messages-rule
```

## Key Concepts

### Quality Gates

1. **Code Quality**: Compile, lint, analyze, format
2. **Documentation**: Completeness, quality, updates
3. **Testing**: Pass rate, coverage, no skips
4. **Security**: No secrets, no vulnerabilities, OPSEC compliance
5. **Build**: Success, dependencies, metadata

### Diagnostic Message Structure

**ERROR (Blocker)**:
```text
❌ ERROR: [Clear problem statement]

Explanation: [Why this is an error and its impact]

Solution: [Specific steps to fix]

Location: [File:Line or specific context]

Help: [Link to docs/prompt or command to run]
```

**WARNING (Should Fix)**:
```text
⚠ WARNING: [Clear problem statement]

Impact: [What could go wrong if not fixed]

Solution: [Specific steps to fix]

Location: [File:Line or specific context]

Help: [Link to docs/prompt or command to run]
```

**INFO (FYI)**:
```text
ℹ INFO: [Helpful information]

Context: [Why this is being shown]

Action (optional): [What to do if this matters]
```

## Integration Points

- **Git Rules**: Pre-commit validation required
- **Ticket Rules**: Validation before completion
- **CI/CD Rules**: Local validation mirrors remote
- **Documentation Rules**: Doc validation uses structured diagnostics

## Success Metrics

- **Commit Quality**: 100% of commits pass validation
- **Build Stability**: Zero broken builds from quality issues
- **Developer Velocity**: Reduced time from error to fix
- **Learning**: Developers understand problems quickly
- **Autonomy**: Can fix issues without asking for help

## Anti-Patterns

### ❌ Quality Anti-Patterns
- Committing with "TODO: fix warnings later"
- Disabling warnings globally
- Commenting out failing tests
- Skipping validation "just this once"

### ❌ Diagnostic Anti-Patterns
- Vague error messages ("Error occurred")
- Missing solutions
- Technical jargon without explanation
- Blame/shame language
- Generic solutions ("Fix the code")

## Tool-Specific Quick Reference

### .NET
```powershell
dotnet build /warnaserror
dotnet format --verify-no-changes
dotnet test --no-build
```

### Python
```bash
flake8 .
pylint src/
mypy src/
black --check .
pytest
```

### JavaScript/TypeScript
```bash
npm run lint
npm run type-check
npm run format:check
npm test
```

## Related Rule Frameworks

- **Git Rules**: `.cursor/rules/git/`
- **Ticket Rules**: `.cursor/rules/ticket/`
- **CI/CD Rules**: `.cursor/rules/cicd/`
- **Documentation Rules**: `.cursor/rules/documentation/`

---

**TL;DR**: Zero warnings, zero errors before every commit. Every diagnostic should teach with WHAT + WHY + HOW. Quality is not negotiable.

