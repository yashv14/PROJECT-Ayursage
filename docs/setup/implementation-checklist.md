# Phased implementation checklist

- [x] Phase 0: inspect the user-authorized current workspace and report the audit.
- [x] User approved Phase 1 in C:\Users\yvasa\Videos\PROJECT-Ayursage.
- [ ] Phase 1: foundation accepted; see verification.md for actual evidence.
- [x] Phase 2: Flask backend foundation verified locally.
  - [x] Application factory and process-environment configuration.
  - [x] GET /api/health and API blueprint.
  - [x] JSON HTTP errors and generic server-error response.
  - [x] Backend unittest suite; existing pinned runtime dependencies retained.
  - [x] Executed dependency checks and 13 backend tests; results in verification.md.
- [x] Database foundation milestone authorized on 13 October 2026.
  - [x] One shared extension, environment configuration, initial models and Alembic migration.
  - [x] Isolated SQLite migration/constraint tests; 31 backend tests pass including the original 13.
  - [x] Execution evidence and MySQL verification limits in database-foundation.md.
  - [x] Authentication in the subsequent milestone below.
  - [x] Ownership enforcement applied to patient APIs; doctor access remains denied pending explicit grants.
- [x] Authentication/JWT/RBAC milestone authorized on 13 October 2026.
  - [x] Scrypt hashing, patient registration, login and authenticated-user endpoint.
  - [x] Explicit roles, role/ownership helpers and local privileged provisioning.
  - [x] Additive password-hash migration preserving legacy rows without enabling login.
  - [x] 52 backend tests pass; pip check and route inspection pass. See authentication.md.
- [x] Patient Management and Clinical Assessment APIs authorized on 13 October 2026.
  - [x] Create/retrieve own patient profile; create/list/retrieve own assessments.
  - [x] Exact source-named twelve-input payload, structure/type validation and actor linkage.
  - [x] Ownership enforced; user selected denied doctor access until grants exist.
  - [x] Additive JSON input migration; legacy records retain null, never default zeros.
  - [x] 77 backend tests pass; pip check clean; ten route operations registered.
  - [x] Explicit 30-day assessment-read grants implemented under the approved consent/administrator policy; see patient-doctor-access-grants.md. Approved local SQLite backed up/migrated and live HTTP acceptance passed on 14 October; browser/live MySQL remain unverified.
- [x] Assessment review workflow foundation authorized on 13 October 2026.
  - [x] Reserved review states, ordered history, actor/timestamp fields and additive migration.
  - [x] Application review writes blocked; existing history protected against ORM mutations.
  - [x] Default pending state, validated history chain; no prediction or approval inferred.
  - [x] 93 backend tests pass; pip check clean; ten existing route operations retained.
  - [ ] Review action endpoints blocked pending grants and explicit review/prediction policy.
- [ ] Phase 3: inspect and integrate approved V17 artifacts.
- [x] Receptionist role, restricted exact-email lookup, appointments and attendance implemented on 14 October; migration 0006 applied after verified local backup; see receptionist-module.md.
  - [x] 123 backend / 39 frontend tests, build, pip check and live local SQLite/HTTP acceptance passed; clinical/grant restrictions retained.
  - [ ] Invitations isolated pending secure email delivery configuration; full receptionist module and browser acceptance remain incomplete.
  - [x] Step 1: isolated checksum utility and disabled-loading scaffold; 10 non-loading tests passed.
  - [ ] Review scaffold/dependency plan/restricted execution before installation or loading.
  - [ ] Resolve runtime evidence and approved references; no model loading or inference performed.
- [ ] Phase 4: verified clinical engines and separate diet module.
- [ ] Phase 5: versioned Flask REST API.
- [ ] Phase 6: React doctor interface.
- [ ] Phase 7: doctor review and approval workflow.
- [ ] Phase 8: authorized reports and file storage.
- [ ] Phase 9: integration and end-to-end testing.
- [ ] Phase 10: Azure cost/eligibility checks and deployment.
- [ ] Phase 11: final documentation and verification.

The user authorized Phase 2 on 12 October 2026, then the small database foundation
milestone, authentication/JWT/RBAC and patient/assessment APIs on 13 October 2026.
Doctor assessment-read grants were subsequently authorized and implemented; see
patient-doctor-access-grants.md. Review actions and further integrations remain deferred.
Future phases retain their existing labels and are not begun here.
Phase 1's unresolved container acceptance is retained in verification.md.
The user authorized only Phase 3 Step 1 on 12 October 2026. Stop after this tested
scaffold; obtain approval before installing audit packages or deserializing models.
Never mark container reopening, model compatibility or tests as passed without evidence.
