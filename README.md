```markdown
# TrueTestAuth

TrueTestAuth is a Streamlit-based assessment platform that combines **behavioral keystroke authentication**, **continuous identity verification**, **proctored exams**, and an **auto-graded C++ coding-lab environment** for faculty and students.

The application provides separate faculty and student workflows, stores application data in local JSON files, uses a TensorFlow/Keras LSTM model for behavioral authentication, and supports multiple C++ execution backends.

---

## Project Overview

TrueTestAuth is designed around a simple assessment workflow:

- Faculty create exams and coding labs.
- Students access assessments through their enrolled courses.
- Student identity is verified using typing behavior.
- Exams continuously monitor keystroke dynamics during the session.
- Copy/paste-related actions are blocked and logged in supported assessment fields.
- C++ lab submissions are compiled, executed, tested, scored, and stored.
- Faculty can review submissions, behavioral-authentication timelines, integrity information, and academic history.

The current repository is implemented as a **single Streamlit application with supporting Python modules, a custom frontend component, local JSON persistence, and a bundled LSTM model**.

---

## Problem Statement

Password-based login only verifies possession of credentials at one point in time. For online assessments, the application also needs a way to monitor whether the student's interaction remains consistent throughout an assessment.

TrueTestAuth addresses this by using:

1. Password-based account authentication.
2. Keystroke-dynamics-based behavioral verification.
3. Periodic behavioral checks during exams and coding labs.
4. Clipboard-event logging and client-side clipboard restrictions.
5. Integrated C++ compilation and hidden-test grading.

---

## Key Features

### Role-Based Access

The application supports two roles:

- **Faculty**
  - Dashboard overview
  - Exam creation and management
  - Coding-lab creation and management
  - Exam and lab submission review
  - Behavioral-authentication reports
  - Course settings and enrolled-student view

- **Student**
  - Course dashboard
  - Course-specific exams and labs
  - Behavioral login verification
  - Exam identity-verification gate
  - Timed exam portal
  - Continuous behavioral authentication
  - C++ coding workspace
  - Submission history
  - Exam submission and integrity summary

### Behavioral Authentication

The application extracts a 13-dimensional keystroke feature vector:

1. `mean_dwell`
2. `std_dwell`
3. `median_dwell`
4. `max_dwell`
5. `mean_flight`
6. `std_flight`
7. `median_flight`
8. `min_flight`
9. `typing_speed_wpm`
10. `dwell_flight_ratio`
11. `rhythm_consistency`
12. `total_time_ms`
13. `n_keys`

These features are used by the TensorFlow/Keras behavioral-authentication model.

### Continuous Verification

During exams and coding labs, the frontend collects recent keystroke events and sends feature vectors for periodic authentication checks.

The implemented thresholds are:

| Confidence | Status |
|---|---|
| `>= 0.65` | Verified |
| `0.45 - < 0.65` | Warning |
| `< 0.45` | Flagged |

Exam sessions also maintain a consecutive-failure counter.

### Copy/Paste Protection

In the custom frontend:

- Paste is prevented.
- Copy is prevented.
- Cut is prevented.
- Context-menu usage is prevented.
- Drag-and-drop is prevented.
- Paste attempts are logged with the affected question/problem and character count.

These restrictions are attached to exam answer textareas and the coding-lab code/stdin editors.

### Proctored Exams

Faculty can create exams with:

- Exam title
- Subject/course
- Instructions
- Date
- Start time
- Duration
- Descriptive questions
- MCQs with four options
- Marks per question

Student exams provide:

- Countdown timer
- Question navigator
- Answer persistence during reruns
- Continuous authentication
- Recent authentication readings
- Manual submission
- Automatic submission when the timer expires

MCQs are automatically graded. Descriptive questions are stored for review.

### Coding Labs

Faculty can create multi-problem C++ labs with:

- Problem title
- Difficulty
- Markdown-compatible statement
- Time limit
- Memory limit
- Visible sample input/output
- Hidden test cases
- Points per hidden test
- Starter code

Students receive a browser-based C++ editor with:

- C++17 indicator
- Line numbers
- Run button
- Submit button
- Reset button
- Custom stdin
- Compilation/test results
- Previous-attempt history
- Continuous behavioral authentication

### PDF Question-Paper Text Extraction

Faculty can upload a PDF question paper. `pdfplumber` is used to extract plain text from the PDF, which can then be reviewed in the UI and used as the initial text for the first exam question.

### Faculty Reports

The reports section provides:

- Average authentication confidence
- Minimum confidence
- Total authentication checks
- Flag count
- Authentication timeline chart
- Per-exam summary
- Academic history
- CSV report download

---

## Technology Stack

### Backend / Application

- Python
- Streamlit
- Pandas
- NumPy
- TensorFlow / Keras
- Requests
- python-dotenv
- pdfplumber

### Machine Learning

- TensorFlow / Keras
- LSTM neural network
- Manual z-score feature normalization

### Code Execution

- Local `g++` / `clang++`
- Piston API
- Judge0 API

### Frontend

- HTML
- CSS
- JavaScript
- Streamlit custom component protocol

### Persistence

- JSON files under `data/`

---

## System Architecture

TrueTestAuth follows this architecture:

~~~mermaid
flowchart TD
    U[User Browser] --> S[Streamlit Application<br/>app.py]

    S --> AUTH[Authentication & Session Management]
    S --> DM[DataManager<br/>data_manager.py]
    S --> ML[BehavioralAuthModel<br/>ml_model.py]
    S --> CC[CppCompiler<br/>compiler.py]
    S --> UI[Custom Streamlit UI]

    UI --> FE[frontend/index.html]
    FE --> KS[Keystroke Capture]
    FE --> CP[Clipboard / Interaction Controls]

    KS --> FEVENTS[Behavioral Feature Payloads]
    FEVENTS --> S

    AUTH --> USERS[(data/users.json)]
    DM --> DATA[(Local JSON Storage)]

    ML --> MODEL[(models/behavioral_auth_model_lstm/)]
    ML --> SCORE[Behavioral Confidence]

    CC --> LOCAL[g++ / clang++]
    CC --> PISTON[Piston API]
    CC --> JUDGE0[Judge0 API]

    LOCAL --> RESULT[Compile / Run Result]
    PISTON --> RESULT
    JUDGE0 --> RESULT

    RESULT --> LABS[data/lab_submissions.json]
    SCORE --> LOGS[data/auth_logs.json]
    CP --> CPLOG[data/cp_logs.json]

    FAC[Faculty Workflow] --> S
    STU[Student Workflow] --> S
~~~

---

## Project Structure

~~~text
TrueTestAuth/
├── .devcontainer/
│   └── devcontainer.json
├── .streamlit/
│   └── config.toml
├── frontend/
│   └── index.html
├── models/
│   └── behavioral_auth_model_lstm/
│       ├── lstm_model.keras
│       └── metadata.json
├── data/
│   ├── users.json
│   ├── exams.json
│   ├── labs.json
│   └── enrollments.json
├── app.py
├── compiler.py
├── data_manager.py
├── ml_model.py
├── seed_demo.py
├── ui_components.py
├── requirements.txt
├── packages.txt
├── .env.example
├── .gitignore
└── README.md
~~~

The application can also create the following JSON files at runtime:

~~~text
data/
├── submissions.json
├── lab_submissions.json
├── auth_logs.json
└── cp_logs.json
~~~

---

## How the Project Works

### 1. Faculty Registration / Login

Faculty can create an account with:

- Full name
- Username
- Password
- Course name

Faculty login authenticates using username, password, and role.

After login, the faculty member is routed to the overview dashboard.

---

### 2. Student Registration

Student registration is implemented as a three-step process.

#### Step 1 — Account Details

The student provides:

- Full name
- Username
- Enrollment number
- Password
- Faculty/course selection

#### Step 2 — Behavioral Enrollment

The student types:

~~~text
the quick brown fox jumps
~~~

The phrase is entered repeatedly. The implementation targets **10 behavioral samples**.

Each sample is converted into the 13-feature vector listed above.

#### Step 3 — Registration Completion

The application:

1. Creates the student account.
2. Saves the collected keystroke samples.
3. Enrolls the student in the selected faculty course.
4. Attempts to retrain the behavioral-authentication model.

---

## Student Login Flow

Student login has an additional behavioral verification stage.

~~~text
Username + Password
        ↓
Credential Validation
        ↓
Behavioral Phrase Verification
        ↓
LSTM Prediction
        ↓
Confidence >= 0.45 ?
     ↙        ↘
   Yes         No
    ↓           ↓
Student Login  Retry
                ↓
          3 failed attempts
                ↓
              Block
~~~

If the behavioral model is not trained, the code allows the student to proceed without behavioral verification.

---

## Exam Workflow

The student:

1. Opens an enrolled course.
2. Selects an available exam.
3. Starts a new exam session.
4. Receives an exam session ID.
5. Enters the identity-verification gate.
6. Types the behavioral phrase.
7. Must achieve at least `0.45` confidence.
8. Enters the timed exam.
9. Answers MCQs and/or descriptive questions.
10. Is continuously monitored through typing behavior.
11. Can submit manually.
12. Is automatically submitted when the timer expires.
13. Receives a submission/integrity summary.

During an exam, continuous checks are scheduled every **30 seconds**. A check only produces an authentication event when enough recent keystrokes have been collected.

---

## Dataset & Preprocessing

The repository does not contain a conventional external behavioral-authentication dataset.

Instead, `seed_demo.py` generates synthetic keystroke-feature samples from predefined typing profiles.

The bundled demo configuration creates:

- 3 student profiles
- 15 samples per student
- 45 total behavioral training samples

The synthetic profiles differ primarily in dwell-time and flight-time distributions.

These samples are used to train the initial LSTM model.

---

## Model / Algorithm Details

### Feature Extraction

`ml_model.py` computes:

- Mean dwell time
- Standard deviation of dwell time
- Median dwell time
- Maximum dwell time
- Mean flight time
- Standard deviation of flight time
- Median flight time
- Minimum flight time
- Typing speed in WPM
- Dwell/flight ratio
- Rhythm consistency
- Total typing time
- Number of keys

The same feature logic is implemented in the JavaScript frontend so that captured browser data matches the Python model's expected feature order.

### Normalization

During training:

~~~text
X_scaled = (X - mean) / (std + 1e-8)
~~~

The calculated means and standard deviations are stored in `metadata.json`.

### Model Architecture

~~~text
Input
  Shape: (13, 1)
      ↓
LSTM
  64 units
  return_sequences=True
      ↓
Dropout
  0.30
      ↓
LSTM
  32 units
      ↓
Dropout
  0.30
      ↓
Dense
  32 units
  ReLU
      ↓
Dropout
  0.15
      ↓
Dense
  N classes
  Softmax
~~~

### Training Configuration

| Parameter | Value |
|---|---:|
| LSTM units | 64 |
| Second LSTM units | 32 |
| Dense units | 32 |
| Dropout | 0.30 |
| Final dropout | 0.15 |
| Epochs | 80 |
| Batch size | 16 |
| Optimizer | Adam |
| Learning rate | `1e-3` |
| Loss | `sparse_categorical_crossentropy` |
| Validation split | 15% when at least 10 samples are available |

The model requires at least two distinct users before training.

### Authentication Thresholds

The model returns the probability associated with the authenticated user's class.

The implemented decision threshold for acceptance is:

~~~text
confidence >= 0.45
~~~

Continuous monitoring additionally uses:

- `>= 0.65` → Verified
- `0.45 - < 0.65` → Warning
- `< 0.45` → Flagged

---

## Current Behavioral Model Artifact

The uploaded project contains:

~~~text
models/behavioral_auth_model_lstm/
├── lstm_model.keras
└── metadata.json
~~~

The bundled metadata contains three behavioral classes:

~~~text
alice_cs
bob_cs
charlie
~~~

The repository does not contain a separate benchmark/evaluation dataset or persisted test metrics, so no independent accuracy, precision, recall, ROC-AUC, or similar performance claims are made here.

---

## Coding Lab Workflow

A student opens a coding lab and selects one of its problems.

### Run

The **Run** action:

1. Sends the current code and custom stdin to Streamlit.
2. Calls `CppCompiler.compile_and_run()`.
3. Executes the code using the configured compiler backend.
4. Returns stdout, stderr, compile errors, exit code, engine, timing, and success state.

The Run operation uses the supplied/sample input only.

### Submit

The **Submit** action:

1. Sends the code to Streamlit.
2. Loads the selected problem's hidden test cases.
3. Runs the program once for each test case.
4. Compares normalized program output with expected output.
5. Awards points for passing tests.
6. Stores the complete submission record.
7. Shows per-test results.

---

## C++ Compilation Backends

`compiler.py` supports three execution engines.

### Local Compiler

The local backend searches for:

~~~text
g++
~~~

or:

~~~text
clang++
~~~

It compiles with:

~~~text
-std=c++17
-O2
-pipe
~~~

and removes temporary source and executable files afterward.

### Piston

The project integrates with:

~~~text
https://emkc.org/api/v2/piston/execute
~~~

with:

~~~text
language = cpp
version = 10.2.0
~~~

### Judge0

The project integrates with:

~~~text
https://judge0-ce.p.rapidapi.com/submissions
~~~

with language ID:

~~~text
54
~~~

Judge0 requires:

~~~text
JUDGE0_API_KEY
~~~

---

## Actual Runtime Engine Order

The generic `CppCompiler` supports a configurable order.

However, the Streamlit application explicitly creates:

~~~python
CppCompiler(prefer_local=True)
~~~

Therefore, the application attempts engines in this order:

~~~text
1. Local g++ / clang++
2. Piston
3. Judge0
~~~

Judge0 is skipped when `JUDGE0_API_KEY` is unavailable.

---

## API Documentation

TrueTestAuth does **not** expose a public REST API.

The application is built as a Streamlit application, and the custom browser component communicates with Streamlit through the Streamlit component protocol.

### External APIs

| Service | Method | Purpose |
|---|---|---|
| Piston | `POST /api/v2/piston/execute` | Remote C++ compilation/execution |
| Judge0 | `POST /submissions` | Submit C++ execution job |
| Judge0 | `GET /submissions/{token}` | Poll Judge0 execution result |

The frontend also sends internal application events such as:

~~~text
enrollment_sample
verify_phrase
exam_continuous_check
exam_cp_event
exam_answer
lab_run
lab_submit
lab_continuous_check
lab_paste
~~~

These are internal application events, not public HTTP endpoints.

---

## Data Storage

TrueTestAuth uses local JSON persistence instead of a relational or NoSQL database.

### User Data

`data/users.json`

Stores:

- Username
- SHA-256 password hash
- Full name
- Role
- Course information
- Enrollment number
- Creation timestamp
- Behavioral samples
- Enrollment state

### Course Enrollment

`data/enrollments.json`

Stores student/faculty course relationships.

### Exams

`data/exams.json`

Stores:

- Exam metadata
- Questions
- Question type
- Options
- Correct MCQ answer
- Marks
- Status
- Timing

### Labs

`data/labs.json`

Stores:

- Lab metadata
- Problems
- Difficulty
- Statements
- Time limits
- Memory limits
- Sample tests
- Hidden tests
- Starter code
- Total points

### Runtime Records

The application creates:

~~~text
data/submissions.json
data/lab_submissions.json
data/auth_logs.json
data/cp_logs.json
~~~

These store exam submissions, coding-lab submissions, authentication events, and clipboard events.

---

## Installation & Setup

### Prerequisites

The repository's development container is configured around **Python 3.11**.

For local execution, install:

- Python
- A C++17 compiler such as `g++` or `clang++`

A local C++ compiler is not strictly required if a configured remote execution backend is available.

### Clone the Repository

~~~bash
git clone https://github.com/erharsh2104/TrueTestAuth.git
cd TrueTestAuth
~~~

### Create a Virtual Environment

#### Windows

~~~powershell
python -m venv .venv
.venv\Scripts\activate
~~~

#### Linux / macOS

~~~bash
python3 -m venv .venv
source .venv/bin/activate
~~~

### Install Dependencies

~~~bash
pip install -r requirements.txt
~~~

---

## Environment Variables

Create a `.env` file based on `.env.example` when Judge0 integration is required.

~~~text
JUDGE0_API_KEY=your_judge0_api_key
~~~

The application uses `python-dotenv` to load environment variables.

Do not commit `.env` files or API credentials to Git.

---

## Initialize Demo Data

The project provides:

~~~bash
python seed_demo.py
~~~

The script:

1. Creates demo faculty/student accounts when required.
2. Generates synthetic behavioral samples.
3. Enrolls students in the demo course.
4. Trains the behavioral-authentication LSTM.
5. Saves the trained model.
6. Creates the demo exam.
7. Creates the demo coding lab.

The script can be rerun to rebuild the demo model/data.

---

## How to Run

Start the application with:

~~~bash
streamlit run app.py
~~~

The Streamlit configuration uses port:

~~~text
8501
~~~

The application is normally available at:

~~~text
http://localhost:8501
~~~

---

## Usage

### Faculty

1. Register or log in as faculty.
2. Open the faculty dashboard.
3. Create/manage exams.
4. Create/manage coding labs.
5. Review student submissions.
6. Inspect behavioral-authentication reports.
7. Review course and student information.

### Student

1. Register using a faculty/course.
2. Complete behavioral enrollment.
3. Log in using username/password.
4. Complete behavioral verification.
5. Open an available exam or coding lab.
6. Complete the assessment.
7. Submit the assessment.
8. Review the resulting submission/integrity information.

---

## Demo Data

The uploaded project contains demo data for:

### Faculty

~~~text
prof_sharma
~~~

### Students

~~~text
alice_cs
bob_cs
charlie
~~~

The project also contains:

- 1 demo course enrollment setup
- 1 demo exam
- 1 demo coding lab
- 3 coding problems
- A trained behavioral-authentication model

Credentials are intentionally not documented in this README.

---

## Demo Coding Lab

The seeded demo lab contains:

| Problem | Difficulty |
|---|---|
| Hello, World! | Easy |
| Sum of N Numbers | Medium |
| Palindrome Check | Hard |

The lab includes hidden test cases and point allocations for automated evaluation.

---

## Integrity Score

The completed-exam integrity score is calculated using:

1. Average behavioral confidence.
2. Number of paste events.

### Behavioral Score

~~~text
behavioral_score = average_confidence × 100
~~~

### Paste Penalty

~~~text
0 paste events  → 100
1 paste event   → 80
2 paste events  → 55
3+ paste events → 20
~~~

### Final Score

~~~text
integrity_score =
    behavioral_score × 0.60
    + paste_penalty × 0.40
~~~

### Classification

| Integrity Score | Classification |
|---|---|
| `>= 70` | High |
| `40 - < 70` | Suspicious |
| `< 40` | Flagged |

These classifications are application-defined labels.

---

## Faculty Reports

The faculty reporting workflow can display:

- Average authentication confidence
- Minimum authentication confidence
- Number of authentication checks
- Number of flags
- Authentication timeline
- Exam-level summary
- Academic history
- CSV report download

---

## Streamlit Configuration

`.streamlit/config.toml` configures:

~~~text
Theme: dark
Headless mode: true
Port: 8501
Browser usage statistics: disabled
~~~

---

## Development Container

The repository includes:

~~~text
.devcontainer/devcontainer.json
~~~

The configuration uses a Python 3.11 development image and installs system/Python dependencies defined by:

~~~text
packages.txt
requirements.txt
~~~

`packages.txt` currently includes:

~~~text
g++
~~~

The development container also forwards port `8501`.

---

## Security Considerations

The current implementation is intended for an academic/demo environment and requires additional hardening before production deployment.

### Password Storage

Passwords are hashed using SHA-256.

The implementation does not use a salted password hashing algorithm such as:

- Argon2
- bcrypt
- scrypt

### Local JSON Persistence

Application data is stored in JSON files.

This provides simple persistence but does not provide the concurrency control, transaction guarantees, role-based database permissions, or auditing capabilities expected from a production database.

### Client-Side Restrictions

Copy/paste and interaction restrictions are implemented in JavaScript.

Because these controls execute on the client side, they should not be treated as a complete anti-cheating or security boundary.

### C++ Code Execution

The local execution backend uses subprocess execution for submitted C++ programs.

A production deployment should isolate untrusted code inside a hardened sandbox with:

- CPU limits
- Memory limits
- Filesystem restrictions
- Network restrictions
- Process isolation
- Execution timeouts

---

## Limitations

The current implementation has several limitations:

- Demo behavioral-authentication training data is synthetic.
- No real-world behavioral-keystroke dataset is bundled.
- No separate benchmark/test dataset is included.
- No persisted model evaluation metrics are included.
- The authentication model is a multi-class LSTM classifier.
- Password hashing uses SHA-256 without salting.
- Persistence uses local JSON files.
- No public REST API is implemented.
- Client-side clipboard protection is not a complete security mechanism.
- Local C++ execution is not implemented as a production-grade sandbox.
- The configured memory limit is part of the lab problem definition but is not enforced as an operating-system-level memory restriction by the local compiler backend.
- No automated unit/integration test suite is included.
- `.gitignore` excludes runtime data/model assets, so a fresh clone should use `seed_demo.py` to regenerate the demo environment.

---

## Future Improvements

Potential improvements include:

- Replace JSON persistence with PostgreSQL/MySQL or another production database.
- Use Argon2, bcrypt, or scrypt for password hashing.
- Implement secure sandboxed C++ execution.
- Enforce CPU, RAM, filesystem, and network restrictions.
- Use a real keystroke-dynamics dataset.
- Add independent training/validation/test splits.
- Add formal model evaluation and calibration.
- Improve behavioral verification using a dedicated verification architecture.
- Add automated unit and integration testing.
- Introduce stronger session management and authorization.
- Move configuration fully into environment variables.
- Add a dedicated backend API layer if external clients are required.

---

## Results / Screenshots

The uploaded project does not contain a dedicated screenshots folder or benchmark-results report.

The repository does contain the trained model:

~~~text
models/behavioral_auth_model_lstm/lstm_model.keras
~~~

The training code reports training/validation accuracy while training, but these values are not persisted as a formal evaluation report.

Therefore, this README does not claim a specific model accuracy or other benchmark metric.

---

## License

No `LICENSE` file or explicit software license is present in the uploaded project.

Therefore, the repository should currently be considered **unlicensed unless a license is added by the project owner**.

---

## Contributors

The repository Git history identifies:

- **Harsh Tripathi**

Additional contribution history can be viewed through the Git commit history.

---

## Important Files

| File | Purpose |
|---|---|
| `app.py` | Main Streamlit application and workflow router |
| `compiler.py` | C++ compilation, execution, fallback engines, and grading |
| `data_manager.py` | JSON persistence and data operations |
| `ml_model.py` | Behavioral feature extraction and LSTM authentication |
| `seed_demo.py` | Demo data, model training, exam, and lab initialization |
| `ui_components.py` | Reusable UI components |
| `frontend/index.html` | Browser typing capture and assessment interface |
| `requirements.txt` | Python package dependencies |
| `packages.txt` | System dependency list |
| `.env.example` | Environment-variable template |
| `.streamlit/config.toml` | Streamlit configuration |

---

## End-to-End Workflow

~~~text
                    ┌──────────────────────┐
                    │      User Browser    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │     Streamlit App    │
                    │        app.py         │
                    └───────┬───────┬──────┘
                            │       │
             ┌──────────────┘       └───────────────┐
             ▼                                      ▼
   ┌────────────────────┐                 ┌────────────────────┐
   │ Behavioral Auth    │                 │  DataManager       │
   │   ml_model.py      │                 │ data_manager.py    │
   └─────────┬──────────┘                 └─────────┬──────────┘
             │                                      │
             ▼                                      ▼
   ┌────────────────────┐                 ┌────────────────────┐
   │ LSTM Model         │                 │ Local JSON Files   │
   │ .keras + metadata  │                 │ users/exams/labs   │
   └────────────────────┘                 │ submissions/logs   │
                                          └────────────────────┘

             Student Coding Submission
                         │
                         ▼
                ┌──────────────────┐
                │   CppCompiler    │
                │   compiler.py    │
                └────────┬─────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
      Local g++       Piston         Judge0
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                Compile / Run Result
                         │
                         ▼
                Hidden-Test Grading
                         │
                         ▼
                Lab Submission Data
~~~

---

## Project Status

The current codebase provides an academic/demo implementation of a behavioral-authenticated assessment platform with:

- Faculty and student roles
- Behavioral enrollment
- Behavioral login verification
- Continuous behavioral monitoring
- Proctored exams
- MCQ auto-grading
- Descriptive-question storage
- C++ coding labs
- Automated hidden-test grading
- Local JSON persistence
- Faculty reporting
- Clipboard-event logging
- TensorFlow/Keras LSTM authentication
- Local and remote C++ execution backends
- Custom Streamlit frontend components

This README is intentionally based on the implementation present in the project and does not add unsupported technologies, APIs, results, or features.
```
