# Rule Authoring Framework

**Version**: 1.1.0  
**Status**: Production Ready  
**Last Updated**: 2025-11-04  
**Latest**: Added extraction-from-practice as 8th core rule (PRIMARY recommended approach)

## Quick Links

- **Start Here**: [Rule Authoring Overview](rule-authoring-overview.mdc) - Navigation hub
- **Foundation**: [File Structure](rule-file-structure.mdc) - Read this first
- **Validation**: [Validation Report](VALIDATION-REPORT.md) - Framework self-validation

## What is This?

A comprehensive, self-consistent framework for authoring rules that:
- Define workflows and file generation
- Enforce validation and constraints
- Support automation and tooling
- Enable traceability and versioning

## The Eight Core Rules

### 0. [Extraction from Practice](rule-extraction-from-practice.mdc) - **PRIMARY APPROACH**
**ID**: `rule.authoring.extraction-from-practice.v1`  
**File**: `rule-extraction-from-practice.mdc`

**What it defines**:
- How to extract rules from real conversations and work (the recommended approach)
- Refinement cycle (2-3 iterations to stability)
- The dogfooding principle (AI adjusts its own rules)

**When to read**: **FIRST** - Before creating any rules.

**Key takeaway**: Do not design rules from scratch. Do real work 2-3 times, notice patterns, extract what actually worked, refine.

### 1. [File Structure](file-structure-rule.mdc)
**ID**: `rule.authoring.file-structure.v1`

Defines the canonical structure for all rules: 10-field front-matter, 10 ordered sections, and must-pass checklists.

**Read first** - This is the foundation.

### 2. [Naming Conventions](naming-conventions-rule.mdc)
**ID**: `rule.authoring.naming-conventions.v1`

Defines ID patterns (`rule.domain.action.v1`), file names, and directory structure.

**Read when** - Creating a new rule.

### 3. [Contracts and Scope](contracts-and-scope-rule.mdc)
**ID**: `rule.authoring.contracts-and-scope.v1`

Defines how to write explicit input/output contracts and scope boundaries.

**Read when** - Defining what a rule needs and produces.

### 4. [Cross-References](cross-references-rule.mdc)
**ID**: `rule.authoring.cross-references.v1`

Defines stable ID-based reference system for dependencies.

**Read when** - A rule depends on other rules or templates.

### 5. [Templars and Exemplars](templars-and-exemplars-rule.mdc)
**ID**: `rule.authoring.templars-and-exemplars.v1`

Defines separation between templates (structure) and examples (patterns).

**Read when** - Creating templates or examples for rules.

### 6. [Provenance and Versioning](provenance-and-versioning-rule.mdc)
**ID**: `rule.authoring.provenance-and-versioning.v1`

Defines semantic versioning and traceability for rules and outputs.

**Read when** - Creating or updating rules.

### 7. [Validation and Checklists](validation-and-checklists-rule.mdc)
**ID**: `rule.authoring.validation-and-checklists.v1`

Defines checklist patterns and validation approaches.

**Read when** - Writing the checklist for a rule.

## Quick Start

### Creating Your First Rule (Recommended: Extraction)

1. **Read** [Rule Authoring Overview](rule-authoring-overview.mdc) (15 min)
2. **Read** [Extraction from Practice](rule-extraction-from-practice.mdc) (20 min)
3. **Do real work** - Solve 2-3 similar problems, notice patterns
4. **Extract rule** - Write down what you actually did
5. **Formalize** - Use framework structure (reference File Structure as needed)
6. **Refine** - Improve after next 2-3 uses

**Time**: Spread over 2-3 real tasks, ~30-60 min total rule writing - robust rule

### Creating Your First Rule (Alternative: Design)

1. **Read** [Rule Authoring Overview](rule-authoring-overview.mdc) (15 min)
2. **Read** [File Structure](file-structure-rule.mdc) (20 min)
3. **Follow** Design-from-scratch guide in overview
4. **Test** against real scenarios (may need significant revision)

### Reviewing a Rule

Use the validation checklist from [Validation and Checklists](validation-and-checklists-rule.mdc):

- [ ] Front-matter complete (10 fields)
- [ ] ID follows naming convention
- [ ] All sections present in order
- [ ] Checklist is last section
- [ ] Contracts are explicit
- [ ] Cross-references use IDs
- [ ] Version matches ID

## Framework Validation

The framework has been validated against its own standards. See [VALIDATION-REPORT.md](VALIDATION-REPORT.md) for details.

**Result**: All 8 core rules pass self-validation

**Note**: The extraction-from-practice rule was itself extracted from real experience of creating the first 7 rules, demonstrating the approach it documents (dogfooding).

## Directory Structure

```
.cursor/rules/rule-authoring/
|---- README.md                                   # This file
|---- VALIDATION-REPORT.md                        # Self-validation report
|---- rule-authoring-overview.mdc                 # Navigation hub - START HERE
|---- rule-extraction-from-practice.mdc           # Core rule 0 - PRIMARY APPROACH
|---- file-structure-rule.mdc                     # Core rule 1
|---- naming-conventions-rule.mdc                 # Core rule 2
|---- contracts-and-scope-rule.mdc                # Core rule 3
|---- cross-references-rule.mdc                   # Core rule 4
|---- templars-and-exemplars-rule.mdc             # Core rule 5
|---- provenance-and-versioning-rule.mdc          # Core rule 6
`---- validation-and-checklists-rule.mdc          # Core rule 7
```

## For Different Roles

### New Rule Author
**Recommended** (Extraction):
1. Read [Overview](rule-authoring-overview.mdc)
2. Read [Extraction from Practice](rule-extraction-from-practice.mdc)
3. Do 2-3 similar tasks, extract rule
4. Refine over next uses

**Time**: Spread over 2-3 real tasks (~1-2 weeks), 30-60 min total

**Alternative** (Design):
1. Read [Overview](rule-authoring-overview.mdc)
2. Read [File Structure](file-structure-rule.mdc)
3. Follow design-from-scratch quick start

**Time**: 30-60 minutes up front, likely needs revision

### Experienced Rule Author
1. Use [Overview](rule-authoring-overview.mdc) as navigation
2. Jump to specific rules as needed
3. Check examples in existing rules

**Time**: 5-15 minutes per lookup

### Rule Reviewer
1. Use validation checklist from [Validation and Checklists](validation-and-checklists-rule.mdc)
2. Check against each core rule
3. Verify compliance

**Time**: 10-20 minutes per rule

### Framework Maintainer
1. Read all seven core rules
2. Understand dependencies
3. Follow versioning rules for updates
4. Update [Overview](rule-authoring-overview.mdc) if structure changes

**Time**: 2-4 hours for full understanding

## Key Concepts

### IDs Over Paths
Rules reference each other by **stable IDs**, not file paths:
```yaml
requires:
  - rule.ticket.plan.update.v1
```

### Contracts Are Explicit
Every rule declares what it reads and writes:
```yaml
globs: **/plan.md          # Can read
governs: **/plan.md        # Can write
```

### Checklists Are Last
Must-pass validation always in final section:
```markdown
## FINAL MUST-PASS CHECKLIST

- [ ] OPSEC clean
- [ ] Structure valid
- [ ] Contracts met
```

### Separation of Concerns
- **Rules**: Define behavior
- **Templars**: Define structure (placeholders)
- **Exemplars**: Show patterns (real content, never copied)

## Architecture

```
* Extraction from Practice (PRIMARY APPROACH)
    |
    |----> File Structure (foundation for formalization)
    |   |----> Naming Conventions
    |   |----> Contracts and Scope
    |   |   `----> Validation and Checklists
    |   |----> Cross-References
    |   |   |----> Templars and Exemplars
    |   |   `----> Provenance and Versioning
    |   `----> Overview (hub, depends on all)
    |
    `----> Workflow: Do Work -> Extract -> Formalize -> Refine
```

## Framework Principles

1. **Explicit Over Implicit** - All dependencies, contracts, and side effects are declared
2. **Stable References** - IDs never change, files can move freely
3. **Version Safety** - Semantic versioning with major version in ID
4. **Self-Consistency** - Framework applies to itself
5. **Automation-Ready** - Rules are machine-readable and validatable
6. **Human-Friendly** - Clear structure and navigation

## Benefits

### For Rule Authors
- Clear template to follow
- No guessing about structure
- Confidence in correctness

### For Rule Users
- Predictable rule behavior
- Clear validation criteria
- Trustworthy outputs

### For Organizations
- Consistent documentation
- Automation opportunities
- Knowledge preservation
- Onboarding efficiency

## Next Steps

### Just Created the Framework?
You are done! The framework is complete and validated.

### Ready to Use It?
1. **Read** [Overview](rule-authoring-overview.mdc)
2. **Create** your first rule in your domain (ticket, migration, etc.)
3. **Validate** using the checklist
4. **Iterate** as you learn

### Want to Extend It?
1. **Create templars** for rule authoring (optional)
2. **Create exemplars** showing good/bad examples (optional)
3. **Build tools** for automated validation (optional)
4. **Generate visualizations** of dependency graphs (optional)

## Support

### Questions?
- Check [Overview](rule-authoring-overview.mdc) for common scenarios
- Read the specific core rule for detailed guidance
- Review existing rules in other domains for examples

### Issues?
- Verify against [VALIDATION-REPORT.md](VALIDATION-REPORT.md)
- Check that you followed the structure from [File Structure](file-structure-rule.mdc)
- Review the checklist from [Validation and Checklists](validation-and-checklists-rule.mdc)

### Improvements?
- Follow versioning rules from [Provenance and Versioning](provenance-and-versioning-rule.mdc)
- Update the affected core rule(s)
- Bump version appropriately (MAJOR for breaking changes)
- Update this README if structure changes

## Version History

### v1.1.0 (2025-11-04)
- **Added**: 8th core rule: Extraction from Practice
- **Change**: Extraction approach is now PRIMARY recommended method
- **Reason**: Based on real experience creating first 7 rules + user feedback
- All rules updated to reference extraction approach

### v1.0.0 (2025-11-04)
- Initial release
- Seven core rules defined
- Framework validated against itself
- Production ready

## License and Usage

This framework is designed for internal organizational use. Adapt as needed for your context while maintaining the core principles of explicitness, stability, and self-consistency.

---

**Remember**: Start with [Rule Authoring Overview](rule-authoring-overview.mdc) for the best introduction to this framework.

