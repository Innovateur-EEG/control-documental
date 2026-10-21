# Gestor Interface Closure

**Branch:** `dev`  
**Implementation status:** Atomic package processing, persistence hardening, and generated/signed path regression tests passed CI. A follow-up fix invalidates cached signed-PDF bytes after replacing the signed file; its CI run and local/cloud end-to-end acceptance remain open.

## Scope

This work closes the end-user (gestor) workflow without redesigning the application or changing the existing metadata-driven capture configuration.

- Project administrators see only participations in their assigned projects in the Gestor workflow, individual-file review, export tools, and the entity catalog; SuperAdmin project scope remains global.
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
2. A directly assigned person appears in the correct project; a project Admin does not see that person's participation in another project they do not administer. Confirm this restriction in the Gestor view, “Revisión de Expedientes Individuales,” “Herramientas de Exportación,” and the entity catalog. Confirm “Tablero de Avance Documental” still shows all projects.
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
- Items 10 and 11 remain pending for the user's final validation.

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
- Generated packages use unique storage paths instead of overwriting the current package before the database commit. The previous generated/signed objects are removed only after the new metadata commits successfully.
- Signed-package uploads use unique paths, preserve the generated-package reference, and remove the previous signed object only after the new metadata commits.
- Replacing a signed package invalidates the session-cached download bytes so the UI cannot offer a previously cached version as the current file.
- Failed database persistence triggers cleanup of the newly uploaded generated/signed object. Cleanup failures are surfaced as warnings rather than hiding the primary failure.
- Regression tests cover upload failure, persistence failure, cleanup failure, and the success path for the shared upload/persist helper.

### Still to verify

- GitHub Actions passed for persistence hardening and initial atomic template processing. Follow-up path-separation changes and their regression test are awaiting CI confirmation.
- Manual cloud smoke test remains advisable: upload evidence; generate a package twice; upload a signed package twice; reload the session and confirm the current paths/statuses and downloads. Do not test destructive cases against production data.
- Storage cleanup is best-effort: if Supabase removal fails, the application warns and can leave an orphaned object for later cleanup.
