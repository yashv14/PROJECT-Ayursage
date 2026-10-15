# Disposable MySQL doctor-access verification

15 October 2026 (Asia/Calcutta). Actual native MySQL and real-browser checks,
not SQL compilation or mocked database acceptance.

## Verified target and isolation

Final accepted run: MySQL Community Server 8.0.46, loopback 127.0.0.1:51632,
schema `ayursage_e2e_46488abcfdf6`, data directory
`C:/Users/yvasa/Videos/PROJECT-Ayursage/.local/mysql-e2e-46488abcfdf6/data`.
The helper generates a new server directory, schema, schema-only account and
password on every run. Credentials are passed through private process pipes/env,
not printed or committed. Existing application DATABASE_URL is never used.

Docker's daemon was unavailable; the already-installed mysqld executable was
used with --no-defaults, --no-monitor, private datadir, loopback binding, ephemeral
port and mysqlx disabled. No installation or existing MySQL service change.
The original Windows monitor caused an exact-PID ownership check to reject;
--no-monitor makes the owned process handle match the server PID file.

Before bootstrap SQL writes, the helper verifies PID, actual data directory and
port. Before migration/application writes, the Flask fixture independently checks
URL driver/host/schema/user/port, ownership-file location, DATABASE(), @@datadir,
@@port, @@server_uuid and zero tables in the new schema. No SQLite fallback exists
in MySQL mode. The fixture explicitly reported dialect=mysql and migration head
0006_receptionist_appointments. All six existing upgrade revisions completed.

Final shutdown receipt `.local/mysql-e2e-46488abcfdf6/stopped.json` records PID
25688, exit_code=0, running=false. The MySQL log records normal shutdown. Data/logs
are retained in ignored task-created directories; no schema/table drops, resets
or deletion of existing data were executed. Failed provisioning/migration attempts
also used fresh separate test directories/schemas and were stopped.

## Reproduced defect and minimal fix

The real MySQL migration initially failed with error 3818. Migration 0006 created
appointment_lock.id as AUTO_INCREMENT while ck_appointment_lock checks id=1.
MySQL prohibits that CHECK/AUTO_INCREMENT combination; SQLite had accepted it.

`tests/backend/test_mysql_compatibility.py` reproduced the offending MySQL DDL
before the fix and failed as expected. The only application/schema-source change
is autoincrement=False on AppointmentLock.id and its matching create-table column
in existing migration 0006. The singleton still seeds ID 1, retains its CHECK and
is used by the same booking lock query. Other entity IDs remain auto-incrementing.
No existing database was migrated or altered; this correction enables fresh MySQL
installations to reach the existing migration head. No unrelated revision/refactor.

## Results actually executed

| Level | Result |
| --- | --- |
| MySQL migrations | All six upgrades passed in the fresh verified schema |
| MySQL-specific assertions | Seven groups passed: ORM relationships, real unique-constraint rollback/session reuse, committed assessments, nullable JSON/notes, 22-record history keyset ordering/pagination, exact expiry boundary, revocation |
| MySQL browser E2E | One scenario, four stages passed; Node reports 5 tests including parent |
| SQLite browser regression | Same scenario and four stages passed, explicitly reported sqlite |
| Backend regression | 91 focused tests passed, including grant/directory/patient/foundation/database/reception and the new MySQL DDL test |
| Frontend unit/state | 49 passed |
| Frontend rendering | 18 passed: doctor-render 5, patient-render 13 |
| Production frontend build | Passed with write:false; dist preserved |

The browser scenario uses real installed Chrome 155.0.8059.40 and existing
playwright-core 1.56.0 at its prior external location. It covers admin-issued grant,
patient My Profile visibility, doctor directory/history/detail and stored fields,
unrelated doctor/patient and unauthorized-role denial, patient UI revocation, a new
doctor GET returning 403, removal of displayed inputs/notes and fresh directory
exclusion. It does not claim instantaneous remote revocation of delivered data.
No V17 execution; the test fixture rejects load/predict calls.

The first 91-test regression attempt hit Windows sandbox permissions in two
temporary-file tests. The same suite outside the sandbox passed all 91. The DDL
regression failed before the fix and passed after it; no final test failure remains.

## Exact reproduction commands

From frontend, using existing mysqld on PATH and the existing external runner:

```powershell
$env:AYURSAGE_E2E_DATABASE = 'mysql'
$env:AYURSAGE_PLAYWRIGHT_MODULE = 'C:\Users\yvasa\Videos\AYURSAGE\.phase9-release\frontend\node_modules\playwright-core\index.mjs'
node --test --test-isolation=none tests/e2e/doctor-access.test.js
$env:AYURSAGE_E2E_DATABASE = 'sqlite'
node --test --test-isolation=none tests/e2e/doctor-access.test.js
node --test --test-isolation=none tests/doctor.test.js tests/patient.test.js tests/foundation.test.js tests/session.test.js tests/assessment-prediction.test.js
node --test --test-isolation=none tests/doctor-render.test.js
node --test --test-isolation=none tests/patient-render.test.js
node --input-type=module -e "import { build } from 'vite'; await build({ build: { write: false } });"
```

From workspace root (all test databases are disposable):

```powershell
@'
import sys, unittest
sys.path.insert(0, 'tests/backend')
import test_access_grants, test_doctor_directory, test_patients, test_foundation, test_database, test_reception, test_mysql_compatibility
classes = (test_access_grants.AccessGrantTests, test_doctor_directory.DoctorDirectoryTests, test_patients.PatientApiTests, test_foundation.FoundationTests, test_database.DatabaseConfigurationTests, test_database.DatabaseModelTests, test_reception.ReceptionTests, test_reception.ReceptionMigrationConcurrencyTests, test_mysql_compatibility.MySQLCompatibilityTests)
suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in classes)
result = unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(not result.wasSuccessful())
'@ | .venv/Scripts/python.exe -B -
```

Windows native server/browser and temporary-file checks required subprocess/file
access outside the sandbox. Reproduction creates a new identity and port, never
reuses the reported schema. An unidentified/nonempty target fails before migrations.

## Limits

This establishes the selected workflow on local MySQL 8.0.46/Windows, not Azure,
production readiness, every MySQL deployment/version, or existing-database upgrades.
MySQL probes use synthetic data and real SQL/Flask handlers; expiry uses controlled
time in the fixture process. The broader 91 backend regressions remain SQLite/DDL
tests, not 91 MySQL tests. MySQL scheduling concurrency, load/performance, cloud TLS
and deployment were not tested. No package/browser installation, real patient data,
frozen ML change, prediction, clinical-write feature or unrelated workflow change.
