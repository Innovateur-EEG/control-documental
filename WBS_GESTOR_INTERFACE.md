# Gestor Interface Closure

**Branch:** `dev`  
**Implementation status:** Atomic package processing, persistence hardening, generated/signed path separation, and signed-PDF cache invalidation passed CI. A review found and fixed stale signed-package metadata on “Reiniciar Flujo”; regression coverage and CI for that final fix are pending. Local/cloud end-to-end acceptance remains open.

## Scope

This work closes the end-user (gestor) workflow without redesigning the application or changing the existing metadata-driven capture configuration.

- Project administrators are scoped to their assigned projects in individual-file review, export tools, and the entity catalog; SuperAdmin scope remains global. “Mis Expedientes” is independent of Admin project scope and shows direct user assignments plus descendants.
- The document-progress dashboard remains global for Admin and SuperAdmin, by explicit requirement.
- Entity catalog scoping uses an EXISTS-style relationship filter, not DISTINCT over the full Persona row, because PostgreSQL JSON columns do not support equality comparisons.
- Direct assignments take precedence; inherited permissions resolve through the nearest assigned ancestor.
- Unknown/missing permissions fail closed to read-only.
- Hierarchy traversal is cycle-safe.
- Read-only users cannot trigger write operations such as package generation.
- Evidence uploads report failures cleanly and commit their database record only after storage upload succeeds.
- Generated PDF packages are persisted in Supabase Storage and can be downloaded again after a new session.
- Package generation now fails closed: if any configured template is missing, unsupported, fails to download/render, or fails PDF conversion, no partial package is returned or published.
- Generated-package path resolution does not fall back to a legacy signed-file path when generated-path metadata is absent; this protects old signed records from misidentifying the signed PDF as the generated original.
- Signed packages have a separate storage path; metadata preserves the generated-package path.
- Signed-package upload is unavailable until a package record exists.
- Removing access targets the selected user/person assignment; deleting a person clears the mapped association relationship.

## Automated tests

The new pure-helper tests cover hierarchy cycles, direct permissions, inherited permissions, nearest-ancestor precedence, and default-deny behavior.

Run in PowerShell:

```powershell
mise exec --command "python -m pytest tests/test_gestor_logic.py tests/test_dynamic_fields.py -q"
mise test
```

## Manual acceptance checklist

Use a non-production test project and accounts. Do not validate destructive actions against production data.

1. A Gestor with no assignments sees the empty-state message.
2. Confirm “Mis Expedientes” displays direct assignments and descendants independently of Admin project scope. Separately, confirm project Admin scope in “Revisión de Expedientes Individuales,” “Herramientas de Exportación,” and the entity catalog; confirm “Tablero de Avance Documental” remains global.
3. A descendant of an assigned person appears; nested descendants inherit the nearest assigned ancestor's permission.
4. A read-only user can inspect and download existing material but cannot save capture data, upload evidence, generate a package, upload a signed package, or change traceability.
5. **How to test:** use a writable test user and a test entity with at least one field controlled by `visible_if`. Record the current value of that conditional field and one unrelated field. Change the controlling field so the conditional field disappears, save, then change the condition back so it reappears. Verify its prior value is preserved. Change and save one unrelated field too, and verify that value persists after rerun/reopening the entity. If no conditional field is configured, create a temporary test configuration first; do not alter production data.
6. **How to test:** upload a small harmless file to a test entity. Verify it appears in the app and in the `expedientes` Supabase Storage bucket, and that a matching `DocumentoExpediente` row exists. The automated test `tests/test_evidencias.py` now simulates a storage failure and verifies rollback occurs without persisting a document record. Do not simulate storage failures by changing the bucket in production.
7. Generate a package, leave the page/session, return, and download the same persisted package.
8. Upload a signed PDF; verify the signed path and status are stored while the generated-package path remains available in metadata.
9. Enter courier delivery details; verify the method, date, carrier, and tracking number persist after rerun.
10. Remove one selected user's access and verify other users' assignments remain.
11. Run the full test suite; check generated Word/Excel/PDF outputs against a known sample.

## Latest manual UX results (2026-10-19)

- Items 1–4 passed, including the prior project-scope checks. The intermittent blank-screen issue has not recurred; continue monitoring.
- Items 5 and 6 were pending before the latest changes. Item 5 now has an explicit JSON example in the chat; item 6 has an automated failure-path test. The manual persistence and successful-upload checks still need local validation.
- The user accepted the prior outcomes for items 7–9; the latest requested labels and package workflow adjustments are implemented but still need local UX verification.
- Access revocation isolation (item 10) passed on 2026-10-21: revoking one selected user's assignment did not affect other users' independent assignments. Full CI and the remaining manual acceptance are tracked below.

## Additional UX requirements

- “Directorio de Usuarios y Accesos” must be visible only to SuperAdmin. The section is now rendered only for SuperAdmin.
- The project-linking picker must not expose arbitrary global entities to a project Admin. It now limits Admin candidates to entities already within their assigned-project scope and excludes entities already linked to the selected target project. SuperAdmin can choose any entity not already linked to that target project.

## UX test findings (2026-10-19)

- **Confirmed defect:** project Admin view can fail with PostgreSQL `could not identify an equality operator for type json` when the entity catalog query applies `DISTINCT` to full `Persona` rows. Fixed on `dev` by using a relationship `EXISTS` filter.
- **Confirmed scope defect:** “Revisión de Expedientes Individuales” and “Herramientas de Exportación” used the global participation list. Fixed on `dev` to use only participations from the Admin's assigned projects. The “Tablero de Avance Documental” remains global.
- **Open UX defect:** after login, the screen intermittently appears blank for any user and recovers after refreshing and logging in again. Cause not yet established; capture the Streamlit terminal output and browser console at the time of occurrence before making a speculative fix.

## UX feedback implementation (2026-10-20)

Changes pushed to `dev`; they are not yet accepted as locally validated.

- Added `visible_if` example for a field conditional on `estado_civil == "Casado"`.
- Evidence upload now uses a form submission to keep file selection and upload action together; it supports replacing an existing evidence file. Evidence configuration now supports a JSON object, including an optional `vigencia` value displayed in the Gestor view; numeric `vigencia` values are interpreted as days.
- Added `tests/test_evidencias.py` for storage-failure rollback and success-path persistence, plus a GitHub Actions workflow for targeted tests and Python compilation.
- Added an additive migration for `configuracion_evidencias.configuracion_json` and `usuarios.nombre`. Run `mise run db-migrate` before using the updated app against an existing database; the migration does not delete existing data.
- Changed the user-facing tab to “Documentos Adjuntos” and package workflow terminology to “Paquete para firma”.
- Package workflow now displays sections in order 1 (download), 2 (signature instructions), 3 (attach signed package). Regeneration requires explicit confirmation and clears signed-package/delivery metadata; it attempts to remove the previous signed file from Storage.
- Signed package upload button now reads “Cargar/Adjuntar paquete firmado”; the signed-file link action reads “Generar link de descarga”.
- Project manager receipt control was moved to the document progress dashboard, restricted to the project's Admin or SuperAdmin, and shown only for packages that have been sent. Gestor users are directed to the dashboard for receipt registration.
- User records now have an optional name field so the delivery recipient can be displayed with name, email, and phone. Existing accounts will need their names filled in through “Directorio de Usuarios y Accesos”.
- CI passed for the initial atomic template-processing changes. CI for the latest added batch-failure and legacy path-separation regression tests remains in progress. Local end-to-end validation remains required.

## Known verification boundary

Unit tests do not prove that Supabase Storage, the configured database, Streamlit reruns, project-specific access, or generated documents work together. Keep the WBS open until the local acceptance checklist is complete.

## Data integrity and persistence hardening

**Scope:** evidence uploads, generated PDF packages, signed PDF packages, and package/delivery metadata. Work is incremental on `dev`; no broad refactor.

### Implemented

- Evidence uploads now remove the newly uploaded object if database persistence fails; the original error is preserved if rollback or cleanup also fails.
- Generated packages use unique storage paths instead of overwriting the current package before the database commit. The previous generated object is removed only after the new metadata commits successfully; historical signed PDFs are retained in Storage.
- Signed-package uploads use unique paths, preserve the generated-package reference, and retain prior signed objects as history. Metadata points to the latest signed upload.
- Replacing a signed package invalidates the session-cached download bytes so the UI cannot offer a previously cached version as the current file.
- Restarting the delivery flow clears the active signed-package path, signed-file label/date, and delivery metadata, and invalidates cached signed bytes. The signed object remains in Storage as history.
- Failed database persistence triggers cleanup of the newly uploaded generated/signed object. Cleanup failures are surfaced as warnings rather than hiding the primary failure.
- Regression tests cover upload failure, persistence failure, cleanup failure, and the success path for the shared upload/persist helper.

### Still to verify

- GitHub Actions passed for persistence hardening, atomic template processing, generated/signed path separation, and signed-PDF cache invalidation. CI for the reset-flow metadata regression fix is pending.
- Manual cloud smoke test: evidence upload passed. Package generation/replacement, signed upload, persistence after reload, and generated/signed path separation passed. Updated signed-upload label/widget refresh, download-link placement, required-field gate, access revocation isolation, and PDF signature-package workflow for configured Word and Excel templates were accepted. This is not a claim of standalone Excel/PDF generation. Do not test destructive cases against production data.
- Storage cleanup is best-effort: if Supabase removal fails, the application warns and can leave an orphaned object for later cleanup.


## Latest manual acceptance and follow-up (2026-10-21)

- Gestor access/permission checks and conditional-field persistence are accepted.
- Evidence upload passed all three checks: visible in the app, present in Supabase Storage, and matching `DocumentoExpediente` record present.
- Package-flow checks 1–2 and 4–6 passed. The generated-package folder retains only the current generated PDF; the signed folder retains prior uploads as history.
- Signed PDF upload itself works. UI follow-up implemented on `dev`: show uploaded filename and timestamp, reset the uploader widget after upload, and place “Generar link de descarga” beside the file label.
- Package tab is now hidden while visible required capture fields are missing or invalid, with an informational message naming the fields. Values must be saved before the gate opens.
- Automated CI passed for the latest `dev` commit `10370e2` (run [39787357701](https://github.com/Innovateur-EEG/control-documental/actions/runs/39787357701)).
- Do not merge to `main` until remaining manual acceptance is complete and the user explicitly authorizes the merge.


## Final acceptance update (2026-10-22)

- Access revocation isolation passed: revoking the selected user's assignment left other users' independent assignments intact.
- PDF signature-package workflow passed for configured Word and Excel templates. This validates conversion/signature-package processing, not independent Excel or PDF output generation.
- “Mis Expedientes” was decoupled from Admin project scope for direct assignments and descendants. Manual validations passed: independent assignment visibility/editability across projects, single top title for Usuario, and no duplicate heading in Admin tabs.
- Latest CI run [39787357701](https://github.com/Innovateur-EEG/control-documental/actions/runs/39787357701) passed on commit `10370e2`.
- Remaining: final diff review and explicit user decision on whether to merge `dev` into `main`. `main` remains unchanged until explicit authorization.


---

## Current maintenance status — 2026-11-24

### Completed on `main`

- PR [#10](https://github.com/Innovateur-EEG/control-documental/pull/10) fixed empty section headings in the dynamic capture form.
- PR [#11](https://github.com/Innovateur-EEG/control-documental/pull/11) shortened the required-fields blocker message.
- Both changes are merged into `main`. Their checks passed.

### Capture feedback correction — PR #13

PR [#13](https://github.com/Innovateur-EEG/control-documental/pull/13) is open against `main`.

The source of the misleading green status was the permission indicator:
`st.success("✏️ Edición Completa")` represented edit permission, not form completion.
The UI now uses a neutral `Permiso: edición` caption.

The PR also:
- Moves the persisted-required-fields package blocker beside the save action.
- Consolidates validation, save failure, and save success feedback beside that action.
- Displays success only after the database commit succeeds.
- Rolls back failed commits and shows a safe error message.
- Extracts capture validation into a pure helper with regression tests.
- Preserves the existing dynamic-field JSON configuration and database schema.

### Automated verification

For PR #13, GitHub Actions completed successfully on 2026-11-24:

- Python compilation: passed.
- Full pytest suite: **117 passed, 65 warnings**.
- CodeQL Python analysis: passed.
- CodeQL Actions analysis: passed.

These results establish automated verification only. They do not establish manual UI or cloud acceptance.

### Manual acceptance required

Use a non-production environment and test accounts. Do not use production data for negative tests.

1. **Permission label:** open an editable expediente. Confirm the green “Edición Completa” status is gone. Confirm the neutral “Permiso: edición” caption appears. Confirm read-only users still see “Solo Lectura”.
2. **Invalid required field:** clear one visible required field and select “Validar y Guardar Datos”. Confirm red validation appears beside the button. Confirm no green save message appears.
3. **Persistence after invalid save:** reopen or refresh the expediente. Confirm the last saved value remains unchanged.
4. **Package blocker:** while a required value remains missing, confirm the blocker message appears beside the save button. Confirm “Paquete para firma” remains unavailable.
5. **Successful save:** enter valid values for all visible required fields and save. Confirm “Datos guardados correctamente” appears beside the button after rerun.
6. **Persistence after successful save:** refresh or reopen the expediente. Confirm the new values remain saved.
7. **Package gate opens:** confirm “Paquete para firma” appears only after persisted required values are valid.
8. **Conditional field preservation:** hide a conditional field, save an unrelated visible field, then make the condition true again. Confirm the hidden field's previous value remains.
9. **Dependent options:** change a parent field. Confirm the child options update and allow only a currently valid selection.
10. **Read-only behavior:** confirm a read-only user cannot save capture data.
11. **Database failure handling:** only if a safe test database is available, simulate a failed save. Confirm no success message appears and the previous saved values remain.

### Required user evidence

For each step, report **Pass**, **Fail**, or **Not tested**.
For failures, provide a screenshot and the relevant Streamlit terminal/browser-console error.
Redact personal data, access tokens, connection strings, and other secrets.
Identify only the environment type (local, staging, or production); do not send credentials.

### Branch and deferred work

- PR #13 is based on current `main`. The `dev` branch was 11 commits behind `main` when work started.
- Do not merge PR #13 until manual acceptance is complete and the user explicitly authorizes the merge.
- Issue [#12](https://github.com/Innovateur-EEG/control-documental/issues/12), explicit row/column placement for dynamic fields, remains intentionally deferred. It would change the JSON configuration and is outside this bug fix.
- The intermittent blank screen after login remains a monitoring item. Its root cause is unknown; collect logs if it recurs.
