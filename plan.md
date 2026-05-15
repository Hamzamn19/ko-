# EdTech System Implementation Plan & Architecture

## Overview
This document serves as the master execution plan and architectural reference for our 40-hour hackathon project. We are building an automated EdTech SaaS platform for exam grading and analytics.

## Tech Stack
- **Backend Framework:** Python 3.11, FastAPI
- **Database:** SQLite with SQLAlchemy ORM
- **PDF Generation:** ReportLab
- **Computer Vision (Pre-processing):** NovaVision (Diginova) API
- **Intelligence Engine (Reading):** Puq.ai API

---

## Architecture & Workflow

### Phase 1: Exam Definition & PDF Generation
**Status: ✅ COMPLETED**
- **Action:** Instructor defines exam metadata (Course, Instructor, Question Count).
- **Process:** 
  - Generates a 1-page A4 PDF cover sheet.
  - Places a unique QR code (Exam ID) in the top right.
  - Draws a Student ID optical box and individual score boxes for grading.
- **Database Storage:** Saves the `Exam ID`, metadata, and the exact `(x, y, width, height)` coordinates of all drawn boxes (mapped to a top-left origin) into the `Exams` table.

### Phase 2: Paper Scanning & NovaVision Processing
**Status: 🚧 NEXT UP**
- **Action:** Instructor uploads a scanned image of the filled-out exam cover page to `POST /api/papers/upload`.
- **NovaVision Role (Structural Pre-processor):** 
  - Backend sends the raw image to NovaVision.
  - NovaVision perfectly deskews/aligns the image.
  - NovaVision reads the QR code and returns the `Exam ID`.
- **Database Storage:** Backend creates a `ScannedPaper` record associated with the Exam ID and sets its status to `PROCESSING`.

### Phase 3: Cropping & Puq.ai Extraction
**Status: 🚧 PENDING**
- **Action:** Slicing the image and extracting data.
- **Local Cropping:** 
  - Backend looks up the `layout_data` (coordinates) from the `Exams` table using the Exam ID.
  - Backend uses Python (Pillow/OpenCV) to physically crop the aligned image into tiny fragments: 1 slice for the Student ID area, and N slices for the individual question score boxes.
- **Puq.ai Role (Intelligence Engine):**
  - **OMR:** Send the Student ID slice to Puq.ai to read the filled optical bubbles.
  - **HTR:** Send the small score box slices to Puq.ai's Handwriting Text Recognition endpoint to read the teacher's handwritten integers.
- **Validation & Database Storage:**
  - Save the recognized scores and confidence metrics to the `Scores` table.
  - If Puq.ai returns low confidence or an invalid format, flag the paper as `NEEDS_REVIEW`. Otherwise, mark as `COMPLETED`.
  - *(Note: The legacy local `mnist_gtx_model.h5` model has been officially bypassed in favor of the Puq.ai cloud service for this hackathon).*

### Phase 4: Analytics & Review Endpoints
**Status: 🚧 PENDING**
- **Action:** Providing insights to the instructor.
- **Endpoints:**
  - `GET /api/exams/{id}/analytics`: Calculates class averages, score distributions, and individual success rates per specific question (identifying areas where students struggle).
  - `POST /api/papers/{id}/review`: Allows instructors to manually correct/override scores that were flagged as `NEEDS_REVIEW` by Puq.ai.

---

## Database Schema (Mental Model)
- **`Exams`**: `id` (Unique Exam ID), `course_code`, `question_count`, `layout_data` (JSON of coordinates).
- **`ScannedPapers`**: `id`, `exam_id`, `image_url`, `status`, `student_number`.
- **`Scores`**: `id`, `scanned_paper_id`, `question_number`, `points_awarded`, `confidence_score` (from Puq.ai).
