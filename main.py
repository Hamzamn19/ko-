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
import fitz  # PyMuPDF

# --- READER ENGINE ---
from reader_engine import ReaderEngine
# We officially switch to the integrated ReaderEngine for all tasks
reader = ReaderEngine(model_path="mnist_gtx_model.onnx")

# --- DATABASE INTEGRATION ---
from sqlalchemy.orm import Session
from database import engine, get_db, Base
import models

# Create the database tables automatically on startup
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Exam Cover API")

# A4 dimensions in points (1 mm ~ 2.83465 points)
A4_WIDTH, A4_HEIGHT = A4
MARGIN = 20 * mm

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
    if not os.path.exists("index.html"):
        raise HTTPException(status_code=404, detail="index.html not found")
    with open("index.html", "r") as f:
        return f.read()

@app.get("/admin", response_class=HTMLResponse)
async def get_admin_dashboard():
    if not os.path.exists("admin.html"):
        raise HTTPException(status_code=404, detail="admin.html not found")
    with open("admin.html", "r") as f:
        return f.read()

@app.get("/api/exams")
async def list_exams(db: Session = Depends(get_db)):
    return db.query(models.Exam).order_by(models.Exam.created_at.desc()).all()

@app.get("/api/papers")
async def list_papers(db: Session = Depends(get_db)):
    return db.query(models.ScannedPaper).order_by(models.ScannedPaper.created_at.desc()).all()

# --- HELPERS ---

async def process_upload_to_image(file: UploadFile) -> np.ndarray:
    contents = await file.read()
    if file.filename.lower().endswith(".pdf") or (file.content_type and file.content_type == "application/pdf"):
        try:
            doc = fitz.open(stream=contents, filetype="pdf")
            page = doc.load_page(0)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_data = pix.tobytes("png")
            nparr = np.frombuffer(img_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            doc.close()
            return image
        except Exception as e:
            print(f"PDF conversion failed: {e}")
            return None
    else:
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return image

def convert_to_top_left(x: float, y_bottom_left: float, width: float, height: float) -> Dict[str, float]:
    y_top_left = A4_HEIGHT - (y_bottom_left + height)
    return {"x": round(x, 2), "y": round(y_top_left, 2), "width": round(width, 2), "height": round(height, 2)}

# --- PDF DRAWING LOGIC ---

def draw_student_id_section(c, x, y, width, height):
    c.saveState()
    c.setStrokeColor(colors.black); c.setLineWidth(1)
    c.rect(x, y - height, width, height, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(x + width/2, y - 12, "STUDENT ID / OGRENCI NO")
    cols, box_w, box_h, gap = 10, 12, 14, 3
    total_cols_w = cols * box_w + (cols - 1) * gap
    start_x = x + (width - total_cols_w) / 2
    top_y = y - 32
    c.setLineWidth(0.7)
    for i in range(cols):
        c.rect(start_x + i * (box_w + gap), top_y, box_w, box_h, stroke=1, fill=0)
    omr_box_size, row_spacing = 9, 13.5
    omr_start_y = top_y - 2
    for i in range(cols):
        cur_x = start_x + i * (box_w + gap) + (box_w - omr_box_size) / 2
        for j in range(10):
            cur_y = omr_start_y - (j + 1) * row_spacing
            c.setLineWidth(0.5); c.rect(cur_x, cur_y, omr_box_size, omr_box_size, stroke=1, fill=0)
            c.setFillColor(colors.lightgrey); c.setFont("Helvetica", 6); c.drawCentredString(cur_x + omr_box_size/2, cur_y + 2, str(j))
            c.setFillColor(colors.black)
    c.restoreState()

def draw_tabular_header_with_qr(c, start_x, start_y, width, info_dict, qr_img_buffer):
    full_w = width - (2 * MARGIN)
    LEFT_WIDTH, RIGHT_WIDTH = full_w * 0.60, full_w * 0.40
    header_height = 180
    c.rect(start_x, start_y - 75, LEFT_WIDTH * 0.50, 75)
    c.setFont("Helvetica-Bold", 10); c.drawCentredString(start_x + (LEFT_WIDTH * 0.25), start_y - 40, "UNIVERSITY LOGO")
    qr_size = 70; qr_x = start_x + (LEFT_WIDTH * 0.50) + (LEFT_WIDTH * 0.50 - qr_size) / 2
    qr_y = start_y - 75 + (75 - qr_size) / 2
    c.rect(start_x + (LEFT_WIDTH * 0.50), start_y - 75, LEFT_WIDTH * 0.50, 75)
    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(qr_img_buffer), qr_x, qr_y, width=qr_size, height=qr_size)
    row_h = 35; curr_y = start_y - 75
    for label, key in [("Course", "course_code"), ("Instructor", "instructor_name"), ("Date", None)]:
        c.rect(start_x, curr_y - row_h, LEFT_WIDTH, row_h)
        c.setFont("Helvetica-Bold", 7); c.drawString(start_x + 3, curr_y - 20, label)
        if key:
            c.setFont("Helvetica", 7); val = info_dict.get(key, '').upper()
            if key == "course_code": val += f" - {info_dict.get('course_name', '').upper()}"
            c.drawString(start_x + 60, curr_y - 20, val)
        curr_y -= row_h
    draw_student_id_section(c, start_x + LEFT_WIDTH, start_y, RIGHT_WIDTH, header_height)
    return start_y - header_height

def draw_question_box(c, x, y, w, h, q_num, max_points):
    c.rect(x, y - h, w, h); c.line(x, y - 20, x + w, y - 20)
    c.setFont("Helvetica-Bold", 9); c.drawCentredString(x + (w/2), y - 13, f"Q{q_num} ({max_points}p)")
    box_w, box_h = w - 8.0, h - 20.0 - 18.0; bx, by = x + 4.0, y - 20.0 - 4.0 - box_h
    c.saveState(); c.setStrokeColor(colors.lightgrey); c.roundRect(bx, by, box_w, box_h, 4.0, stroke=1, fill=0); c.restoreState()
    c.setFont("Helvetica", 6); c.drawCentredString(bx + (box_w/2), by - 6, f"0-{max_points}")
    return {"x": bx, "y": by, "width": box_w, "height": box_h}

# --- ENDPOINTS ---

@app.post("/api/generate-cover", response_model=ExamCoverResponse)
async def generate_cover_endpoint(metadata: ExamMetadata, db: Session = Depends(get_db)):
    try:
        exam_id = f"{metadata.course_code}-{str(uuid.uuid4())[:8]}"
        buffer = io.BytesIO(); c = canvas.Canvas(buffer, pagesize=A4)
        qr = qrcode.QRCode(box_size=4, border=1); qr.add_data(exam_id); qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_buf = io.BytesIO(); qr_img.save(qr_buf, format="PNG"); qr_buf.seek(0)
        layout_data = {"grading_boxes": []}
        header_y = draw_tabular_header_with_qr(c, MARGIN, A4_HEIGHT - MARGIN, A4_WIDTH, metadata.dict(), qr_buf)
        full_w = A4_WIDTH - (2 * MARGIN)
        layout_data["student_id_box"] = convert_to_top_left(MARGIN + (full_w * 0.60), A4_HEIGHT - MARGIN - 180, full_w * 0.40, 180)
        box_w, box_h, spacing = (full_w - (4 * 3*mm)) / 5, 35*mm, 3*mm
        curr_x, curr_y = MARGIN, header_y - 10*mm
        for i in range(metadata.question_count):
            if curr_x + box_w > A4_WIDTH - MARGIN + 1: curr_x, curr_y = MARGIN, curr_y - (box_h + 10*mm)
            coords = draw_question_box(c, curr_x, curr_y, box_w, box_h, i+1, 10)
            layout_data["grading_boxes"].append({"question": i+1, "coordinates": convert_to_top_left(coords["x"], coords["y"], coords["width"], coords["height"])})
            curr_x += box_w + spacing
        c.showPage(); c.save(); buffer.seek(0)
        db_exam = models.Exam(id=exam_id, course_code=metadata.course_code, course_name=metadata.course_name, instructor_name=metadata.instructor_name, question_count=metadata.question_count, layout_data=layout_data)
        db.add(db_exam); db.commit()
        return ExamCoverResponse(exam_id=exam_id, layout_data=layout_data, pdf_base64=base64.b64encode(buffer.read()).decode("utf-8"))
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scan-paper")
async def scan_paper(file: UploadFile = File(...), db: Session = Depends(get_db)):
    image = await process_upload_to_image(file)
    if image is None: raise HTTPException(status_code=400, detail="Invalid image or PDF file")
    
    # 1. Automatic QR Code Detection
    exam_id = reader.detect_qr_code(image)
    if not exam_id: raise HTTPException(status_code=400, detail="Could not read QR code from paper. Please ensure the QR code is clearly visible.")
    
    db_exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not db_exam: raise HTTPException(status_code=404, detail=f"Exam layout not found for ID: {exam_id}")
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    sid_box = db_exam.layout_data["student_id_box"]
    luma_refs = {"white": np.percentile(gray, 95), "black": np.percentile(gray, 5), "grey": np.mean(gray)}
    
    student_id, cols, rows = "", 10, 10
    gx, gy, gw, gh = sid_box["x"], sid_box["y"] + 35, sid_box["width"], sid_box["height"] - 35
    cw, rh = gw / cols, gh / rows
    for c in range(cols):
        digit = None
        for r in range(rows):
            if reader.scan_omr_circle(gray, int(gx + (c + 0.5) * cw), int(gy + (r + 0.5) * rh), int(min(cw, rh) * 0.4), luma_refs):
                digit = str(r); break
        student_id += digit if digit else "?"

    results = []
    for q in db_exam.layout_data["grading_boxes"]:
        coords = q["coordinates"]
        roi = reader.crop_roi_safely(image, int(coords["x"]), int(coords["y"]), int(coords["width"]), int(coords["height"]), margin_pct=0.1)
        results.append({"question": q["question"], "score": reader.predict_digit(roi)})

    db_paper = models.ScannedPaper(exam_id=exam_id, student_number=student_id, image_url="placeholder", status=models.ProcessingStatus.COMPLETED)
    db.add(db_paper); db.commit(); db.refresh(db_paper)
    for res in results:
        db.add(models.Score(scanned_paper_id=db_paper.id, question_number=res["question"], points_awarded=res["score"], confidence_score=1.0))
    db.commit()
    return {"exam_id": exam_id, "paper_id": db_paper.id, "student_id": student_id, "scores": results}

@app.post("/predict")
async def predict_handwriting(file: UploadFile = File(...)):
    """Predicts score from a single snippet using ReaderEngine (ONNX)."""
    image = await process_upload_to_image(file)
    if image is None: raise HTTPException(status_code=400, detail="Invalid image or PDF file")
    score = reader.predict_digit(image)
    return {"score": score}

@app.get("/api/predict/status")
async def predict_status():
    return {"status": "running", "engine": "onnxruntime"}
