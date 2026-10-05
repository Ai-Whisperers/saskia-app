<!-- ROADMAP-REDIRECT -->
# ⚠️ Moved

**This ADR has been moved.** The canonical location is:

> **`docs/roadmap/decisions/ADR-001-test-architecture.md`**

See [`docs/roadmap/decisions/`](../../docs/roadmap/decisions/) for the full decisions index.

---

<!-- ORIGINAL CONTENT BELOW -->

# ADR-001 — Test architecture: factories, flows, invariants

**Status:** accepted (2026-09-25)
**Audience:** Kiki + any future contributor writing tests in this repo.

## Context

The suite grew to 2,200+ tests across 233 files with three recurring
costs: hand-rolled seed data (998 raw session sites, 49 copy-pasted
helpers, UNIQUE-collision flakes), repeated HTTP boilerplate (299 direct
client.post sites), and inline invariant assertions. Six production bugs
in one week were of the cross-route class no unit test could catch.

## Decision

Three-layer architecture; extend it, don't fork it:

1. **`tests/factories.py`** — ALL DB row construction. Unique-by-construction
   names, `**kw` passthrough, traits, explicit timestamps, composition sugar
   (`make_catalog`/`make_sellable`). Never write `Ingredient(name=...)` inline
   in a new test.
2. **`tests/flows.py`** — ALL HTTP driving. Real form contracts (repeated
   fields, CSRF, redirect conventions), `FlowResult` with `.ok/.json/.flash`,
   `api_crud()` for JSON clusters, `assert_see()` for content, `as_anonymous()`.
3. **`tests/_lib/invariants.py`** — cross-session assertions
   (stock-never-negative, money-is-int, audit-covers, snapshots-immutable,
   FK-clean). One import per scenario.

Scenario tests live in `tests/e2e/` and use all three; unit tests may use
factories directly.

## Consequences

- New route ⇒ add a flow helper + a negative-path row in the matrix +
  the route-coverage manifest enforces a test reference exists.
- Every prod incident gets a regression test named for its class
  (bug→test rule; see test_hotfix_regressions, test_route_coverage_manifest).
- Serial run is the release gate; `-n 4` (make test-xdist) is the fast loop;
  plain `pytest` is order-stable (`-p no:randomly` in addopts).

## Checklist: adding a new route (tear-off)

- [ ] Flow helper in tests/flows.py (form fields verified against the route signature)
- [ ] Happy-path scenario (e2e) using factories, never inline models
- [ ] Negative-path row in tests/e2e/test_negative_path_matrix.py
- [ ] Route-coverage manifest passes (it will fail until the above exist)
- [ ] If it mutates stock/money: an invariants assertion in the scenario
