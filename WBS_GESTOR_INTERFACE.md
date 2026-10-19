# Gestor Interface Closure

**Branch:** `dev`  
**Implementation status:** In progress; automated and local end-to-end verification remain required.

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
5. A writable user can save capture data; unrelated JSON keys and hidden conditional-field values remain intact.
6. Upload an evidence file and verify both the storage object and database row exist. Simulate a storage failure and verify no row is committed.
7. Generate a package, leave the page/session, return, and download the same persisted package.
8. Upload a signed PDF; verify the signed path and status are stored while the generated-package path remains available in metadata.
9. Enter courier delivery details; verify the method, date, carrier, and tracking number persist after rerun.
10. Remove one selected user's access and verify other users' assignments remain.
11. Run the full test suite; check generated Word/Excel/PDF outputs against a known sample.

## UX test findings (2026-10-19)

- **Confirmed defect:** project Admin view can fail with PostgreSQL `could not identify an equality operator for type json` when the entity catalog query applies `DISTINCT` to full `Persona` rows. Fixed on `dev` by using a relationship `EXISTS` filter.
- **Confirmed scope defect:** “Revisión de Expedientes Individuales” and “Herramientas de Exportación” used the global participation list. Fixed on `dev` to use only participations from the Admin's assigned projects. The “Tablero de Avance Documental” remains global.
- **Open UX defect:** after login, the screen intermittently appears blank for any user and recovers after refreshing and logging in again. Cause not yet established; capture the Streamlit terminal output and browser console at the time of occurrence before making a speculative fix.

## Known verification boundary

Unit tests do not prove that Supabase Storage, the configured database, Streamlit reruns, project-specific access, or generated documents work together. Keep the WBS open until the local acceptance checklist is complete.
