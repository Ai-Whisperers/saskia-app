# Agile Documentation Rules

## Overview
This directory contains comprehensive documentation rules for agile development artifacts including Epics, Business Features, Technical Features, and User Stories. Each rule is compact and focused, with detailed examples available in separate files.

## Quick Reference

| Document Type | Rule | Example | Use When |
|--------------|------|---------|----------|
| **Epic** | [Rule](epic-documentation-rule.mdc) | [Example](epic-example.md) | Large body of work spanning multiple sprints |
| **Business Feature** | [Rule](business-feature-documentation-rule.mdc) | [Example](business-feature-example.md) | Cohesive functionality delivering user value |
| **Technical Feature** | [Rule](technical-feature-documentation-rule.mdc) | [Example](technical-feature-example.md) | Technical capability supporting business features |
| **User Story** | [Rule](user-story-documentation-rule.mdc) | [Example](user-story-example.md) | Specific work completable within a sprint |
| **Story Splitting** | [Guidance](story-splitting-rule.mdc) | N/A | Story is too large and needs to be split |

## Documentation Structure

```
.cursor/rules/agile/
├── README.md                                   # This file - navigation and overview
├── epic-documentation-rule.mdc                 # Epic structure (compact)
├── epic-example.md                             # Full epic example
├── business-feature-documentation-rule.mdc     # Business feature structure (compact)
├── business-feature-example.md                 # Full business feature example
├── technical-feature-documentation-rule.mdc    # Technical feature structure (compact)
├── technical-feature-example.md                # Full technical feature example
├── user-story-documentation-rule.mdc           # User story structure (compact)
├── user-story-example.md                       # Full user story example
└── story-splitting-rule.mdc                    # Story splitting guidance
```

## Documentation Rules

### [Epic Documentation Rule](epic-documentation-rule.mdc) | [Example](epic-example.md)
**Compact rule** defining structure for Epic documentation. Epics are large bodies of work that can be broken down into smaller, more manageable pieces.

**Key Sections:**
- Epic Header (ID, Title, Status, Priority)
- Business Context (Problem, Value, Success Metrics)
- Scope and Boundaries (In/Out of Scope, Dependencies)
- High-Level Requirements (Functional/Non-Functional)
- Technical Overview (Architecture, Technology Stack)
- Risk Assessment (Technical/Business Risks)
- Timeline and Milestones
- Feature Breakdown

**Example:** EPP-192 - Standard Configuration Management NL Power for EBASE System Tables

---

### [Business Feature Documentation Rule](business-feature-documentation-rule.mdc) | [Example](business-feature-example.md)
**Compact rule** defining structure for Business Feature documentation. Business Features deliver value to end users or stakeholders.

**Key Sections:**
- Feature Header (ID, Title, Epic, Status, Priority)
- Business Context (Problem, User Need, Business Value)
- User Stories (Primary and Secondary)
- Functional/Non-Functional Requirements
- Scope and Boundaries
- Technical Considerations
- Acceptance Criteria

**Example:** BF-001 - Extract Configuration Data from EBASE Environments

---

### [Technical Feature Documentation Rule](technical-feature-documentation-rule.mdc) | [Example](technical-feature-example.md)
**Compact rule** defining structure for Technical Feature documentation. Technical Features focus on specific technical capabilities or components.

**Key Sections:**
- Feature Header (ID, Title, Business Feature, Epic, Technical Complexity)
- Technical Context (Problem, Business Impact, Technical Value)
- User Stories (Technical user stories)
- Technical Requirements (Functional, Non-Functional, Integration)
- Architecture and Design (Patterns, Technology Stack, Component Design)
- Implementation Details (Approach, Code Structure, Dependencies)
- Testing Strategy (Unit, Integration, Performance, Security)
- Deployment and Operations

**Example:** TF-001 - Standardized Domain Entity and Repository Framework

---

### [User Story Documentation Rule](user-story-documentation-rule.mdc) | [Example](user-story-example.md)
**Compact rule** defining structure for User Story documentation. User Stories are simple, concise descriptions of features from the user's perspective.

**Key Sections:**
- Story Header (ID, Title, Feature, Epic, Story Points)
- User Story (Main story, User Type, Business Value)
- Acceptance Criteria (Given-When-Then, Functional/Non-Functional)
- Technical Considerations (Approach, Dependencies, Integration)
- Design and UX (UI, UX, Accessibility, Responsive Design)
- Testing Requirements (Scenarios, Test Data, Performance, Security)
- Definition of Done

**Example:** US-001 - Extract Configuration Data from EBASE Environments

---

### [Story Splitting Rule](story-splitting-rule.mdc)
**Guidance document** for identifying when a user story is too large and should be split into smaller, more manageable stories.

**Key Sections:**
- When to Consider Story Splitting (Size, Complexity, Dependency, Risk Indicators)
- Story Splitting Patterns (User Journey, Technical Layer, Business Rules, etc.)
- Splitting Decision Framework
- Implementation Guidance (for POs, Developers, Scrum Masters)
- Red Flags: When NOT to Split
- Success Criteria and Warning Signs

## Usage Guidelines

### When to Use Each Document Type

#### Epic
- Use for large bodies of work spanning multiple sprints
- When work can be broken down into multiple features
- For significant business initiatives requiring coordination across teams

#### Business Feature
- Use for cohesive pieces of functionality that deliver user value
- When the focus is on business requirements and user needs
- For features that can be developed and delivered independently

#### Technical Feature
- Use for specific technical capabilities or components
- When the focus is on technical implementation and architecture
- For features that support business features but are technically complex

#### User Story
- Use for specific, implementable pieces of functionality
- When the work can be completed within a single sprint
- For detailed requirements that need to be implemented by developers

### Documentation Hierarchy
```
Epic
├── Business Feature 1
│   ├── Technical Feature 1.1
│   │   ├── User Story 1.1.1
│   │   ├── User Story 1.1.2
│   │   └── User Story 1.1.3
│   └── Technical Feature 1.2
│       ├── User Story 1.2.1
│       └── User Story 1.2.2
└── Business Feature 2
    ├── Technical Feature 2.1
    │   └── User Story 2.1.1
    └── Technical Feature 2.2
        └── User Story 2.2.1
```

### Best Practices

#### Content Guidelines
- Use clear, concise language appropriate for the audience
- Include specific, measurable acceptance criteria
- Focus on business value and user needs
- Avoid technical jargon in business-focused documents
- Include relevant diagrams and mockups where helpful

#### Format Guidelines
- Use markdown format for all documents
- Follow consistent heading structure
- Include proper metadata (ID, dates, status)
- Use checkboxes for acceptance criteria and definition of done
- Include links to related documents

#### Review Process
- Business stakeholders review business context and value
- Technical leads review technical feasibility and approach
- Product owners review scope and priorities
- Development teams review implementation details
- QA teams review testability and acceptance criteria

### Quality Checklist

#### For All Documents
- [ ] Clear, descriptive title
- [ ] Proper metadata and status
- [ ] Consistent formatting and structure
- [ ] Links to related documents
- [ ] Appropriate level of detail for the document type

#### For Epics
- [ ] Business problem clearly defined
- [ ] Success metrics are measurable
- [ ] Scope boundaries are clear
- [ ] Feature breakdown is complete
- [ ] Risk assessment is thorough

#### For Business Features
- [ ] User stories follow proper format
- [ ] Acceptance criteria are testable
- [ ] Business value is clearly stated
- [ ] Technical considerations are addressed
- [ ] Definition of done is complete

#### For Technical Features
- [ ] Technical approach is feasible
- [ ] Architecture impact is assessed
- [ ] Dependencies are identified
- [ ] Testing strategy is comprehensive
- [ ] Implementation details are clear

#### For User Stories
- [ ] Story follows "As a [user], I want [functionality] so that [benefit]" format
- [ ] Acceptance criteria use Given-When-Then format
- [ ] Story points are estimated
- [ ] Dependencies are identified
- [ ] Definition of done is complete

## Maintenance

### Version Control
- All documentation should be version controlled
- Use meaningful commit messages
- Tag major versions and releases
- Maintain change logs for significant updates

### Regular Reviews
- Review and update documentation regularly
- Ensure consistency across all documents
- Validate that templates and exemplars are current
- Gather feedback from teams and stakeholders

### Continuous Improvement
- Collect feedback on documentation quality
- Update templates based on lessons learned
- Share best practices across teams
- Maintain alignment with agile principles 