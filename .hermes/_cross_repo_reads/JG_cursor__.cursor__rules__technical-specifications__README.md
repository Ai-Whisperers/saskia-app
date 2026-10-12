---
id: rule.technical-specifications.overview.v1
kind: rule
version: 1.0.0
description: Complete rule system for C++ to C# migration technical specifications with architecture patterns and documentation standards
globs: **/docs/technical/**/*.md, **/.cursor/rules/technical-specifications/*.mdc
governs: ""
implements: technical-specifications.overview
requires:
  - rule.technical-specifications.architecture.v1
  - rule.technical-specifications.hybrid-architecture.v1
  - rule.technical-specifications.domain-object.v1
  - rule.technical-specifications.enumeration.v1
  - rule.technical-specifications.business-rules.v1
  - rule.technical-specifications.entity-relationship.v1
  - rule.technical-specifications.integration-points.v1
  - rule.technical-specifications.anti-duplication.v1
model_hints: { temp: 0.2, top_p: 0.9 }
provenance: { owner: team-migration, last_review: 2025-11-04 }
---

# Technical Specifications Documentation Rules

## Purpose & Scope

This directory contains comprehensive rules for creating technical specifications during C++ to C# migration projects. These rules ensure consistent, accurate, and implementation-ready documentation that supports successful system migration.

**Applies to**: All technical specification documentation created during C++ to C# migration projects within `docs/technical/` folder structure. Provides navigation and overview of complete rule system including architecture patterns, domain documentation, and quality standards.

**Does not apply to**: Implementation documentation (docs/implementation/), RFCs (docs/rfcs/), code files, or non-migration documentation.

## Inputs (Contract)

- C++ to C# migration project requiring structured technical documentation
- Understanding of migration phases (Phase 1 Data Collection, Phase 2 Specification Creation)
- Decision on documentation architecture approach (3-folder, hybrid layered, or custom)
- Knowledge of domains requiring documentation

## Outputs (Contract)

Complete rule system providing:
- Documentation architecture patterns (3-folder, hybrid layered structure)
- Specification type rules (domain objects, business rules, enumerations, etc.)
- Quality standards and anti-duplication enforcement
- Cross-reference patterns and navigation guidance
- Migration-ready technical specifications following all rule standards

## Purpose (Original)

This directory contains comprehensive rules for creating technical specifications during C++ to C# migration projects. These rules ensure consistent, accurate, and implementation-ready documentation that supports successful system migration.

## Rule Categories

### **Documentation Architecture**
1. **[Documentation Architecture Rule](documentation-architecture-rule.mdc)** - Three-folder structure and separation of concerns
1. **[Hybrid Documentation Architecture Rule](hybrid-documentation-architecture-rule.mdc)** - Layered architecture with database and domain separation

### **Core Document Types**
2. **[Domain Overview Rule](domain-overview-rule.mdc)** - Central navigation hubs and system architecture documentation
3. **[Entity Relationship Rule](entity-relationship-rule.mdc)** - Database schema and entity relationship documentation
4. **[Domain Object Rule](domain-object-rule.mdc)** - Individual domain entity specifications with detailed field meanings
5. **[Enumeration Rule](enumeration-rule.mdc)** - Enumeration definitions with values and business meanings
6. **[Business Rules Rule](business-rules-rule.mdc)** - Business logic, validation rules, and decision criteria
7. **[Integration Points Rule](integration-points-rule.mdc)** - External system interfaces, data exchange patterns, script functions, and automation APIs

### **Practical Examples**
8. **[Exemplar Files](exemplars/README.md)** - Real specification examples demonstrating each rule in practice

## Important: Domain Objects vs Entities in C# DDD

In C# Domain-Driven Design, **Domain Objects** is a broader category that includes:
- **Entities** - objects with identity that can change over time
- **Value Objects** - immutable objects defined by their attributes
- **Aggregates** - clusters of domain objects treated as a unit
- **Domain Services** - operations that don't naturally belong to entities

The Domain Object Rule specifically covers **Domain Entities** - objects with unique identity and lifecycle management.

## Documentation Strategy

### **Hybrid Architecture Approach**
This rule system uses a **hybrid documentation strategy**:

#### **Three-Folder Separation**:
- **docs/technical/**: Current system specifications ("WHAT exists")
- **docs/implementation/**: C# target design ("HOW to build")  
- **docs/rfcs/**: Future proposals ("WHAT could be")

#### **Layered Documentation within Technical**:
- **Database Layer**: 3-file pattern for database documentation
- **Domain Layer**: DDD pattern for business logic documentation
- **Domain-by-Domain**: Complete layered structure per domain

See **[Hybrid Documentation Architecture Rule](hybrid-documentation-architecture-rule.mdc)** for complete guidance.

### **Modular Approach**
- **Separation of Concerns**: Each document type serves a specific purpose
- **Cross-Referencing**: Extensive linking between related specifications
- **Maintainable Structure**: Updates isolated to relevant documents
- **Parallel Development**: Different teams can work on different specification types

### **"WHAT" vs "HOW" Principle**
- **Focus on WHAT**: Business requirements, current behavior, data structures
- **Avoid HOW**: Implementation details, C++ code specifics, technical internals
- **Exception**: HOW details only when essential for business logic understanding

### **Reference-Driven Architecture**
- **Central Navigation**: Domain overview files serve as navigation hubs
- **Detailed Specifications**: Individual files provide comprehensive detail
- **Cross-Linking**: Related concepts linked across files
- **Reading Paths**: Different audiences can follow appropriate navigation paths

## Document Relationships

### **Hierarchy Structure**
```
Domain Overview (Navigation Hub)
├── Entity Relationships (Data Structure)
├── Domain Objects (Field Details)
│   ├── Enumerations (Value Definitions)
│   └── Business Rules (Logic Specifications)
└── Integration Points (External Dependencies)
```

### **Cross-Reference Patterns**
- **Domain Overview** links to all other document types
- **Entity Relationships** links to domain objects and business rules
- **Domain Objects** reference enumerations and business rules
- **Business Rules** reference domain objects and enumerations
- **Integration Points** reference domain objects and business rules

## Quality Standards

### **Accuracy Requirements**
- All content traceable to Phase 1 data collection findings
- No fabricated or assumed information
- Clear source references for all technical claims
- Distinction between current state and migration requirements

### **Completeness Standards**
- All current system functionality captured
- All business rules and logic documented
- All data structures and relationships specified
- All external dependencies identified

### **Clarity Standards**
- Business language for business concepts
- Technical language for implementation details
- Consistent terminology across all documents
- Clear navigation and cross-referencing

## Implementation Guidance

### **For Domain Overview Files**
- Serve as central navigation and architecture documentation
- Provide business context and high-level system understanding
- Link extensively to detailed specification files
- Support multiple stakeholder reading paths

### **For Entity Relationship Files**
- Document complete data model with accurate field names
- Include comprehensive Mermaid ERDs with business-meaningful labels
- Specify all constraints, keys, and relationships
- Focus on data structure, not implementation details

### **For Domain Object Files**
- Document every field with business meaning and technical details
- One file per major domain entity
- Include complete field specifications with constraints and usage
- Provide business context for all fields and relationships

### **For Enumeration Files**
- Include "enum" in filename for clarity
- Document all enumeration values with exact numeric codes
- Provide business descriptions and usage patterns
- Include migration requirements and compatibility considerations

### **For Business Rules Files**
- Document all business logic extracted from source system
- Focus on WHAT rules do, not HOW they're implemented
- Include validation rules, algorithms, and decision logic
- Provide clear step-by-step logic for complex processes

### **For Integration Points Files**
- Document all external system interfaces and dependencies
- Include actual data formats and interface specifications
- Specify migration compatibility requirements
- Document error handling and performance characteristics

## Migration Context

### **C++ System Characteristics**
- **Position-Based Access**: Document field position patterns from C++
- **Memory Management**: Note manual memory management implications
- **Caching Strategies**: Sophisticated caching patterns to preserve
- **Integration Patterns**: Legacy integration approaches requiring preservation

### **C# Implementation Requirements**
- **Business Logic Preservation**: Exact replication of business behavior
- **Performance Maintenance**: Meet or exceed current system performance
- **Interface Compatibility**: Maintain external system interface contracts
- **Data Structure Translation**: Accurate mapping from C++ to C# domain objects

### **Migration Quality Gates**
- **Technical Accuracy**: All specifications reflect actual system behavior
- **Implementation Readiness**: Development teams can implement from specifications
- **Business Validation**: Business stakeholders confirm requirement accuracy
- **Integration Preservation**: External system compatibility maintained

## Usage Guidelines

### **For Migration Phase 2 (Specification Creation)**
1. **Start with Domain Overview**: Create central navigation document first
2. **Build Entity Relationships**: Document complete data model
3. **Detail Domain Objects**: Specify individual entities with field details
4. **Define Enumerations**: Document all enum types with values
5. **Capture Business Rules**: Extract and document all business logic
6. **Specify Integration Points**: Document external system dependencies

### **For Different Stakeholders**
- **Business Analysts**: Focus on domain overview and business rules
- **Architects**: Review entity relationships and integration points
- **Developers**: Study domain objects and enumerations
- **Integration Teams**: Focus on integration points and data formats
- **QA Teams**: Use all specifications for test case development

### **For Maintenance**
- **Keep Cross-References Current**: Update links when files are renamed or reorganized
- **Maintain Accuracy**: Update as source system analysis reveals new information
- **Preserve Completeness**: Add new findings without losing existing accuracy
- **Support Evolution**: Structure supports ongoing system understanding

## Success Criteria

### **Specification Quality**
- All current system functionality captured in specifications
- Development team can implement C# system from specifications alone
- Business stakeholders confirm accuracy of documented requirements
- External system compatibility requirements clearly defined

### **Documentation Standards**
- Consistent structure and formatting across all documents
- Complete cross-referencing enables efficient navigation
- Clear separation between current state and migration requirements
- Maintainable structure supports long-term documentation needs

### **Migration Readiness**
- Specifications provide complete foundation for migration planning
- All technical risks and dependencies identified
- Business logic preservation requirements clearly specified
- Integration compatibility requirements fully documented

## Getting Started

### **Creating New Specifications**
1. **Review Relevant Rules**: Study applicable rule files for document type
2. **Study Exemplars**: Review [exemplar files](exemplars/README.md) for practical examples
3. **Follow Templates**: Use provided templates and patterns from exemplars
4. **Maintain Cross-References**: Link to related specifications
5. **Validate Content**: Ensure accuracy against Phase 1 findings

### **Reviewing Existing Specifications**
1. **Check Completeness**: Verify all required content is present
2. **Validate Accuracy**: Confirm content matches source system analysis
3. **Test Implementation Readiness**: Assess clarity for development teams
4. **Verify Cross-References**: Ensure all links are functional and current

### **Updating Specifications**
1. **Identify Impact**: Determine which other documents may be affected
2. **Maintain Consistency**: Keep terminology and cross-references current
3. **Preserve Quality**: Don't compromise accuracy for convenience
4. **Update Cross-References**: Keep navigation links functional

This rule system ensures that technical specifications provide a complete, accurate, and implementation-ready foundation for successful C++ to C# system migration.

## Deterministic Steps

When starting with technical specification rules:

1. **Understand Migration Phase**: Identify if in Phase 1 (Data Collection) or Phase 2 (Specification Creation)
2. **Choose Architecture**: Select documentation-architecture (3-folder) or hybrid-architecture (layered)
3. **Create Folder Structure**: Set up docs/technical/, docs/implementation/, docs/rfcs/ folders
4. **Identify Domains**: List all domains requiring documentation from C++ system
5. **Apply Per-Domain Rules**: For each domain, apply domain-overview, entity-relationship, domain-object, etc.
6. **Enforce Anti-Duplication**: Ensure references instead of duplication across all specifications
7. **Validate Completeness**: Verify all required specification types present per chosen architecture
8. **Cross-Reference**: Link all specifications using relative file paths

## OPSEC and Leak Control

All technical specifications must comply with OPSEC requirements:
- **NO** internal server names, IP addresses, or URLs
- **NO** credentials, tokens, API keys, or passwords
- **NO** employee names or email addresses
- **NO** confidential customer data or business-sensitive information
- **NO** proprietary vendor details or licensing information
- Document structures and business logic only (infrastructure details excluded)

## Integration Points

This overview rule coordinates all technical specification rules:
- **rule.technical-specifications.architecture.v1**: Provides 3-folder foundation
- **rule.technical-specifications.hybrid-architecture.v1**: Adds layered structure
- **rule.technical-specifications.domain-object.v1**: Documents domain entities
- **rule.technical-specifications.enumeration.v1**: Documents C++ enumerations
- **rule.technical-specifications.business-rules.v1**: Documents business logic
- **rule.technical-specifications.entity-relationship.v1**: Documents database schema
- **rule.technical-specifications.integration-points.v1**: Documents external interfaces
- **rule.technical-specifications.anti-duplication.v1**: Enforces reference patterns

## Failure Modes and Recovery

**Failure**: Wrong architecture chosen for project complexity
- **Detection**: Simple project has excessive folder structure, or complex project lacks organization
- **Recovery**: Reassess per hybrid-architecture applicability criteria, adjust structure

**Failure**: Rules not consistently applied across domains
- **Detection**: Some domains have complete documentation, others are incomplete
- **Recovery**: Use this overview to ensure all specification types present per domain

**Failure**: Cross-references broken after reorganization
- **Detection**: Links to specifications result in 404 or wrong files
- **Recovery**: Systematically update all relative paths, validate all links

**Failure**: OPSEC violations in specifications
- **Detection**: Server names, credentials, or sensitive data in documentation
- **Recovery**: Remove all OPSEC-sensitive information per OPSEC section above

## Related Rules

This overview coordinates with:
- **rule.technical-specifications.architecture.v1**: Three-folder pattern
- **rule.technical-specifications.hybrid-architecture.v1**: Layered architecture
- **rule.technical-specifications.domain-object.v1**: Domain entity documentation
- **rule.technical-specifications.domain-overview.v1**: Domain navigation hubs
- **rule.technical-specifications.enumeration.v1**: Enumeration documentation
- **rule.technical-specifications.business-rules.v1**: Business logic documentation
- **rule.technical-specifications.entity-relationship.v1**: Database schema documentation
- **rule.technical-specifications.integration-points.v1**: Integration documentation
- **rule.technical-specifications.anti-duplication.v1**: Duplication prevention

## FINAL MUST-PASS CHECKLIST

- [ ] OPSEC clean across ALL specifications (no server names, credentials, emails, confidential data)
- [ ] Architecture chosen appropriate for project (3-folder or hybrid layered)
- [ ] All 9 specification rule types available and documented in this overview
- [ ] Documentation folder structure created per chosen architecture
- [ ] Cross-references use relative paths and stable rule IDs (rule.technical-specifications.*)
- [ ] Anti-duplication rule enforced preventing SQL/business rule/enum duplication
- [ ] All rules follow rule-authoring framework (10-field front matter, canonical sections, checklists)