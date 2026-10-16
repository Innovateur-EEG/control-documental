# WBS 1.2 — Dynamic Capture Controls

**Branch:** `dev`  
**Status:** Implementation complete; targeted automated tests passed (41 tests); full-suite and UI verification remain pending.

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

The implementation scope is complete on `dev`, but this is **not a test-verified release**. The targeted dynamic-field test file was run locally on 2026-10-16 and all 41 tests passed. The full test suite and manual UI regression checks remain pending.

When online, run:

```powershell
mise exec --command "python -m pytest tests/test_dynamic_fields.py -q"
mise test
```

Run the full suite and resolve failures before treating WBS 1.2 as technically accepted. Then perform a local UI check for:
1. A condition becoming true and false during editing.
2. A dependent selection changing after its parent changes.
3. An obsolete dependent selection being rejected on save.
4. A hidden field retaining its previously saved value.
5. Required validation not blocking submission for a hidden field.
6. Generated Word/Excel documents reflecting saved values correctly.

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
