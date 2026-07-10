# TrueTestAuth

TrueTestAuth is a Streamlit-based educational proctoring platform designed for secure online assessments and programming labs. It combines behavioral authentication, continuous monitoring, and automated code evaluation into a single, user-friendly application for both instructors and students.

The system is intended to simulate a realistic classroom assessment environment where faculty can manage exams and coding labs, while students can complete tasks in a monitored setting with anti-cheating safeguards and automated feedback.

---

## Overview

TrueTestAuth provides the following core capabilities:

- A polished login and registration experience for students and faculty.
- A faculty dashboard for managing exams, labs, students, and reports.
- A student dashboard for accessing enrolled courses and assessments.
- Behavioral keystroke authentication to monitor typing patterns.
- Copy-paste blocking during assessments.
- C++ code execution and evaluation for programming assignments.

This project is well-suited for demos, academic presentations, and experimentation with educational proctoring concepts.

---

## Key Features

### 1. Role-Based Access

The application supports two primary roles:

- Faculty: manage courses, exams, labs, enrolled students, and reports.
- Student: view assessments, attempt exams, and submit coding solutions.

### 2. Behavioral Authentication

The platform analyzes typing behavior using keystroke-based features such as:

- Dwell time
- Flight time
- Typing speed
- Rhythm consistency
- Total typing duration

These features are used to produce a behavioral confidence score that helps detect suspicious activity during assessments.

### 3. Copy-Paste Protection

The app blocks common clipboard-based actions in assessment fields to reduce opportunities for unauthorized assistance.

### 4. Coding Lab Environment

Students can work on C++ programming tasks directly inside the app and run their code through an integrated compilation pipeline.

The compilation layer uses a fallback sequence:

1. Judge0
2. Piston
3. Local g++ compiler

This helps ensure the platform remains functional under different network and system conditions.

### 5. Demo Data Seeding

The project includes demo data generation so you can test the full experience immediately without manually creating users or assessments.

---

## Project Architecture

The application is organized into the following main modules:

- app.py: Main Streamlit application entry point.
- compiler.py: Handles code compilation and execution.
- data_manager.py: Stores and manages JSON-based app data.
- ml_model.py: Implements the behavioral authentication model logic.
- seed_demo.py: Creates demo users, exams, labs, and model data.
- frontend/index.html: Frontend component for collecting typing and interaction data.
- data/: Stores local JSON data files.
- models/: Stores trained model artifacts.

---

## Technology Stack

The project is built with:

- Python
- Streamlit
- scikit-learn
- NumPy
- Pandas
- Joblib
- Requests
- python-dotenv
- pdfplumber

---

## Installation

### Prerequisites

Make sure Python 3.9 or newer is installed on your system.

### Clone the Repository

```bash
git clone https://github.com/erharsh2104/TrueTestAuth.git
cd TrueTestAuth
```

### Create a Virtual Environment

On Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

On macOS/Linux:

```bash
python -m venv venv
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Seed Demo Data

```bash
python seed_demo.py
```

This command populates the local JSON data files with sample users, an exam, a lab, and the initial model setup.

### Run the Application

```bash
streamlit run app.py
```

Then open the local address shown in the terminal, usually:

```text
http://localhost:8501
```

---

## Demo Credentials

The seeded demo accounts use the password:

```text
demo123
```

Available demo users:

| Role | Username | Notes |
|------|----------|-------|
| Faculty | prof_sharma | Demo faculty account |
| Student | alice_cs | Demo student account |
| Student | bob_cs | Demo student account |
| Student | charlie | Demo student account |

---

## How the Application Works

### Student Workflow

1. Log in as a student.
2. Open an enrolled course or assessment.
3. Start an exam or lab.
4. Complete the assigned task while the typing monitor observes behavior.
5. Submit the work for evaluation.

### Faculty Workflow

1. Log in as faculty.
2. Review enrolled students and courses.
3. Create or manage exams and coding labs.
4. Review submissions and reporting information.

### Proctoring Logic

During an assessment:

- the system records keystroke information,
- computes a behavioral confidence score,
- tracks suspicious events such as paste attempts,
- and stores the results for later review.

---

## Compiler and Execution Flow

The compiler layer is designed to support flexible C++ execution.

### Execution Order

1. Judge0, if an API key is available.
2. Piston, as a network-based fallback.
3. Local g++ compiler, as an offline fallback.

### Judge0 Configuration

To enable Judge0, create a .env file based on the example file and add your API key:

```bash
JUDGE0_API_KEY=your_api_key_here
```

If no key is present, the application will fall back to the other available engines.

---

## Data Storage

The project uses JSON files for local persistence instead of a database. The main files are stored in the data folder:

- users.json
- exams.json
- labs.json
- submissions.json
- lab_submissions.json
- auth_logs.json
- cp_logs.json
- enrollments.json

This design keeps the system simple to demo and easy to understand.

---

## File Structure

```text
TrueTestAuth/
├── app.py
├── compiler.py
├── data_manager.py
├── ml_model.py
├── seed_demo.py
├── requirements.txt
├── README.md
├── .env.example
├── frontend/
│   └── index.html
├── data/
├── models/
└── .streamlit/
```

---

## Notes and Limitations

This project is intended as a prototype and demonstration platform. Some limitations include:

- The behavioral model is based on a small demo dataset.
- It is not a production-grade LMS or enterprise proctoring system.
- Password hashing is intentionally simple for prototype use.
- Browser and environment differences may affect timing precision.

---

## Future Improvements

Possible enhancements include:

- Real database integration
- Advanced analytics dashboards
- Webcam and screen monitoring support
- Multi-language coding support
- Stronger authentication and security hardening
- Expanded user role and permission management

---

## License

This project is intended for educational and demonstration purposes.

If you are using it as a learning resource, feel free to adapt and extend it.

---

## Contributing

Contributions are welcome. If you would like to improve the project, you can:

- report bugs,
- suggest new features,
- improve documentation,
- or submit a pull request.
