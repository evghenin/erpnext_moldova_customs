# AI Agent Instructions

## Output Rules

- Be concise and direct.
- Omit introductory and concluding filler.
- Return only the requested code, focused diff, or brief bullet points.
- Show only changed sections unless full context is required for correctness.
- Include necessary test results, assumptions, warnings, and blockers.

## Context-Efficient Workflow

- Start from the user's named file, symbol, failing test, command, or diagnostic.
- Form one local hypothesis before exploring broadly and identify the cheapest check that can disprove it.
- Search narrowly and read only the nearby code needed to understand the controlling path.
- Reuse existing utilities, DocType methods, and analogous tests before adding abstractions.
- For an error, begin with the supplied snippet and immediate diagnostic; inspect one nearby dependency only when necessary.
- Avoid broad repository mapping, repeated reads, unrelated refactors, and architectural redesigns unless requested.
- Do not rewrite unchanged file sections.
- Make the smallest testable patch, then run the narrowest relevant validation before further edits.
- Do not skip tests, validation, security checks, or required domain reasoning to save tokens.

## Project Stack

- Python 3.10+ with Frappe/ERPNext v15. App: Moldova customs declarations (import-cost hub).
- Current work is **V1** (signed ASYCUDA/SAD PDF). **V2** (scanned paper + AI) is later and must reuse V1 DocTypes.
- Put business rules in the owning DocType or existing utility module. Preserve Frappe permissions and lifecycle.
- Use `FrappeTestCase` for database and DocType behavior; use `unittest.TestCase` for pure parsers and utilities.
- Follow `pyproject.toml`, `.pre-commit-config.yaml`, and `.editorconfig`: Ruff, 110-character Python lines, Python 3.10 syntax, double quotes, tabs for source files, two-space JSON indentation.
- SAD source fields: `cd_*`. Do not fork Purchase Factura. Soft-depend on `erpnext`; reuse e-Factura Fiscalization / file / timeline patterns when present.
- `required_apps = ["erpnext"]`. Do not add Gemini or a second Fiscalization widget in V1.

## Validation

- ERPNext/Frappe runs in Docker under WSL. `bench` is not on the WSL host PATH.
- Identify the running stack with `docker ps` or `docker compose -f .devcontainer/docker-compose.yml ps` from the `erpnext-dev` repo root.
- Run all `bench` commands and tests inside the Frappe container (`devcontainer-frappe-1` / service `frappe`). Do not treat host `bench: command not found` as a test failure or a reason to skip validation.
- Prefer a focused test for the changed behavior.
- Use site `test.localhost` for all `bench run-tests`. Do not use `development.localhost`.
- Full suite: `bench --site test.localhost run-tests --app erpnext_moldova_customs`
- Formatting / mixed file types: `pre-commit run --all-files`
- Report failures briefly. Do not hide unrelated pre-existing failures.

## Versions

- **V1 (now):** digitally signed ASYCUDA/SAD PDF, text-layer parse + CMS/MoldSign. Parsers must **not** call AI.
- **V2 (later):** `import_source = scanned_paper`; AI fills the **same** CD schema. Model output is untrusted; fail-closed identity and totals on the server. Do not start V2 until V1 hub, recon, LCV, VAT JE, and Fiscalization exist.

## Domain Invariants

- The Customs Declaration is the import-cost **hub and fiscal evidence**. Import/submit must not create GL or stock ledger entries. Posting is an explicit user action (Create LCV, Create JE, Link PI).
- Preserve original files, bytes, hashes, and provenance. Derivatives must not replace originals. Never auto-mark signature `Valid`. Signature ≠ review ≠ Fiscalization.
- Keep `cd_*` source values separate from ERP-converted currency, qty, UOM, and amounts.
- `identity_key` = SHA256(company + office + declarant + year + decl_nbr). Reject duplicates; lock per company on concurrent import.
- Duty is **per CD item** (Box 47 type `020`). Missing 020 = 0%. Store the printed rate; do not hardcode 5/8/10/12 (samples include 15%). VAT is type `030`.
- Type `020` already includes duty on that row’s **share of transport** (SAD distributes freight by amount into Box 46). Never LCV `duty_rate × freight`. Cash freight is a separate recon target (PI tax, PI line, or separate PI).
- One CD item (HS / Box 31) groups **many** PI item rows. Never assume 1:1. One PI item maps to at most one CD item.
- Reconcile goods (by HS) before costs. Create LCV only from full per-row `020` plus cash freight that is not already a PI valuation charge. Create JE only from `030`. VAT never goes on LCV.
- Linked submitted CD is fiscal evidence for the **goods** PI. Reuse `Purchase Invoice.fiscal_status` (Fiscalization Completed). Cancel/unlink recalculates. A draft or unlinked CD does not complete it.
- Fail closed when item 020/030 sums disagree with printed totals (money precision). Store unknown Box 47 types as raw `cd_tax_type`; do not invent procedure-fee codes.
- Timeline: Info records via `log_event` (English msgid + args). Do not `_().format(...)` before write.
- `examples/` is gitignored commercial SADs. Develop against it locally; commit only sanitized fixtures or golden JSON. Do not commit live PDFs, scans, or API keys.

## References

- [docs/v1-plan.md](docs/v1-plan.md) — V1 product plan, SAD boxes, domain model, slices.
- [docs/v2-plan.md](docs/v2-plan.md) — scanned-paper / AI import path.
- [README.md](README.md) — install and tooling.
- Keep this file short; change product rules in the plans, then update invariants here.

## Scope Boundaries

- Keep changes limited to files relevant to the requested task.
- Add hooks or new dependencies only when technically required.
- If a required change affects an unrelated-looking file, explain why before proceeding.
- Do not commit changes or create branches unless explicitly requested.
- Do not implement V2, Customs portal API, or auto-posting unless the user asks.
