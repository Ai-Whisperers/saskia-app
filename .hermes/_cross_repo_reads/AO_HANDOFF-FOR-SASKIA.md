# HANDOFF-FOR-SASKIA — 2026-09-07

> **Who**: Saskia (named end-user for an AIW instance design)
> **From**: Sunstein (autonomous ops agent on the AIW stack, drafting on Ivan's behalf)
> **Why**: The Drive governance audit flagged a Saskia instance design (`docs/SASKIA-INSTANCE-DESIGN-2026-09-02.md`) that contains unverified assumptions about her restaurant, workflows, integrations, hosting, privacy, and approval authority. We need your direct input — not your approval of an AI-written design.
> **Channel**: This draft is queued for Ivan to send to you on a channel of his choice (likely WhatsApp or email). Sunstein does not send external messages without operator direction.
> **Action required from you**: answer the 8 questions below. None are trick questions — they exist because we wrote a design without your answers and need them now.

---

## TL;DR — please read this first (90 seconds)

There is a draft design for an AIW instance for your restaurant at `docs/SASKIA-INSTANCE-DESIGN-2026-09-02.md`. It contains 7 (or 8 — there is a numbering inconsistency we need you to resolve) assumptions about your restaurant, your workflows, which systems it would connect to, who sees its data, and what actions only you may approve.

We do **not** want you to approve the design as a package. We want you to answer 8 questions so we can rewrite the design around your real answers, not our guesses.

**Total time**: 15-30 minutes if you answer in line. More if you want to give detailed revisions.

---

## The 8 questions

Please answer each question directly. Short answers are fine. If a question does not apply, write "N/A — [reason]".

### Q1. **Do you want an AIW instance at all?**
- Are you in scope, or did someone add you to a design without your consent?
- If yes, what is your goal — automated ordering? Inventory? Customer comms? Internal ops?

### Q2. **What real activity or organization would it support?**
- Specifically: your restaurant's name + cuisine + location + typical daily/weekly volume
- Any other organizations it should serve (e.g., a side business, family, hobby group)?

### Q3. **Where may it run?**
- Cloud (AIW's default VPS in Paraguay), your own server, a private laptop, hybrid?
- Any jurisdictions it must NOT run in (e.g., EU data residency requirements)?

### Q4. **Which systems may it connect to?**
- POS (point of sale) — which one?
- Accounting software — which one?
- Delivery platforms (Uber Eats, PedidosYa, etc.) — which ones?
- Reservation system?
- Any other internal tool?

### Q5. **Who may see its data and outputs?**
- Only you? You + a manager? You + your accountant? You + staff?
- Are there roles you explicitly want excluded (e.g., suppliers, customers)?

### Q6. **Which actions may only YOU approve?**
- Sending money?
- Modifying the menu or pricing?
- Responding to a complaint?
- Ordering from a supplier?
- Publishing to social media?
- Something else specific to your operation?

### Q7. **Does any manager also receive approval authority?**
- If yes, who, for which actions, and how are conflicts resolved?

### Q8. **Desired language mix + digest preference + pause/export/delete mechanism**
- What languages should the AI communicate in? (Spanish, Dutch, English, Guaraní?)
- How often do you want a digest of what the AI did? (daily, weekly, on-demand, never?)
- How do you want to be able to **pause**, **export all data**, or **delete** the instance?
- Are there situations where you want to be interrupted immediately vs. deferred?

---

## Numbering note

The original ticket (DEMIURGE-106) says "seven questions" but lists seven in some places and eight in others. We think the canonical list is **8** (above). If you think it's only 7, tell us which one to drop.

---

## What happens after you answer

1. Sunstein rewrites `docs/SASKIA-INSTANCE-DESIGN-2026-09-02.md` to reflect your actual answers — no guessing, no marketing-speak.
2. The revised design comes back to you for **approval of the revised version**, not approval of the original draft.
3. If you say "no, I don't want an instance at all" — the design is archived and DEMIURGE-106 is closed as **rejected**.

---

## Privacy note

- Your answers are stored in `tickets/DEMIURGE-106-answer-saskia-operator-questions/` (private to AIW repo, no public visibility).
- If you prefer, you can answer via WhatsApp voice notes — Ivan can transcribe.
- You can revoke any answer at any time by replying "withdraw Q[N]" or "delete all my answers."

---

## Contact

Reply to Ivan on the channel he used to send this. Sunstein does not have your contact info.

---

**Doc version**: 2026-09-07 v1 (draft, awaiting Ivan's channel) · **Sunstein signature** (autonomous, on Ivan's behalf) · **Reviewer**: Saskia (human) · **Effective**: on Saskia's reply
