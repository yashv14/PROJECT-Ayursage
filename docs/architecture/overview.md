# AYUR-SAGE architecture

AI-Based Ayurvedic Treatment and Diet Recommendation System.

Approved flow: React / Vite / JavaScript / Bootstrap -> Flask REST API -> MySQL,
with separate Python V17 inference code within the same Flask application.
No Node/Express backend or unnecessary microservices. The backend now provides
the Flask foundation and one Flask-SQLAlchemy extension, with initial Alembic
migrations for roles, users, patients and clinical assessments. MySQL via PyMySQL
is the target; isolated persistence tests use SQLite with foreign keys enabled.

The application factory is `backend.app.create_app`; routes use the blueprint in
`backend/app/api`, configuration lives in `backend/config`, and JSON error handlers
live in `backend/app/errors.py`. Database setup lives in `backend/app/database`,
models in `backend/app/models`, and Alembic scripts in `backend/migrations`.
Auth helpers live in `backend/app/auth`; services and utils remain reserved.
The root `ml/` folders are reserved for frozen V17 code
called by Flask later; they do not represent a separate deployed service.
JWT authentication supports patient, doctor and admin roles. Files and generated reports will use
cloud object storage. Deployment will use Docker and managed cloud hosting.
Storage and deployment remain unimplemented. Authentication setup and verification
are documented in ../setup/authentication.md.

Role codes are patient, doctor and admin (administrator); each user has one role.
Each patient has one unique required owner user. Each assessment links to a patient
and its recording user, with a database-clock timestamp and optional manual notes.
These links establish persistence relationships only. Authentication resolves the
current user and role from the database; reusable helpers check explicit roles and
patient ownership. Patient APIs now enforce owner scope on every read/write route;
assessment authorship is not an access grant. The ownership helper denies doctor
and administrator overrides; an explicit future policy is required. The user chose
to keep doctor access denied pending grants. Public registration atomically creates
a patient user/profile; privileged users require local CLI provisioning.
Assessments now persist the exact source-named input object in a nullable JSON
column. New API records require all twelve features; legacy records retain null.
No medical ranges, decision rules, output fields or care plans are added. Names
are checked against source without importing it; preprocessing and inference
compatibility remain unverified. See ../setup/patient-assessment-apis.md.
See ../setup/database-foundation.md for configuration and executed verification.

The frontend holds presentation and API client concerns. Flask owns authorization,
validation, patient history, audit records and service orchestration. ML code owns
artifact compatibility checks and frozen inference. Diet logic remains distinct
from V17 outputs and requires verified datasets and clinical rules.

## Frozen contract to verify against source

The 12 declared inputs are Disease, Symptom Severity, Nadi Reading,
Constitution/Prakriti, Stress Levels, Sleep Patterns, Age Group, Physical Activity
Levels, BP Systolic, BP Diastolic, Pulse Rate and Weight (kg). Exact names, types,
encodings, values and preprocessing remain unverified until source inspection.

The four declared outputs are Herbal Therapy Strategy, Lifestyle Recommendations,
Therapeutic Yoga Module and Follow-up Recommendation. Diet is not a fifth output.

Doctor prescriptions, medication/dosage decisions and clinical notes remain manual.
Model suggestions must remain separate from doctor-approved care plans. No clinical
efficacy or performance claims are established. No training runs in the application.

## Future security requirements

Authentication, role-based authorization, audit logging, protected patient records,
authorized report access and environment-based secrets are required in later phases.
Historical records remain separate from the 12 current inference inputs. Azure
deployment requires local integration evidence and an explicit cost/eligibility review.
