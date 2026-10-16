# AYUR-SAGE

AI-Based Ayurvedic Treatment and Diet Recommendation System.

AYUR-SAGE integrates a multi-output Machine Learning pipeline (V17) with a secure Flask REST API and a modern React/Vite web interface. The system assists clinicians and patients by generating tailored Ayurvedic recommendations across four therapeutic dimensions:
1. **Herbal Therapy Strategy**
2. **Lifestyle Recommendations**
3. **Therapeutic Yoga Module**
4. **Follow-up Recommendation**

---

## Architecture Overview

* **Frontend:** React 19, Vite, Bootstrap 5. Serves by default at `http://127.0.0.1:3000` with automated proxying to the Flask API.
* **Backend:** Flask 3.1, Flask-SQLAlchemy, Alembic migrations, PyJWT authentication, and ReportLab PDF generation. Runs on `http://127.0.0.1:5000`.
* **ML Inference:** Direct in-process execution using pre-trained multi-output XGBoost and Scikit-Learn pipelines. No Docker daemon or external container dependencies required.
* **Database:** SQLite for local development (`.local/auth/auth.sqlite3`); MySQL-compatible schema via SQLAlchemy.

---

## Machine Learning Model Artifact

Because the trained model artifact exceeds Git repository size limits, it is excluded via `.gitignore`:
* **Expected location:** `ml/artifacts/ayursage_model.pkl`
* **Expected SHA-256:** `e0b60420eaf618e165822af5f69f8c437794c06ae0ca885e5d68df8e6a9a7c98`

### Setup Instructions for Collaborators
1. Obtain `ayursage_model.pkl` from the project's shared drive or release assets.
2. Place the file into `ml/artifacts/ayursage_model.pkl`.
3. When the backend starts, it automatically verifies the cryptographic SHA-256 checksum and loads the model into memory.

---

## Quickstart Guide

### 1. Backend Setup

Activate your Python 3.12 environment and install dependencies:

```bash
# Activate your environment
source /path/to/venv/bin/activate   # Linux / macOS
# or .venv\Scripts\activate          # Windows

# Install unified backend + ML requirements
pip install -r backend/requirements.txt
```

Start the backend server (runs on `http://127.0.0.1:5000` by default):

```bash
python -m backend.local
```

You should see:
```text
[INFO] AYUR-SAGE V17 ML model loaded successfully.
 * Running on http://127.0.0.1:5000
```

### 2. Frontend Setup

From the project root:

```bash
# Install frontend dependencies
npm install

# Start development server (runs on http://127.0.0.1:3000 by default)
npm run dev
```

Open `http://localhost:3000` in your browser.

---

## Using the Application

1. **Register / Login:** Register as a new patient at `http://localhost:3000/#/auth`.
2. **Create Profile:** Create your patient profile when prompted.
3. **Submit Clinical Assessment:**
   * Enter values for the 12 clinical indicators (Disease, Symptom Severity, Nadi Reading, Constitution/Prakriti, Stress Levels, Sleep Patterns, Age Group, Physical Activity Levels, BP Systolic/Diastolic, Pulse Rate, Weight).
   * Check **"Request a V17 prediction"**.
   * Click **Save and request prediction**.
4. **View Recommendations:** The 4 AI-generated Ayurvedic recommendations will appear immediately below the confirmation.

---

## Running Automated Tests

* **Run Backend & ML Integration Tests (Pytest):**
  ```bash
  python -m pytest tests/
  ```
  *(182 tests passing)*

* **Run Frontend Unit & Contract Tests:**
  ```bash
  npm test
  ```
  *(108 tests passing)*

---

## Project Structure

```text
PROJECT-Ayursage/
├── backend/                  # Flask REST API, database models, migrations & services
│   ├── app/                  # Application factory, blueprints, auth, and error handlers
│   ├── local.py              # Local SQLite development launcher
│   ├── migrations/           # Alembic database migrations
│   └── requirements.txt      # Consolidated backend and ML runtime dependencies
├── frontend/                 # React 19 frontend application
│   ├── src/                  # Components, pages, routing, and API services
│   ├── tests/                # Node test runner test suites
│   ├── package.json          # Frontend packages & scripts
│   └── vite.config.js        # Vite dev server configuration (port 3000 + API proxy)
├── ml/                       # Machine Learning subsystem
│   ├── artifacts/            # Model artifact directory (ayursage_model.pkl)
│   ├── inference/            # Artifact checksum validation & verification
│   └── source/               # V17 training source code
├── package.json              # Root workspace script runner
├── tests/                    # Backend, auth, database, and real model integration tests
└── README.md                 # Project documentation
```
