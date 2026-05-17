# Project GEMINI: Exam Cover & Analytics System (KO-)

This project is an automated EdTech platform designed for exam grading, student identification, and performance analytics using Computer Vision (OCR/OMR) and AI.

## Project Overview

The system automates the lifecycle of physical exam papers:
1.  **Generation**: Creates A4 PDF cover sheets with unique QR codes and OMR (Optical Mark Recognition) boxes for Student IDs and scores.
2.  **Scanning**: Processes images of filled exam sheets to extract Student IDs (via OMR) and handwritten scores (via Handwriting Text Recognition).
3.  **Analytics**: Stores results in a database and provides a "Student 360" dashboard for tracking progress.
4.  **Local Analytics**: Stores results in a database and provides a "Student 360" dashboard.
5.  **Programmatic Reports**: Generates automated performance reports and custom quizzes locally using algorithmic analysis (defined in `report_generator.py`).

### Core Technology Stack
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.11)
- **Database**: [SQLAlchemy](https://www.sqlalchemy.org/) with SQLite
- **Computer Vision**: [OpenCV](https://opencv.org/) & [ONNX Runtime](https://onnxruntime.ai/)
- **PDF Generation**: [ReportLab](https://www.reportlab.com/)
- **OCR/HTR**: Custom MNIST-based model (`mnist_gtx_model.onnx`) and an optional "NovaVision" inference server.
- **Reporting Engine**: Local Python logic for rule-based analytics and quiz generation.

## Key Components

- **`main.py`**: The central FastAPI application containing all API endpoints for PDF generation, scanning, and data retrieval.
- **`models.py`**: SQLAlchemy ORM models (Student, Exam, Question, ScannedPaper, Score).
- **`report_generator.py`**: Contains the programmatic logic for generating student and class performance reports without external AI dependencies.
- **`reader_engine.py`**: The core "intelligence" module. Handles image alignment, QR code detection, OMR bubble scanning, and OCR score prediction.
- **`handwriting_ocr.py`**: Implements the low-level handwriting recognition logic using ONNX models.
- **`inference_server.py`**: A standalone service (NovaVision) that provides the `predict` endpoint for score recognition.
- **`database.py`**: Configures the SQLite database connection (`db/hackathon.db`).
- **`static/`**: Contains UI assets and stores generated/scanned images.

## Building and Running

### Prerequisites
- Python 3.11+
- System libraries for OpenCV (see `Dockerfile` for details)

### Local Development
1.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **Start the API server**:
    ```bash
    uvicorn main:app --reload
    ```
3.  **Start the Inference Server (Optional - if using NovaVision)**:
    ```bash
    uvicorn inference_server:app --port 8001
    ```

### Docker Deployment
The project includes a `docker-compose.yml` for easy setup:
```bash
docker-compose up --build
```

## Development Conventions

- **Database**: SQLite is used for development. Tables are created automatically on startup in `main.py`.
- **Styling**: The project uses a custom UI framework defined in `static/Aurora.css` and `static/dashboard-ui.css`.
- **OCR Fallback**: The `ReaderEngine` in `reader_engine.py` attempts to use an external `NOVAVISION_URL` but falls back to local processing if the server is unreachable.
- **AI Reports**: The system integrates with an external webhook (`PUQ_WEBHOOK_URL`) for generating complex AI-driven student reports.

## TODOs / Next Steps (Inferred from `plan.md`)
- [ ] Implement manual review/override interface for low-confidence scores.
- [ ] Enhance image alignment for high-angle mobile phone captures.
- [ ] Refine the transition from local MNIST models to cloud-based HTR.
