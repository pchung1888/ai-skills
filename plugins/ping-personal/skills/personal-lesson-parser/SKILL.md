---
name: personal-lesson-parser
model: haiku
description: Parser / ingestion lessons -- PDF extraction, CSV ingest, HTML scraping, staging pipelines, idempotency, confidence tracking, tax-year handling. Invoked by personal-lesson master router when classification matches parser keywords, or directly via /personal-lesson-parser or natural phrases like "lessons about parsing", "lessons about PDF", "lessons about CSV", "lessons about ingest". Appends new lessons to ~/.claude/lessons/personal-lesson-parser.md and reads from there for browse mode.
user_invocable: true
---

# /personal-lesson-parser -- Parser / Ingestion Lessons

Lessons about reading, extracting, and staging data from external sources: PDF
documents, CSV exports, HTML pages, bank statements, and any other ingestion
pipeline. Not specific to any single project or data source.

---

## Capture flow (invoked by master router or directly)

### Step 0 -- Hard-rule gate (when invoked directly)

If invoked directly (not via the master router), check CLAUDE.md and
.claude/rules/*.md for hard rules that the incoming lesson would duplicate. If
the lesson IS a duplicate of a hard rule, reply:

> This is already a hard rule in CLAUDE.md / .claude/rules/. Nothing appended.

Then STOP. If invoked via the master router, skip Step 0 (the router already
ran it).

### Step 1 -- Duplicate check

Grep BOTH sources for a distinctive phrase from the incoming lesson (a file
format name, an error string, a 5-word snippet of the Rule):

1. `~/.claude/lessons/personal-lesson-parser.md` (user-scope appends, skip if absent)
2. The `## Seed Lessons` section of THIS file (`personal-lesson-parser/SKILL.md`)

If either matches, reply:

> Duplicate: already recorded as "<existing title>" in personal-lesson-parser.
> Nothing appended.

Then STOP.

### Step 2 -- Append

Use Edit (or Write if the file does not exist) to append before the end of
`~/.claude/lessons/personal-lesson-parser.md`, using the standard format:

```markdown
---

## [SEVERITY] [Short Title]
**Domain:** parser
**Discovered:** [YYYY-MM in America/New_York -- never UTC]
**Context:** [1-2 sentences -- when this surfaced]
**Problem:** [What goes wrong without this knowledge]
**Rule:** [Actionable imperative -- concrete thing to do or avoid]
**Example:** [Optional: wrong vs right snippet, error message, or file reference]
```

Create `~/.claude/lessons/personal-lesson-parser.md` if absent. The file should
begin with a brief one-line header on creation:
`# Lessons -- Parser / Ingestion (user-scope, auto-appended)`

After appending, confirm: "Appended to ~/.claude/lessons/personal-lesson-parser.md."

---

## Browse mode

When asked "show me parser lessons" or "lessons about <topic> in parsing":
1. Read `~/.claude/lessons/personal-lesson-parser.md` if it exists.
2. Also read the Seed Lessons section below.
3. Search for the user's term across both sources.
4. Quote lesson text verbatim -- do not paraphrase.

---

## Seed Lessons

The lessons below are cross-project reference seeds. They record patterns that
recur in any ingestion pipeline regardless of the specific data source.

---

## CAUTION Stage Imports Before Canonical Writes
**Domain:** parser
**Discovered:** 2026-04
**Context:** Reviewing an ingestion pipeline where raw data (PDFs, CSVs, hand-
entered records) was parsed and written directly into the canonical output store
without a staging step.
**Problem:** Writing parsed rows directly into canonical output makes partial
parses, duplicate records, and misclassified records hard to audit or roll back.
A single bad file can corrupt the entire dataset.
**Rule:** Ingest into a staging structure first. Preserve raw source metadata
there (source file, row index, parse timestamp). Validate confidence and merge
keys. Then promote only reviewed, validated records into the canonical store.
**Example:** Right: `raw source -> staged_imports -> validated records -> canonical output`.
Wrong: `raw source -> canonical output`.

---

## CAUTION Preserve Parser Confidence and Source References on Every Extracted Value
**Domain:** parser
**Discovered:** 2026-04
**Context:** A parser extracted numeric values from PDFs where the source layout
could be ambiguous (columns misaligned, OCR uncertainty, multi-page spanning).
**Problem:** A numeric value without parser confidence, source file, page, and
extraction reference cannot be verified when a reviewer flags a suspicious
figure. You cannot reconstruct which text in which PDF produced the number.
**Rule:** For every PDF-derived value, store: confidence score (or extraction
method), source file path, page number, and the matched text span. Do this at
the staged-import layer, before promotion to canonical output.
**Example:** A staged record should carry `source_file`, `page`, `confidence`,
and `matched_text` alongside the extracted value, not just `{ "value": 12345 }`.

---

## CAUTION Make CSV Merges Idempotent With Stable Composite Keys
**Domain:** parser
**Discovered:** 2026-04
**Context:** A pipeline that imported overlapping date ranges from bank and
brokerage CSV exports, potentially running the same import multiple times.
**Problem:** Appending CSV rows without deterministic merge keys double-counts
transactions, balances, or holdings when imports are rerun or files overlap.
**Rule:** Define a stable idempotency key per CSV source before merging. Use
durable fields: account id, posting date, amount, description, and any
source-provided transaction id. Keep the source filename and row index as audit
metadata (not as the only dedupe key -- filenames change on re-export).
**Example:** A composite key like `account|posted_date|amount|description|txn_id`
for transactions. If `txn_id` is absent (some exports omit it), fall back to
the normalized composite of the other four fields.

---

## CAUTION Separate Tax Year From Import Month in Data Model
**Domain:** parser
**Discovered:** 2026-04
**Context:** An ingestion pipeline organized around calendar months (e.g. an
import for "2026-04"). Annual tax documents (W-2, 1099, etc.) were being
associated with the month of import rather than the tax year they covered.
**Problem:** Treating W-2 and other tax documents as belonging to the import
month attaches tax-year 2025 data to import month "2026-04", or buries annual
tax facts inside monthly data. Year-end reporting and lookups by tax year break.
**Rule:** Model tax-year records with an explicit `tax_year` field, separate from
`import_month`. Link them to a monthly run as provenance metadata only.
**Example:** A W-2 imported in April 2026 for tax year 2025 should store
`tax_year: 2025` and `import_month: "2026-04"` as distinct fields. Queries for
"what are my 2025 tax documents" should filter on `tax_year`, not `import_month`.

---

## CAUTION Recovered Artifacts May Embed Their Own Data Model
**Domain:** parser
**Discovered:** 2026-04
**Context:** Porting a recovered HTML tool that had no separate JSON or CSV data
source. Initial assumption was that there must be an external data file somewhere.
**Problem:** Assuming there is an external data file causes wasted search time
and can lead to creating a redundant file that conflicts with the embedded
constants the original tool was designed to use.
**Rule:** When porting any recovered artifact (HTML, legacy script, archive
export), inspect the source for embedded constants, form defaults, and
calculation functions BEFORE searching for an external data file. Treat
embedded assumptions as the source of truth until a canonical external file
is confirmed to exist.
**Example:** An HTML planning tool stored all defaults and simulation functions
directly in its script block -- constants like `limit: 72000`, `ytdContrib: 24500`.
No external data file; the embedded values ARE the data model.

---

## CAUTION Never Use Document-Level Summaries as Line-Item Source
**Domain:** parser
**Discovered:** 2026-05
**Context:** A monthly data update populated a transactions list with one row
per statement summary (e.g. "statement purchases and fees total") instead of
extracting the merchant-level line items from the source documents.
**Problem:** The output appeared updated but the category breakdown was wrong --
most transactions collapsed into a single uncategorized bucket because the
parser captured totals, not the individual purchases those totals summarized.
**Rule:** For any ingestion that is supposed to produce line-item records (e.g.
transactions, invoice rows, individual expenses), extract from the line-item
source (the PDF statements, CSV exports with one-row-per-transaction). Use
summary documents only for aggregate balances and totals -- never as a source
for synthetic transaction rows.
**Example:** Wrong: one row per credit card statement with a `purchases total`
description. Right: one row per merchant transaction, each with date, merchant,
category, and amount.
