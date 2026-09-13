# Moldova Customs V2 — product plan

V2 is **not** a new product. It is a second **import path** into the same Customs Declaration hub defined in [v1-plan.md](v1-plan.md).

Do not start V2 until V1 DocTypes, reconciliation, LCV, VAT JE, and PI Fiscalization exist and are stable. V2 must not invent parallel documents or posting rules.

## Goal

Import **paper / scanned** Moldova customs declarations (photos or scan PDFs **without** a reliable text layer) using AI, then continue the **same** V1 desk flow: allocate goods by HS, reconcile cash freight, Create LCV, Create VAT JE, link PI → Fiscalization Completed.

## What we already decided

- **V1** = official **digitally signed** ASYCUDA / SAD PDF (text layer + CMS / MoldSign). No Gemini.
- **V2** = **scanned paper** (or image-only PDF). AI extractor only. Same DocTypes, same fail-closed totals, same posting actions.
- `import_source`: `signed_pdf` (V1) | `scanned_paper` (V2).
- The Customs Declaration remains **evidence**, not an auto-poster. Upload never creates GL/SL.
- Signature verification (V1) is **not** Fiscalization and is **not** “AI said it looks fine.”
- Paper import must follow the e-Factura Purchase Factura rule: **Gemini (or equivalent) output is untrusted**. Identity, line arithmetic, and totals are fail-closed **on the server**.
- Do not put a Gemini key in Customs Settings in V1. V2 adds it (or reuses `eFactura Settings.gemini_api_key` if that app is installed — decide at implementation; prefer one key in the Moldova stack).

## Why V2 exists

Born-digital ASYCUDA PDFs (the [examples/](../examples/) corpus) have a text layer. Brokers and older files still arrive as **stamped paper scans**: fax/scan PDF, phone photo, or a PDF that is only images. Those need OCR/AI. The accountant still needs the same hub.

## What V2 must reuse unchanged

Everything in [v1-plan.md](v1-plan.md) after import:

- Customs Declaration + Item + Charge + goods allocation + cost reconciliation
- Per-row duty (Box 47 type **020**, any printed rate including 0 / 8 / 10 / 12 / 15)
- VAT type **030**; VAT base = statistical value + duty when duty exists
- **020 already includes duty on distributed freight** — never `rate × transport` again
- Many PI item rows → one CD HS row (Box 31 lists several SKUs)
- Cash freight vs duty-on-freight
- Create LCV / Create JE / Link PI / Fiscalization Completed
- `identity_key` = SHA256(company + office + declarant + year + decl_nbr)
- Private original + `file_hash`; do not replace the scan with an AI “cleaned” PDF
- `cd_*` source fields vs ERP-converted amounts
- Tests on `test.localhost` in Docker

V2 only **fills** those fields from a different extractor.

## Import pipeline (V2)

1. User uploads image or scan PDF (`import_source = scanned_paper`).
2. Store private original + hash. Do not run the V1 text-layer parser as the authority (it will be empty or garbage).
3. Optional: if a text layer exists and checksums, V2 may **prefer V1 parse** and skip AI (hybrid). If text is missing or totals fail, fall through to AI.
4. Send page images to the model with a **fixed schema** (same fields the V1 parser writes): identity, Box 22, items (HS, qty, masses, Box 46, Box 47 lines), header totals.
5. Server validates: required identity, item duty+VAT vs “Total fees”, VAT base vs statistical+duty, no invented tax types without storing raw `cd_tax_type`.
6. Create CD draft. Mark extraction provenance: `import_source`, model name, prompt version, `extraction_confidence` (informational only — never auto-submit).
7. User reviews every row (AI is a draft typist). Then V1 recon/posting.

Two MoldSign stamps on a **scan** are pictures, not CMS. Signature status = `Not Applicable` or `Indeterminate`. Never auto-`Valid`.

## AI rules (from e-Factura paper import)

Reuse the Purchase Factura pattern (`factura_ai.py` + settings key + desk `use_ai`):

- Fail closed: missing office/declarant/year/number → reject duplicate-unsafe import
- Fail closed: Σ item 020/030 ≠ printed total fees (beyond money precision)
- Fail closed: mapped HS/qty/value that the user did not confirm if the model guessed
- Never treat the model as having “approved” the declaration
- Prompt and schema versioned in code; golden tests with **sanitized** fixture images, not live [examples/](../examples/) commercial files
- Do not log raw document images or API keys

## Desk UX

- Same import dialog as V1, with a source toggle or automatic detect (text layer → V1; image-only → V2)
- Show “Extracted by AI — review required” banner on draft CDs with `import_source = scanned_paper`
- Keep the original scan on the form; show extracted fields beside it (do not need a full PDF viewer in V2 if V1 already has attach)

## Settings (V2 only)

- Gemini (or successor) API key: Customs Settings **or** shared e-Factura key
- Optional: model name, temperature 0, max pages
- No AI in unit tests unless fixture-replay / mocked client

## What V2 is not

- Not a second DocType (“Scanned Customs Declaration”)
- Not a reason to auto-post LCV/JE
- Not Customs portal XML/API
- Not recalculating legal duty from a tariff master
- Not trusting handwritten Box 47 without user review
- Not committing live hotel/broker scans to git

## Open questions (decide when V2 starts)

- Share Gemini key with e-Factura vs own field
- Hybrid: try V1 text parse first on every PDF, including scans that happen to have OCR already
- Whether poor scans (skew, stamp over Box 47) get a “manual entry only” path instead of forcing AI
- Need a small **paper-scan** corpus (the current examples folder is born-digital signed PDFs — useful as AI regression *if* we rasterize them, but that is easier than real stamps/photos)
- Prompt language: Romanian labels on the SAD vs English box numbers (prefer box numbers + printed type 020/030)

## Build slices (after V1)

### V2.0 — flag and settings

`import_source`, settings key, banner, no live model calls.

### V2.1 — schema + mocked extractor

Same JSON the V1 parser emits; tests from rasterized [examples/](../examples/) (local only) and mocked model responses.

### V2.2 — live Gemini path

Desk import for image/scan; fail-closed server checks; review banner.

### V2.3 — hybrid detect

If text layer totals pass, use V1 parser; else AI.

## Relationship to V1 slices

| V1 slice | V2 |
| --- | --- |
| 0 AGENTS.md | Add one invariant: V2 AI is untrusted; V1 parsers must not call AI |
| 1–6 DocTypes, recon, LCV, JE, fiscal | Unchanged consumers |
| 2 signed PDF parser | Sibling module; V2 must write the same normalized structure |
