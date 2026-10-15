# Assessment review workflow foundation

13 October 2026, Asia/Calcutta. **Data/model foundation only: review actions remain
blocked.** Doctor grants, prediction records and an authorized review/release policy
do not exist. No review endpoint or CLI action was registered. No assessment was
approved in the application; no prediction or recommendation was generated.
V17 remains NOT READY and loading disabled; watchdog Step 1.3 remains deferred
and NOT ACCEPTED.

## Inspection and smallest safe design

Inspected ClinicalAssessment, migrations 0001-0003, JWT/RBAC/ownership helpers,
patient/assessment routes, existing backend tests and phase-2b-readiness.md.
Reused the existing extension, factory, user/assessment models and database setup.
No dependencies changed. Current review authorization cannot safely be inferred
from doctor/admin role or assessment authorship, so the permitted scope is only
the foundation described below.

Added `backend/app/models/review.py::AssessmentReview` and migration
`0004_assessment_reviews`. Each history row stores assessment_id, positive
sequence, actor_user_id, from_state, to_state, database-clock decided_at and optional
reason. Unique (assessment_id, sequence) prevents duplicate positions; FKs are
required and RESTRICT deletion of referenced assessments/actors. A check
constraint restricts transition pairs. No existing assessment or decision is
backfilled; history begins empty. No separate mutable current-state column was
added, avoiding disagreement between an overwritten state and its history.

`ClinicalAssessment.review_history` loads in sequence order.
`ClinicalAssessment.review_state` derives state from the complete history, starts
at pending_review and rejects gaps or previous-state mismatches. It cannot be
assigned directly. New/legacy assessments with no decisions remain pending_review,
including records with null inputs or no prediction. No automatic approval path.
State and history are not added to existing HTTP serializers in this foundation.
Existing response contracts and owner-only access stay intact.

Reserved graph, validated by `validate_review_transition` and database pair checks:

| From | To | Intended future meaning |
| --- | --- | --- |
| pending_review | returned_for_changes | Authorized reviewer requests changes |
| returned_for_changes | pending_review | Explicit future resubmission; no resubmission API exists now |
| pending_review | approved | Reserved authorized decision; terminal in this foundation |

Self-transitions, unknown decisions and transitions out of approved are invalid.
This graph is not an authorization policy or approval of missing model results.
Before enabling approved, define exactly what is reviewed, required evidence,
prediction linkage if applicable and release policy. A historical approved row
does not mean an absent prediction has been generated/approved.

## Blocked writes and history protection

`protect_review_history`, registered on SQLAlchemy before_flush, rejects every new
AssessmentReview with ReviewWriteBlocked. There is no caller-supplied authorization
flag, role bypass or configuration switch. Existing-row edits/deletes and relation
detachment raise ReviewHistoryImmutable. `block_review_dml` rejects Session-level
INSERT/UPDATE/DELETE statements targeting the review table, covering ordinary
bulk DML as well. The hooks use the official
[SQLAlchemy session event mechanism](https://docs.sqlalchemy.org/en/20/orm/session_events.html).
They do not log actor IDs, reasons, patient inputs, passwords or JWTs.

This is **application-level protection**, not database-wide tamper-proof storage.
Direct connection/raw SQL, privileged DB access and lower-level bulk persistence
paths can bypass these hooks. Tests deliberately use connection-level SQL solely
to seed synthetic historical decisions, never as an authorized review mechanism.
No production history or decision was created. Database constraints enforce
row-level transition/sequence/FK validity, but not contiguous cross-row history,
actor role, grants, concurrent append policy or prediction requirements; state
derivation rejects inconsistent chains. No database trigger/access-role claim.

The existing patient assessment validator rejects caller-supplied review_state,
review_history, decision, actor_user_id and decided_at. Registration still rejects
privileged role injection. Doctors/admins remain denied access to real assessment
routes. Proposed review/approve paths return 404 because they do not exist; this
is not a newly authorized endpoint with a superficial role check.

To implement review actions later: add approved patient-doctor authorization,
define reviewer/resubmitter permissions and evidence requirements, preserve input/
prediction version linkage, introduce atomic sequence/previous-state concurrency
checks and replace the blocked-write gate only within a reviewed authorized
append service. Keep old decisions instead of updating them. These are prerequisites,
not work performed here. PDF, grants, inference and frontend remain out of scope.

## Migration and verification

Migration 0004 creates assessment_reviews only; prior migrations and records remain
unchanged. Downgrade drops the table/history and was exercised only in disposable
SQLite. Apply migrations explicitly through the existing DATABASE_URL mechanism
before using the foundation. Startup never auto-migrates. MySQL creation SQL was
generated in tests; no live MySQL or production migration occurred. MySQL check
enforcement retains the documented MySQL 8.0.16+ requirement.

Exact commands, from the workspace root:

```powershell
.venv/Scripts/python.exe -B -m unittest discover -s tests/backend -p 'test_*.py' -v
.venv/Scripts/python.exe -B -m pip check
.venv/Scripts/python.exe -B -m flask --app backend.app routes
```

Suite used approved temporary-file access for the existing file-database migration
test; all review fixtures are isolated. First run: 91 tests, 60 errors/one failure,
caused by a misplaced session mutation check in the query hook (NameError on
ordinary reads). Moved it to before_flush; next full run passed 91 tests in 17.935 s.
Added two malformed-history regression tests and chain validation, then ran the
complete suite again: **93 tests in 21.897 seconds, OK, exit 0** (77 existing + 16 new).
No initial failure is counted as passing verification.

Coverage: reserved state transitions/invalid values, default pending without
prediction, decision history/order/timestamps/actors, all-role blocked writes,
unregistered review actions, doctor/admin denial, patient payload injection,
mutation/deletion/detachment and Session bulk-DML rejection, invalid constraints/
links, duplicate sequences, restricted parent deletion, legacy migration preservation,
malformed-history rejection and MySQL SQL generation. Existing model/schema
agreement, authentication, health, ownership and assessment tests passed unchanged.

pip check: **exit 0, No broken requirements found**. Route inspection: **exit 0,
same ten existing operations**, no review or prediction endpoint:

```text
POST /api/auth/login
GET  /api/auth/me
POST /api/auth/register
GET  /api/health
POST /api/patients
GET  /api/patients/me
GET  /api/patients/<int:patient_id>
POST /api/patients/<int:patient_id>/assessments
GET  /api/patients/<int:patient_id>/assessments
GET  /api/patients/<int:patient_id>/assessments/<int:assessment_id>
```

## Changed files and limitations

Updated:

- backend/app/models/__init__.py
- README.md
- docs/setup/implementation-checklist.md

Added:

- backend/app/models/review.py
- backend/migrations/versions/0004_assessment_reviews.py
- tests/backend/test_reviews.py
- docs/setup/assessment-review-foundation.md

Final inspection confirmed the state/history hooks and additive migration match
the tested scope. SHA-256 inventory comparison found 56 original files: three
intentional updates listed above, 53 unchanged, four additions listed above and
no removals. V17 model/source/dataset, inference/loading controls, watchdog and
Docker files, prior readiness reports, auth/APIs, dependency manifests and previous
migrations remained byte-identical. Environments, bytecode and frontend caches
were excluded. Both inventory commands exited 0:

```powershell
.venv/Scripts/python.exe -B -c "import hashlib,json,pathlib; roots=['backend','tests','docs','ml','infra','frontend']; paths=[p for root in roots for p in pathlib.Path(root).rglob('*') if p.is_file() and not any(x in p.parts for x in ('node_modules','.venv','__pycache__','.npm-cache'))]+[pathlib.Path(x) for x in ['README.md','.env.example','.gitignore']]; print(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}))"
```

The before/after values were compared directly. No Git repository
exists, so no tracked-file diff or commit is claimed.

Not performed: live MySQL/production migrations, real review decisions,
grant-based review authorization, DB-wide immutability/concurrent authorized append,
prediction approval/persistence, V17 loading/parity/inference, watchdog/Docker,
live HTTP/deployment, frontend/PDF or clean-environment installation. History
timestamps retain existing DB-clock semantics without a new UTC policy. No
production credentials were requested; no dependencies installed. Stop here.
