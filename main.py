import io
import uuid
import base64
import os
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
import qrcode
from PIL import Image
import numpy as np
import cv2

# --- READER ENGINE ---
from reader_engine import ReaderEngine
from handwriting_ocr import get_handwriting_score_recognizer

reader = ReaderEngine(model_path="mnist_gtx_model.h5")
recognizer = get_handwriting_score_recognizer()

# --- DATABASE INTEGRATION ---

MARGIN = 20 * mm

# --- DATABASE INTEGRATION ---
from sqlalchemy.orm import Session
from database import engine, get_db, Base
import models

# Create the database tables automatically on startup
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Exam Cover API")

# A4 dimensions in points (1 mm ~ 2.83465 points)
A4_WIDTH, A4_HEIGHT = A4

class ExamMetadata(BaseModel):
    course_code: str = Field(..., example="PHY6202")
    course_name: str = Field(..., example="Advanced Physics")
    instructor_name: str = Field(..., example="Dr. Smith")
    question_count: int = Field(..., ge=1, le=20, example=10)

class ExamCoverResponse(BaseModel):
    exam_id: str
    layout_data: Dict[str, Any]
    pdf_base64: str

@app.get("/", response_class=HTMLResponse)
async def get_index():
    # Verify the file exists
    if not os.path.exists("index.html"):
        raise HTTPException(status_code=404, detail="index.html not found in the root directory")
        
    with open("index.html", "r") as f:
        return f.read()

@app.get("/admin", response_class=HTMLResponse)
async def get_admin_dashboard():
    if not os.path.exists("admin.html"):
        raise HTTPException(status_code=404, detail="admin.html not found in the root directory")
    with open("admin.html", "r") as f:
        return f.read()

# --- DEBUG/ADMIN ENDPOINTS ---

@app.get("/api/exams")
async def list_exams(db: Session = Depends(get_db)):
    exams = db.query(models.Exam).order_by(models.Exam.created_at.desc()).all()
    return exams

@app.get("/api/papers")
async def list_papers(db: Session = Depends(get_db)):
    papers = db.query(models.ScannedPaper).order_by(models.ScannedPaper.created_at.desc()).all()
    return papers

# --- TEAMMATE'S INFERENCE ENDPOINTS ---

@app.post("/predict")
async def predict_handwriting(
    file: UploadFile = File(...),
    max_points: int = 100
):
    """
    Teammate's endpoint: Processes a single handwriting ROI image and returns the recognized score.
    """
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    roi = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if roi is None:
        raise HTTPException(status_code=400, detail="Invalid image file")

    result = recognizer.recognize_score(roi, max_points=max_points)
    return result

@app.get("/api/predict/status")
async def predict_status():
    """
    Teammate's endpoint: Returns the status and engine type of the handwriting recognizer.
    """
    return {"status": "running", "engine": recognizer.engine}

def convert_to_top_left(x: float, y_bottom_left: float, width: float, height: float) -> Dict[str, float]:
    """
    Converts ReportLab's bottom-left (0,0) coordinates to a top-left (0,0) coordinate system.
    Returns standard top-left (x, y, w, h).
    """
    y_top_left = A4_HEIGHT - (y_bottom_left + height)
    return {
        "x": round(x, 2),
        "y": round(y_top_left, 2),
        "width": round(width, 2),
        "height": round(height, 2)
    }

def draw_student_id_section(c, x, y, width, height):
    """
    Draws a hybrid Student ID section:
    1. Handwriting boxes (12x14pt)
    2. OMR Grid (9x9pt boxes, 13.5pt row spacing)
    Wrapped in a clean outer frame.
    """
    c.saveState()
    
    # Outer Frame for the section
    c.setStrokeColor(colors.black)
    c.setLineWidth(1)
    c.rect(x, y - height, width, height, stroke=1, fill=0)
    
    # Section Header (Using standard characters for compatibility)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(x + width/2, y - 12, "STUDENT ID / OGRENCI NO")
    
    cols = 10
    box_w = 12
    box_h = 14
    gap = 3
    
    # Center the 10 columns in the width
    total_cols_w = cols * box_w + (cols - 1) * gap
    start_x = x + (width - total_cols_w) / 2
    
    # 1. Handwriting Boxes (Top)
    top_y = y - 32
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.7)
    for i in range(cols):
        cur_x = start_x + i * (box_w + gap)
        c.rect(cur_x, top_y, box_w, box_h, stroke=1, fill=0)
        
    # 2. OMR Grid
    omr_box_size = 9
    row_spacing = 13.5
    omr_start_y = top_y - 2 # Tighter spacing
    
    for i in range(cols):
        cur_x = start_x + i * (box_w + gap) + (box_w - omr_box_size) / 2
        for j in range(10): # Rows 0-9
            cur_y = omr_start_y - (j + 1) * row_spacing
            
            # OMR Box
            c.setStrokeColor(colors.black)
            c.setLineWidth(0.5)
            c.rect(cur_x, cur_y, omr_box_size, omr_box_size, stroke=1, fill=0)
            
            # Number inside (lightgrey, tiny)
            c.setFillColor(colors.lightgrey)
            c.setFont("Helvetica", 6)
            c.drawCentredString(cur_x + omr_box_size/2, cur_y + 2, str(j))
            
    c.restoreState()

def draw_tabular_header_with_qr(c, start_x, start_y, width, info_dict, qr_img_buffer, fill_student_id_str=None):
    """
    Design: Left (60%) = Logo + QR + Info Table
    Right (40%) = Student ID Grid (Hybrid)
    """
    c.setStrokeColor(colors.black)
    c.setLineWidth(1)
    c.setFillColor(colors.black)
    
    full_w = width - (2 * MARGIN)
    LEFT_WIDTH = full_w * 0.60
    RIGHT_WIDTH = full_w * 0.40
    
    current_y = start_y
    divider_x = start_x + LEFT_WIDTH
    # Adjust height to fit OMR + Header properly
    # 10 rows * 13.5 + boxes + margins
    header_height = 180 
    
    # ======= Left Section (Logo + QR + Info) =======
    left_x = start_x
    left_current_y = current_y
    
    # Draw logo and QR side-by-side
    top_section_h = 75
    logo_w = LEFT_WIDTH * 0.50
    logo_h = top_section_h
    logo_bottom = left_current_y - logo_h
    c.rect(left_x, logo_bottom, logo_w, logo_h)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(left_x + logo_w/2, logo_bottom + logo_h/2, "UNIVERSITY LOGO")
    
    # Draw QR Code
    qr_start_x = left_x + logo_w
    qr_section_w = LEFT_WIDTH - logo_w
    qr_size = min(72, qr_section_w - 4, logo_h - 4)
    qr_x = qr_start_x + (qr_section_w - qr_size) / 2
    qr_y = left_current_y - ((logo_h - qr_size) / 2) - qr_size
    c.rect(qr_start_x, left_current_y - logo_h, qr_section_w, logo_h)
    
    # Draw image using PIL ImageReader
    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(qr_img_buffer), qr_x, qr_y, width=qr_size, height=qr_size)
    
    # Info table
    row_h = 35 # Increased row height to match the right side better
    left_current_y -= top_section_h
    
    # Course Name row
    c.rect(left_x, left_current_y - row_h, LEFT_WIDTH, row_h)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(left_x + 3, left_current_y - 20, "Course")
    c.setFont("Helvetica", 7)
    course_text = f"{info_dict.get('course_code', '')} - {info_dict.get('course_name', '')}"
    c.drawString(left_x + 60, left_current_y - 20, course_text.upper())
    
    # Instructor row
    left_current_y -= row_h
    c.rect(left_x, left_current_y - row_h, LEFT_WIDTH, row_h)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(left_x + 3, left_current_y - 20, "Instructor")
    c.setFont("Helvetica", 7)
    instructor_text = info_dict.get('instructor_name', '')
    c.drawString(left_x + 60, left_current_y - 20, instructor_text.upper())
    
    # Date row
    left_current_y -= row_h
    c.rect(left_x, left_current_y - row_h, LEFT_WIDTH, row_h)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(left_x + 3, left_current_y - 20, "Date")
    
    # ======= Right Section: Student ID Grid =======
    draw_student_id_section(c, divider_x, current_y, RIGHT_WIDTH, header_height)
    
    return current_y - header_height # Y coordinate after header

def compute_handwriting_score_box_layout(question_width, question_height, header_h=20):
    """
    Calculates dimensions of handwriting score box.
    Made much larger to be 'closer' to the outer box.
    """
    # Leave a small 4pt margin from the sides of the question box
    box_width = float(question_width) - 8.0
    # Fill most of the remaining height, leaving room for the hint text
    box_height = float(question_height) - header_h - 18.0
    
    offset_x = 4.0
    offset_y = float(header_h) + 4.0
    
    return {
        "offsetX": offset_x,
        "offsetY": offset_y,
        "width": box_width,
        "height": box_height,
        "radius": 4.0,
    }

def draw_question_box(c, x, y, w, h, q_num, max_points, clo=None, fill_score=None):
    """Draws a question box with an OCR-optimized handwriting score area."""
    c.setStrokeColor(colors.black)
    c.setLineWidth(1)
    c.rect(x, y - h, w, h) # Outer frame
    
    header_h = 20
    c.line(x, y - header_h, x + w, y - header_h) # Header divider
    
    c.setFont("Helvetica-Bold", 9)
    label = f"Q{q_num} ({max_points}p)"
    c.drawCentredString(x + (w/2), y - 13, label)

    # Handwriting Box (OCR Optimized)
    # Passing both width and height now
    score_box = compute_handwriting_score_box_layout(w, h, header_h=header_h)
    score_box_x = x + score_box["offsetX"]
    score_box_top = y - score_box["offsetY"]
    score_box_y = score_box_top - score_box["height"]

    c.saveState()
    c.setStrokeColor(colors.lightgrey) # Light grey for filtering
    c.setLineWidth(0.5) # Thin line
    c.roundRect(
        score_box_x,
        score_box_y,
        score_box["width"],
        score_box["height"],
        score_box["radius"],
        stroke=1,
        fill=0,
    )
    c.restoreState()

    # Hint text UNDER the box (not inside)
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 6)
    c.drawCentredString(
        score_box_x + (score_box["width"] / 2),
        score_box_y - 6,
        f"0-{max_points}",
    )
    
    return {
        "x": score_box_x,
        "y": score_box_y,
        "width": score_box["width"],
        "height": score_box["height"]
    }

def generate_pdf_in_memory(metadata: ExamMetadata, exam_id: str):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    layout_data = {"student_id_box": {}, "grading_boxes": []}
    
    # 1. QR Code generation
    qr = qrcode.QRCode(box_size=4, border=1)
    qr.add_data(exam_id)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    img_buffer = io.BytesIO()
    qr_img.save(img_buffer, format="PNG")
    img_buffer.seek(0)
    
    # 2. Draw Header
    info_dict = {
        "course_code": metadata.course_code,
        "course_name": metadata.course_name,
        "instructor_name": metadata.instructor_name
    }
    
    header_y_end = draw_tabular_header_with_qr(
        c, MARGIN, A4_HEIGHT - MARGIN, A4_WIDTH, info_dict, img_buffer
    )
    
    # Map Student ID box for layout data
    header_height = 200
    full_w = A4_WIDTH - (2 * MARGIN)
    LEFT_WIDTH = full_w * 0.60
    RIGHT_WIDTH = full_w * 0.40
    layout_data["student_id_box"] = convert_to_top_left(
        MARGIN + LEFT_WIDTH, A4_HEIGHT - MARGIN - header_height, RIGHT_WIDTH, header_height
    )
    
    # 3. Draw Question Boxes
    # Fit 5 boxes per row
    available_width = A4_WIDTH - (2 * MARGIN)
    spacing = 3 * mm
    box_w = (available_width - (4 * spacing)) / 5
    box_h = 35 * mm # Halved height
    
    start_x = MARGIN
    start_y = header_y_end - 10 * mm
    
    x_offset = start_x
    y_offset = start_y
    
    for i in range(metadata.question_count):
        # Move to next line if we already have 5 boxes (checking x_offset)
        if x_offset + box_w > A4_WIDTH - MARGIN + 1: # small epsilon for float precision
            x_offset = start_x
            y_offset -= (box_h + 10 * mm)
            
        score_box_coords = draw_question_box(
            c, x_offset, y_offset, box_w, box_h, i+1, 10
        )
        
        # Map coordinates for the score box (what we actually want to read)
        layout_data["grading_boxes"].append({
            "question": i + 1,
            "coordinates": convert_to_top_left(
                score_box_coords["x"], 
                score_box_coords["y"], 
                score_box_coords["width"], 
                score_box_coords["height"]
            )
        })
        
        x_offset += box_w + spacing
        
    c.showPage()
    c.save()
    
    buffer.seek(0)
    pdf_base64 = base64.b64encode(buffer.read()).decode("utf-8")
    
    return pdf_base64, layout_data

@app.post("/api/generate-cover", response_model=ExamCoverResponse)
async def generate_cover_endpoint(metadata: ExamMetadata, db: Session = Depends(get_db)):
    try:
        # Generate Unique Exam ID
        short_uuid = str(uuid.uuid4())[:8]
        exam_id = f"{metadata.course_code}-{short_uuid}"
        
        # Generate PDF and layout data
        pdf_base64, layout_data = generate_pdf_in_memory(metadata, exam_id)
        
        # Save Exam and Coordinates to Database
        db_exam = models.Exam(
            id=exam_id,
            course_code=metadata.course_code,
            course_name=metadata.course_name,
            instructor_name=metadata.instructor_name,
            question_count=metadata.question_count,
            layout_data=layout_data
        )
        db.add(db_exam)
        db.commit()
        db.refresh(db_exam)
        
        return ExamCoverResponse(
            exam_id=exam_id,
            layout_data=layout_data,
            pdf_base64=pdf_base64
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scan-paper")
async def scan_paper(
    exam_id: str, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    """
    Receives an uploaded exam paper, processes it using ReaderEngine, 
    and saves results to the database.
    """
    # 1. Fetch Exam Layout from DB
    db_exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not db_exam:
        raise HTTPException(status_code=404, detail="Exam layout not found")
        
    layout_data = db_exam.layout_data
    
    # 2. Load and Preprocess Image
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if image is None:
        raise HTTPException(status_code=400, detail="Invalid image file")

    # In a real-world scenario, we would perform 'Image Alignment' here
    # to align the paper based on markers/corners. For this prototype,
    # we assume the scan is reasonably aligned with the generated layout.
    
    # Convert image to grayscale for OCR/OMR
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 3. Process Student ID (Hybrid OMR)
    # The layout_data['student_id_box'] contains {x, y, width, height} in top-left pixels
    sid_box = layout_data["student_id_box"]
    
    # We need to calibrate luma first. We'll use regions of the image 
    # (assuming fixed calibration areas or just using the ID box itself)
    # For now, let's use a simple global calibration based on image mean
    luma_refs = {
        "white": np.percentile(gray, 95), # Assume top 5% is paper white
        "black": np.percentile(gray, 5),  # Assume bottom 5% is ink black
        "grey": np.mean(gray)
    }
    
    student_id = ""
    # The grid has 10 columns and 10 rows
    cols = 10
    rows = 10
    
    # Approximate OMR grid within the student_id_box
    # Note: These values should ideally be part of layout_data
    # For prototype, we divide the box into a grid
    grid_x = sid_box["x"]
    grid_y = sid_box["y"] + 35 # Skip the header part
    grid_w = sid_box["width"]
    grid_h = sid_box["height"] - 35
    
    col_step = grid_w / cols
    row_step = grid_h / rows
    
    for c in range(cols):
        detected_digit = None
        for r in range(rows):
            cx = int(grid_x + (c + 0.5) * col_step)
            cy = int(grid_y + (r + 0.5) * row_step)
            radius = int(min(col_step, row_step) * 0.4)
            
            is_filled = reader.scan_omr_circle(gray, cx, cy, radius, luma_refs)
            if is_filled:
                detected_digit = str(r)
                break
        student_id += detected_digit if detected_digit else "?"

    # 4. Process Question Scores (Handwritten OCR)
    scores_result = []
    for q_data in layout_data["grading_boxes"]:
        q_num = q_data["question"]
        coords = q_data["coordinates"] # {x, y, width, height}
        
        # Crop the ROI with 10% safety margin
        roi = reader.crop_roi_safely(
            image, 
            int(coords["x"]), 
            int(coords["y"]), 
            int(coords["width"]), 
            int(coords["height"]),
            margin_pct=0.1
        )
        
        # Predict using MNIST model
        predicted_score = reader.predict_digit(roi)
        scores_result.append({
            "question": q_num,
            "score": predicted_score
        })

    # 5. Save results to DB
    db_paper = models.ScannedPaper(
        exam_id=exam_id,
        student_number=student_id,
        image_url="placeholder_url", # In production, upload to S3/Cloud
        status=models.ProcessingStatus.COMPLETED
    )
    db.add(db_paper)
    db.commit()
    db.refresh(db_paper)
    
    for s in scores_result:
        db_score = models.Score(
            scanned_paper_id=db_paper.id,
            question_number=s["question"],
            points_awarded=s["score"],
            confidence_score=1.0 # Placeholder
        )
        db.add(db_score)
    
    db.commit()

    return {
        "paper_id": db_paper.id,
        "student_id": student_id,
        "scores": scores_result
    }
