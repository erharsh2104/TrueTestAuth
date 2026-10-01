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

The application follows this overall architecture:

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

## High-Level Architecture

### `app.py`

Main Streamlit application and router.

Responsibilities include:

- Page configuration
- Session state
- Login and registration
- Faculty dashboard
- Student dashboard
- Exam workflow
- Coding-lab workflow
- Behavioral-authentication event handling
- Submission handling
- Navigation
- Integration with the custom frontend component

### `data_manager.py`

JSON-backed persistence layer.

It manages:

- Users
- Keystroke samples
- Faculty/student enrollments
- Exams
- Exam submissions
- Labs
- Lab submissions
- Behavioral-authentication logs
- Copy/paste logs
- Integrity calculations
- Academic history

### `ml_model.py`

Implements the behavioral-authentication model.

Responsibilities include:

- Keystroke feature extraction
- Feature normalization
- LSTM construction
- Model training
- Behavioral prediction
- Model persistence
- Model loading

### `compiler.py`

Provides the C++ compilation/execution abstraction.

It normalizes results from different engines into one `CompileResult` format and provides hidden-test grading through `grade_submission()`.

### `seed_demo.py`

Creates the bundled demo environment:

- One faculty user
- Three student users
- Synthetic behavioral samples
- Course enrollments
- One demo exam
- One demo coding lab
- Initial LSTM model

### `frontend/index.html`

Custom Streamlit component responsible for:

- Typing-event capture
- Behavioral feature extraction
- Exam answer UI
- Coding editor UI
- Continuous-authentication scheduling
- Clipboard restrictions
- Sending component events back to Streamlit

### `ui_components.py`

Contains reusable UI/layout helpers for the application's visual interface, navigation, cards, metrics, badges, and exam layout.

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

These files are referenced by `data_manager.py` but are not present in the uploaded project snapshot because there are no submissions/logs stored yet.

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

The phrase must be entered repeatedly. The implementation targets **10 behavioral samples**.

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

The flow is:

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

## Behavioral Authentication

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

The model is a Keras `Sequential` network:

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

Implemented values:

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

### Authentication Threshold

The model returns the probability associated with the authenticated user's class.

The implemented decision threshold is:

~~~text
confidence >= 0.45
~~~

---

## Current Behavioral Model Artifact

The uploaded project contains a trained model under:

~~~text
models/behavioral_auth_model_lstm/
├── lstm_model.keras
└── metadata.json
~~~

The bundled metadata currently contains three behavioral classes:

~~~text
alice_cs
bob_cs
charlie
~~~

The repository does not contain a separate benchmark/evaluation dataset or persisted test metrics, so no independent accuracy, precision, recall, ROC-AUC, or similar performance claims are made here.

---

## Behavioral Training Data

There is no conventional external dataset in the repository.

The demo seeding script generates synthetic keystroke-feature samples from predefined typing profiles.

The current demo configuration creates:

- 3 student profiles
- 15 samples per student
- 45 total behavioral training samples

The synthetic profiles differ primarily in dwell-time and flight-time distributions.

This data is used by `seed_demo.py` to train the initial LSTM model.

---

## Integrity Score

For completed exams, the application calculates an integrity score from:

1. Average behavioral confidence.
2. Number of paste events.

The implementation uses:

~~~text
behavioral_score = average_confidence × 100

paste_penalty:
0 paste events  → 100
1 paste event   → 80
2 paste events  → 55
3+ paste events → 20

integrity_score =
    behavioral_score × 0.60
    + paste_penalty × 0.40
~~~

The resulting classification is:

| Integrity Score | Grade |
|---|---|
| `>= 70` | High |
| `40 - < 70` | Suspicious |
| `< 40` | Flagged |

These grades are implementation labels used by the application.

---

## Coding-Lab Workflow

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

`compiler.py` supports three execution engines:

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

and removes its temporary source and executable files afterward.

### Piston

The project uses:

~~~text
https://emkc.org/api/v2/piston/execute
~~~

with:

~~~text
language = cpp
version = 10.2.0
~~~

### Judge0

The project uses Judge0 through RapidAPI:

~~~text
https://judge0-ce.p.rapidapi.com/submissions
~~~

with language ID:

~~~text
54
~~~

which corresponds to C++17 in the implementation.

Judge0 requires the environment variable:

~~~text
JUDGE0_API_KEY
~~~

---

## Actual Runtime Engine Order

The generic `CppCompiler` class supports a configurable order.

However, the running Streamlit application explicitly creates:

~~~python
CppCompiler(prefer_local=True)
~~~

Therefore, **the application attempts engines in this order**:

~~~text
1. Local g++ / clang++
2. Piston
3. Judge0
~~~

Judge0 is skipped when `JUDGE0_API_KEY` is not available.

---

## API Documentation

TrueTestAuth does **not** define a public REST API.

The application itself is a Streamlit application. Communication between the custom browser component and Streamlit uses the Streamlit component protocol and browser-side event handling.

The project does integrate with two external code-execution services:

| Service | Method | Purpose |
|---|---|---|
| Piston | `POST /api/v2/piston/execute` | Remote C++ compilation/execution |
| Judge0 | `POST /submissions` | Submit C++ execution job |
| Judge0 | `GET /submissions/{token}` | Poll Judge0 execution result |

The browser component also sends structured events such as:

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

These are internal application events, not public HTTP API endpoints.

---

## Data Storage

TrueTestAuth uses local JSON persistence rather than a relational or NoSQL database.

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

The following files are created as assessments are used:

~~~text
data/submissions.json
data/lab_submissions.json
data/auth_logs.json
data/cp_logs.json
~~~

They store exam submissions, lab submissions, authentication events, and clipboard events respectively.

---

## Installation

### Prerequisites

The repository's development container is configured around **Python 3.11**.

For local execution, install:

- Python
- A C++17 compiler (`g++` or `clang++`) for local code execution

A local C++ compiler is not strictly required when an available remote compilation backend can execute the code.

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

### Install Python Dependencies

~~~bash
pip install -r requirements.txt
~~~

---

## Environment Variables

Create a `.env` file from `.env.example` when Judge0 integration is required.

~~~text
JUDGE0_API_KEY=your_judge0_api_key
~~~

The application loads environment variables through `python-dotenv`.

No API key or other secret is included in the repository documentation.

> Note: `.env.example` also contains a commented model-path example, but the current application uses the model path defined directly in `app.py` rather than reading `MODEL_PATH` from the environment.

---

## Initialize Demo Data

The project provides a complete demo seeding script:

~~~bash
python seed_demo.py
~~~

The script:

1. Creates the demo faculty account if necessary.
2. Creates the demo student accounts if necessary.
3. Generates synthetic behavioral samples.
4. Enrolls students in the demo course.
5. Trains the behavioral-authentication LSTM.
6. Saves the model.
7. Creates the demo exam.
8. Creates the demo coding lab.

The script is safe to rerun with respect to existing demo users/exam/lab definitions, while the behavioral model is retrained.

---

## Run the Application

Start Streamlit with:

~~~bash
streamlit run app.py
~~~

The Streamlit configuration specifies port:

~~~text
8501
~~~

The application can then be opened at the local Streamlit URL, normally:

~~~text
http://localhost:8501
~~~

---

## Demo Data Included in This Project Snapshot

The uploaded project currently contains:

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

- 1 demo course enrollment set
- 1 demo exam
- 1 demo coding lab
- 3 lab problems
- A trained behavioral-authentication model

Credentials are intentionally not documented here.

---

## Demo Lab

The seeded demo lab contains three C++ problems:

1. **Hello, World!** — Easy
2. **Sum of N Numbers** — Medium
3. **Palindrome Check** — Hard

The lab contains hidden tests and point allocations for automated grading.

---

## Streamlit Configuration

`.streamlit/config.toml` configures:

~~~text
Theme: dark
Headless mode: true
Port: 8501
Browser usage-stat collection: disabled
~~~

---

## Development Container

The repository contains:

~~~text
.devcontainer/devcontainer.json
~~~

The configured development container uses a Python 3.11 image and installs the packages listed in `packages.txt` and `requirements.txt`.

`packages.txt` currently contains:

~~~text
g++
~~~

The devcontainer also forwards port `8501` and is configured to launch Streamlit after attachment.

---

## Security Considerations

The current implementation is suitable for an academic/demo environment, but it should not be treated as a production security system without additional hardening.

### Password Storage

Passwords are stored as SHA-256 hashes through `data_manager.py`.

The implementation does **not** use a salted password-hashing algorithm such as Argon2, bcrypt, or scrypt.

### Local JSON Storage

Authentication information, behavioral samples, submissions, and logs are stored directly in JSON files.

This is simple for demonstrations but does not provide the concurrency, access control, transactional guarantees, or auditing normally expected from a production database.

### Client-Side Restrictions

Copy/paste and interaction restrictions are implemented in JavaScript in the browser.

Client-side controls can be bypassed by a sufficiently privileged or modified client environment and therefore should not be considered a complete anti-cheating mechanism.

### Code Execution

The local compiler executes submitted C++ programs through a subprocess.

Running untrusted source code in a production environment would require a hardened sandbox, resource isolation, filesystem/network restrictions, and stronger process controls.

---

## Limitations

The current implementation has several limitations visible in the codebase:

- Behavioral training data in the demo workflow is synthetic rather than a real-world keystroke dataset.
- The LSTM is trained as a multi-class classifier over enrolled users and does not implement a separate impostor-verification model.
- No independent test set or benchmark evaluation pipeline is included.
- Passwords use plain SHA-256 hashing without salting.
- Application persistence is file-based JSON.
- No public REST API is implemented.
- Client-side clipboard restrictions are not a complete security boundary.
- The stored lab `memory_limit_mb` value is part of the problem definition, but the local compiler execution path does not enforce it through an OS-level memory sandbox.
- No production-grade container sandbox is provided for running untrusted C++ submissions.
- The project does not contain automated unit/integration test suites.
- The bundled `models/` and `data/` directories are ignored by `.gitignore`, so a fresh Git clone should use `seed_demo.py` to recreate the demo runtime assets.

---

## Future Improvements

Potential extensions consistent with the current architecture include:

- Replace JSON persistence with a proper database.
- Use Argon2/bcrypt/scrypt for password storage.
- Add a secure execution sandbox for submitted code.
- Enforce CPU, memory, filesystem, and network limits for code execution.
- Add a real behavioral-keystroke dataset and an independent evaluation split.
- Add model-performance reporting and authentication calibration.
- Introduce stronger session/authentication controls.
- Add automated tests for authentication, grading, persistence, and frontend event handling.
- Separate application configuration from source code.
- Add formal API endpoints if external clients are required.

---

## Results / Screenshots

The uploaded project does not contain a dedicated screenshots directory or benchmark-results file.

The repository does contain a trained behavioral-authentication model artifact:

~~~text
models/behavioral_auth_model_lstm/lstm_model.keras
~~~

The training function reports final training and validation accuracy at runtime, but those metrics are not persisted as a results report in the project.

Therefore, no numerical model-performance claims are included in this README.

---

## License

No `LICENSE` file or explicit software license is present in the uploaded project.

Therefore, the project should currently be treated as **unlicensed unless a license is added by the project owner**.

---

## Contributors

The repository Git history identifies:

- **Harsh Tripathi**

Additional contribution history can be viewed through the Git commit history.

---

## Entry Points

### Main Application

~~~bash
streamlit run app.py
~~~

### Demo Data / Model Initialization

~~~bash
python seed_demo.py
~~~

---

## Important Files at a Glance

| File | Responsibility |
|---|---|
| `app.py` | Main Streamlit application and page/workflow router |
| `compiler.py` | C++ compilation, execution, fallback engines, test-case grading |
| `data_manager.py` | JSON persistence and CRUD operations |
| `ml_model.py` | Behavioral feature extraction and LSTM authentication model |
| `seed_demo.py` | Demo users, behavioral samples, model training, exam and lab seeding |
| `ui_components.py` | Reusable UI/layout components |
| `frontend/index.html` | Custom browser component for typing capture, exam UI, and coding UI |
| `requirements.txt` | Python dependencies |
| `packages.txt` | System package dependency (`g++`) |
| `.env.example` | Environment-variable template |
| `.streamlit/config.toml` | Streamlit runtime configuration |

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

             Student coding submission
                         │
                         ▼
                ┌──────────────────┐
                │  CppCompiler     │
                │  compiler.py     │
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

The current codebase is a functional academic/demo implementation of a behavioral-authenticated assessment platform with:

- Faculty and student roles
- Behavioral enrollment and authentication
- Continuous exam/lab authentication
- Exam management
- C++ coding labs
- Automated test-case grading
- Local JSON persistence
- Faculty reporting
- Custom Streamlit frontend components
- TensorFlow/Keras LSTM model
- Multiple C++ execution backends

This README intentionally documents only behavior, dependencies, assets, configurations, and workflows that are present in the uploaded project.
```
