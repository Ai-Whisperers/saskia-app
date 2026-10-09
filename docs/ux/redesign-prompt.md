# Master redesign prompt

Standing brief for every Sazón screen change. Read this before redesigning a page.

The goal is an interface where employees immediately understand what to do, without being overwhelmed by dozens of options.

Three design principles:

1. **Progressive disclosure.** Show essential information first. Put secondary functionality inside dropdowns, expandable sections, tabs, or contextual menus.
2. **Intuitive workflows.** Organize each screen around the actual sequence of tasks employees perform, rather than simply displaying database fields.
3. **Functional preservation.** Every existing feature, setting, field, calculation, and action must remain accessible and work exactly as before.

Design philosophy, applied the same way in Gerencia, Ventas, Cocina, Inventario, and every existing page:

**Everything available. Only what's relevant visible. The next action always obvious.**

The interface responds to the employee's choices instead of showing every possible field from the beginning. On Ventas, choosing Mostrador prioritizes immediate checkout. Choosing Delivery reveals the address and delivery scheduling fields. When creating a product, selecting a recipe may populate the portion details the system already supports. Do not invent new business behavior to make a screen shorter.

---

## Critical design principle

**Simplify visibility, never functionality.**

Sazón is a comprehensive restaurant management system with interconnected operational modules. The objective is to dramatically simplify the visual interface without reducing the system's capabilities.

A simple interface does not mean a simple system. The complexity should be managed by the interface, not transferred to the employee.

### Absolute rules

1. Never delete existing functionality.
2. Never remove existing fields, actions, settings, filters, calculations, or workflows.
3. Never disable features merely because they complicate the interface.
4. Never change business logic to accommodate a simpler visual design.
5. Never make previously accessible features inaccessible to authorized users.
6. Never remove important operational information simply to make a screen look cleaner.

Use progressive disclosure instead.

---

## Visual hierarchy

Every page has three levels.

### Level 1 — Essential

Immediately visible, with no extra interaction:

- Primary information
- Current task or operational state
- Required inputs
- Critical alerts
- Main action
- Relevant totals or quantities

### Level 2 — Secondary

Reachable through one simple interaction:

- Additional settings
- Optional fields
- Advanced filters
- Import and export
- Printing
- Additional transaction details
- Less frequently used actions

Use dropdown menus, expandable sections, tabs, contextual action menus, and clearly labeled secondary controls.

### Level 3 — Advanced

Keep specialized functionality in a clearly identified advanced section. Do not bury a feature inside multiple nested menus. A user should find any existing feature without guessing where it went.

---

## Workflow-first design

Before redesigning any page:

1. Identify its primary purpose.
2. Identify the employee's most common tasks.
3. Determine the natural sequence of actions.
4. Identify which information is needed at each stage.
5. Organize the interface around that sequence.
6. Identify optional and secondary functionality.
7. Move secondary functionality into the matching expandable control.
8. Preserve all original capabilities.

### Sales

Select products, review the cart, enter the required transaction details, choose the payment method, confirm the sale.

Receipt configuration, notes, and scheduling stay available when they are relevant.

### Product creation

Enter the product name, choose the category, set the price, link the recipe, configure availability, save the product.

Advanced settings, certifications, metadata, images, tags, and additional pricing options stay accessible.

### Kitchen

View production requirements, review quantities and priorities, prepare products, update production status, complete the production tasks.

Planning, HACCP, forecasting, printing, recipes, and reporting stay accessible.

### Inventory

View current stock, identify items that need attention, review or update stock, record the applicable movements, confirm the changes.

Every existing inventory function stays.

---

## Discoverability

Hiding a control must not create confusion. Use clear labels:

- Más opciones
- Configuración avanzada
- Datos adicionales
- Opciones de facturación
- Herramientas
- Filtros avanzados

Avoid vague controls. Do not make users memorize where a feature went. Do not nest navigation more than two levels deep.

Do not hide a frequently used action just to make the screen look minimal. Visibility depends on frequency of use, operational importance, relevance to the current task, safety, and the user's role. Critical warnings and required operational controls stay immediately visible.

---

## Consistency

Use the same progressive-disclosure patterns across the application.

- Advanced filters behave the same way on every page.
- Expandable sections share styling and interaction.
- Forms follow a predictable structure.
- The confirmation action is easy to find.

An employee should learn the pattern once and recognize it everywhere.

---

## Functional verification

Before redesigning a page, inventory every existing field, control, and user action.

After the redesign, verify that every feature is still accessible and still works. Check:

- All user roles
- All navigation routes
- All forms and validation
- All dropdowns and expandable sections
- All calculations
- All data relationships
- All reporting functions
- All operational workflows
- All authorization boundaries

Compare the redesigned page with the original inventory. A page is not complete if any existing capability has become inaccessible.

The employee should always be able to answer:

1. Where am I?
2. What am I supposed to do here?
3. What should I do next?
4. Where can I find additional options?
5. Has my action been completed successfully?

The interface guides the task. It does not ask the employee to interpret a complicated form.
