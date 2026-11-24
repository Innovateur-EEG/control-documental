# WBS 1.2 — Dynamic Capture Controls

**Branch:** `dev`  
**Status:** Implementation and automated verification complete on `dev`. Latest CI passed after adding Word-table, Excel-workbook, and atomic template-batch regression tests. End-to-end UI verification remains pending.

## Scope delivered

- JSON-configured text input options: placeholder and maximum length.
- JSON-configured numeric input constraints: minimum, maximum, and step.
- Checkbox value normalization for persisted booleans and common string representations.
- Conditional visibility through `visible_if`.
- Dependent selection options through `options_map`.
- Configuration validation for supported field types and the new type-specific/conditional settings.
- Server-side validation of submitted values against dependent option lists.
- Preservation of existing values for fields omitted from the visible form, including hidden conditional fields.
- Automated unit tests added alongside each implementation increment.

## Current configuration examples

Conditional visibility:

```json
{
  "visible_if": {
    "field": "nacionalidad",
    "equals": "Extranjera"
  }
}
```

Dependent options:

```json
{
  "options_map": {
    "depends_on": "tipo_persona",
    "map": {
      "Fisica": ["CURP", "Identificación oficial"],
      "Moral": ["Acta constitutiva", "Poder notarial"]
    }
  }
}
```

## Acceptance and deferred verification

The implementation scope is complete on `dev`. The full CI suite passed after the Word-table and Excel-workbook regression tests were added. Subsequent atomic template-batch processing changes also passed CI. Manual UI regression checks remain pending.

When online, run:

```powershell
mise exec --command "python -m pytest tests/test_dynamic_fields.py -q"
mise test
```

Automated verification is green on `dev`. Before treating the workflow as fully accepted, perform a local UI check for:
1. A condition becoming true and false during editing.
2. A dependent selection changing after its parent changes.
3. An obsolete dependent selection being rejected on save.
4. A hidden field retaining its previously saved value.
5. Required validation not blocking submission for a hidden field.
6. Generated Word/Excel documents reflecting saved values correctly. Automated coverage now checks Word paragraph rendering, Word table-cell rendering, and Excel values across worksheets while preserving formulas and cell formatting.

## Commits

- `f5f22a2` — Add dynamic visibility and dependent option helpers.
- `134fbc4` — Test conditional visibility and dependent options.
- `5a6db10` — Use tested helpers for dynamic field rules.
- `92ae543` — Add submitted-value and capture-merge safeguards.
- `9383da5` — Test dependent selection validation and hidden-value retention.
- `ce4e785` — Validate dependent selections before saving capture data.

## Sprint exit decision

**Implementation exit:** complete.  
**Verification exit:** targeted tests passed; full-suite and UI regression checks pending.  
**Merge to `main`:** not performed.


---

## Current release and verification update — 2026-11-24

The earlier `dev` status above is historical. The current release branch is `main`.

- Dynamic capture controls are included in the released application.
- The accepted design preserves values when conditional fields are hidden.
- The package gate checks persisted required fields according to visibility.
- PR [#13](https://github.com/Innovateur-EEG/control-documental/pull/13) adds a testable submission-validation helper and consolidates save feedback. It does not change the JSON configuration or database schema.
- PR #13 automated checks passed: Python compilation, **117 pytest tests**, and CodeQL Python/Actions analysis.
- Manual UI verification for PR #13 remains pending. Use the checklist in [WBS_GESTOR_INTERFACE.md](./WBS_GESTOR_INTERFACE.md), section “Manual acceptance required”.

Do not interpret the earlier “merge not performed” statement as the current release state. PRs #10 and #11 are merged into `main`; PR #13 remains open pending manual acceptance and explicit merge authorization.
