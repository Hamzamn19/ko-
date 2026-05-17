import io
import uuid
import base64
import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Body
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
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
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register Unicode Font (DejaVuSans supports Arabic/Turkish)
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

try:
    pdfmetrics.registerFont(TTFont('DejaVuSans', FONT_PATH))
    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', FONT_BOLD_PATH))
    DEFAULT_FONT = "DejaVuSans"
    DEFAULT_FONT_BOLD = "DejaVuSans-Bold"
except:
    DEFAULT_FONT = "Helvetica"
    DEFAULT_FONT_BOLD = "Helvetica-Bold"

def shape_text(text: str) -> str:
    """Shapes Arabic text and applies BiDi algorithm."""
    if not text: return ""
    reshaped_text = arabic_reshaper.reshape(text)
    return get_display(reshaped_text)

# --- READER ENGINE ---
from reader_engine import ReaderEngine
# We officially switch to the integrated ReaderEngine for all tasks
reader = ReaderEngine(model_path="models/mnist_gtx_model.onnx")

# --- DATABASE INTEGRATION ---
from sqlalchemy.orm import Session
from database import engine, get_db, Base
import models
from report_generator import generate_local_student_report, generate_local_class_report

# Create the database tables automatically on startup
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Exam Cover API")

# Ensure static directory exists
STATIC_DIR = "static"
TEMPLATES_DIR = "templates"
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --- REQUEST MODELS ---

class AIStudentReportRequest(BaseModel):
    language: str = Field(default="tr", description="Rapor dili")
    include_quiz: bool = Field(default=True, description="Quiz dahil edilsin mi")
    quiz_question_count: int = Field(default=10, ge=5, le=20, description="Quiz soru sayısı")

class AIClassReportRequest(BaseModel):
    language: str = Field(default="tr", description="Rapor dili")

# A4 dimensions in points (1 mm ~ 2.83465 points)
A4_WIDTH, A4_HEIGHT = A4
MARGIN = 30

class QuestionInput(BaseModel):
    topic: str = "General"
    max_points: int = 10
    string_tag: str = ""  # Kısa konu etiketi: "Kirchoff Rule", "Nested Loops"

class ExamMetadata(BaseModel):
    course_code: str = Field(..., example="PHY6202")
    course_name: str = Field(..., example="Advanced Physics")
    instructor_name: str = Field(..., example="Dr. Smith")
    question_count: int = Field(..., ge=1, le=20, example=10)
    questions_data: List[QuestionInput] = Field(default=[], description="Optional topics per question")

class ExamCoverResponse(BaseModel):
    exam_id: str
    layout_data: Dict[str, Any]
    pdf_base64: str

@app.get("/", response_class=HTMLResponse)
async def get_index():
    path = os.path.join(TEMPLATES_DIR, "index.html")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="index.html not found")
    with open(path, "r") as f:
        return f.read()

@app.get("/admin", response_class=HTMLResponse)
async def get_admin_dashboard():
    path = os.path.join(TEMPLATES_DIR, "admin.html")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="admin.html not found")
    with open(path, "r") as f:
        return f.read()

@app.get("/scanner", response_class=HTMLResponse)
async def get_scanner():
    path = os.path.join(TEMPLATES_DIR, "scanner.html")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="scanner.html not found")
    with open(path, "r") as f:
        return f.read()

@app.get("/api/exams")
async def list_exams(db: Session = Depends(get_db)):
    return db.query(models.Exam).order_by(models.Exam.created_at.desc()).all()

@app.get("/api/papers")
async def list_papers(db: Session = Depends(get_db)):
    return db.query(models.ScannedPaper).order_by(models.ScannedPaper.created_at.desc()).all()

# --- STUDENT 360 ENDPOINTS ---

class StudentInput(BaseModel):
    student_number: str
    name: str
    email: str

@app.get("/student-360", response_class=HTMLResponse)
async def get_student_360():
    path = os.path.join(TEMPLATES_DIR, "student_360.html")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="student_360.html not found")
    with open(path, "r") as f:
        return f.read()

@app.post("/api/students")
async def create_student(student: StudentInput, db: Session = Depends(get_db)):
    db_student = db.query(models.Student).filter(models.Student.student_number == student.student_number).first()
    if db_student:
        db_student.name = student.name
        db_student.email = student.email
    else:
        db_student = models.Student(**student.dict())
        db.add(db_student)
    db.commit()
    return {"status": "success", "student": student}

@app.get("/api/students")
async def list_students(db: Session = Depends(get_db)):
    from sqlalchemy import func
    
    query = db.query(
        models.Student.student_number,
        models.Student.name,
        models.Student.email,
        func.count(models.ScannedPaper.id.distinct()).label('exam_count'),
        func.sum(models.Score.points_awarded).label('total_score')
    ).outerjoin(
        models.ScannedPaper, models.Student.student_number == models.ScannedPaper.student_number
    ).outerjoin(
        models.Score, models.ScannedPaper.id == models.Score.scanned_paper_id
    ).group_by(
        models.Student.student_number,
        models.Student.name,
        models.Student.email
    ).all()

    res = []
    for student_number, name, email, exam_count, total_score in query:
        res.append({
            "student_number": student_number,
            "name": name,
            "email": email,
            "exam_count": exam_count,
            "total_score": int(total_score) if total_score is not None else 0
        })
    return res

@app.get("/api/students/{student_number}")
async def get_student_details(student_number: str, db: Session = Depends(get_db)):
    from sqlalchemy.orm import joinedload
    student = db.query(models.Student).filter(models.Student.student_number == student_number).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    papers = db.query(models.ScannedPaper).options(
        joinedload(models.ScannedPaper.scores),
        joinedload(models.ScannedPaper.exam)
    ).filter(models.ScannedPaper.student_number == student_number).all()
    
    # Batch-load all relevant questions in one query
    exam_ids = list(set(p.exam_id for p in papers))
    all_questions = {}
    if exam_ids:
        questions = db.query(models.Question).filter(models.Question.exam_id.in_(exam_ids)).all()
        for q in questions:
            all_questions[(q.exam_id, q.question_number)] = q
    
    history = []
    topic_performance = {}
    
    for p in papers:
        total_points = 0
        for score in p.scores:
            pts = score.points_awarded or 0
            total_points += pts
            
            q = all_questions.get((p.exam_id, score.question_number))
            if q and q.topic:
                if q.topic not in topic_performance:
                    topic_performance[q.topic] = {"earned": 0, "max": 0}
                topic_performance[q.topic]["earned"] += pts
                topic_performance[q.topic]["max"] += q.max_points
                
        history.append({
            "exam_id": p.exam_id,
            "course": p.exam.course_code if p.exam else "Unknown",
            "date": str(p.created_at) if p.created_at else None,
            "score": total_points
        })
        
    return {
        "student": {"number": student.student_number, "name": student.name, "email": student.email},
        "history": history,
        "topic_performance": topic_performance
    }

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

def calculate_layout_json(metadata: ExamMetadata, exam_id: str) -> dict:
    """Calculates all absolute PDF coordinates beforehand and packages them into a JSON dict."""
    layout = {"id": exam_id, "qr": [], "sid": [], "q": []}
    
    full_w = A4_WIDTH - (2 * MARGIN)
    LEFT_WIDTH = full_w * 0.60
    RIGHT_WIDTH = full_w * 0.40
    
    start_y = A4_HEIGHT - 70
    header_height = 197
    
    # 1. QR Code
    qr_size = 72
    qr_col_w = LEFT_WIDTH * 0.50
    qr_x = MARGIN + qr_col_w + (qr_col_w - qr_size) / 2
    row1_h = 75
    qr_y_bottom = start_y - row1_h + (row1_h - qr_size) / 2
    qr_y_top = A4_HEIGHT - (qr_y_bottom + qr_size)
    layout["qr"] = [round(qr_x), round(qr_y_top), round(qr_size), round(qr_size)]
    
    # 2. Student ID Box
    sid_x = MARGIN + LEFT_WIDTH
    sid_y_bottom = start_y - header_height
    sid_y_top = A4_HEIGHT - (sid_y_bottom + header_height)
    layout["sid"] = [round(sid_x), round(sid_y_top), round(RIGHT_WIDTH), round(header_height)]
    
    # 3. Question Boxes
    box_w = (full_w - (4 * 3*mm)) / 5
    box_h = 35 * mm
    spacing = 3 * mm
    curr_x = MARGIN
    header_y_end = start_y - header_height
    curr_y = header_y_end - 10*mm
    
    for i in range(metadata.question_count):
        if curr_x + box_w > A4_WIDTH - MARGIN + 1:
            curr_x = MARGIN
            curr_y -= (box_h + 10*mm)
            
        bx = curr_x + 4.0
        by_bottom = curr_y - 20.0 - 4.0 - (box_h - 20.0 - 18.0)
        bw = box_w - 8.0
        bh = box_h - 20.0 - 18.0
        by_top = A4_HEIGHT - (by_bottom + bh)
        
        layout["q"].append([round(bx), round(by_top), round(bw), round(bh)])
        curr_x += box_w + spacing
        
    return layout

# --- PDF DRAWING LOGIC ---

def draw_student_id_section(c, x, y, width, height):
    c.saveState()
    c.setStrokeColor(colors.black); c.setLineWidth(1)
    # The outer rectangle is already drawn by the caller (draw_tabular_header_with_qr)
    
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(x + width/2, y - 12, "STUDENT ID")
    
    cols, box_w, box_h, gap = 10, 12, 14, 3
    total_cols_w = cols * box_w + (cols - 1) * gap
    start_x = x + (width - total_cols_w) / 2
    
    # top_y is where the "box" row starts. 
    # Total content height is roughly 12 (title) + 20 (gap) + 14 (boxes) + 2 (gap) + 135 (OMR) = 183
    # With 197 height, we have some breathing room.
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
            
            # Draw very light digit inside the box
            c.saveState()
            c.setFillColorRGB(0.85, 0.85, 0.85) # Very light grey
            c.setFont("Helvetica", 5) # Smaller font to fit well
            c.drawCentredString(cur_x + omr_box_size/2, cur_y + 2.5, str(j))
            c.restoreState()
    c.restoreState()

def draw_tabular_header_with_qr(c, start_x, start_y, width, info_dict, qr_img_buffer):
    full_w = width - (2 * MARGIN)
    LEFT_WIDTH = full_w * 0.60
    RIGHT_WIDTH = full_w * 0.40
    header_height = 197
    
    # Master Rects
    c.setStrokeColor(colors.black); c.setLineWidth(1)
    c.rect(MARGIN, start_y - header_height, full_w, header_height) # Entire Header
    c.rect(MARGIN, start_y - header_height, LEFT_WIDTH, header_height) # Left Section
    
    curr_y = start_y
    
    # ROW 1: Logo & QR (75 pt)
    row_h = 75
    logo_w = LEFT_WIDTH * 0.50
    c.rect(MARGIN, curr_y - row_h, logo_w, row_h)
    logo_path = "Gemini_Generated_Image_4xrcth4xrcth4xrc.png"
    if os.path.exists(logo_path):
        try:
            from reportlab.lib.utils import ImageReader
            img = Image.open(logo_path)
            img.thumbnail((400, 400), Image.Resampling.LANCZOS)
            logo_buf = io.BytesIO()
            if img.mode in ("RGBA", "P"): img = img.convert("RGB")
            img.save(logo_buf, format="JPEG", quality=85, optimize=True)
            logo_buf.seek(0)
            c.drawImage(ImageReader(logo_buf), MARGIN + 5, curr_y - row_h + 5, 
                        width=logo_w - 10, height=row_h - 10, preserveAspectRatio=True, mask='auto', anchor='c')
        except: pass
        
    qr_w = LEFT_WIDTH * 0.50
    c.rect(MARGIN + logo_w, curr_y - row_h, qr_w, row_h)
    qr_size = 72
    qr_x = MARGIN + logo_w + (qr_w - qr_size) / 2
    qr_y = curr_y - row_h + (row_h - qr_size) / 2
    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(qr_img_buffer), qr_x, qr_y, width=qr_size, height=qr_size)
    curr_y -= row_h
    
    # ROW 2: Exam Type (22 pt)
    row_h = 22
    c.rect(MARGIN, curr_y - row_h, LEFT_WIDTH, row_h)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(MARGIN + LEFT_WIDTH/2, curr_y - 14, "MIDTERM EXAM")
    curr_y -= row_h
    
    # ROWS 3-7: Info Rows (20 pt each)
    row_h = 20
    sig_w = 112.40
    label_w = 63.26
    info_w = LEFT_WIDTH - sig_w - label_w
    
    rows = [
        ("DEPARTMENT", info_dict.get("course_code", "").upper()),
        ("COURSE", info_dict.get("course_name", "").upper()),
        ("DATE", ""),
        ("PERCENTAGE", ""),
        ("NAME & SURNAME", "")
    ]
    
    for i, (label, val) in enumerate(rows):
        is_sig_row = (i == 2 or i == 3) # Row 3 (Date) and Row 4 (Percent)
        current_row_y = curr_y - row_h
        
        # Label Box
        c.rect(MARGIN, current_row_y, label_w, row_h)
        c.setFont("Helvetica-Bold", 6)
        c.drawString(MARGIN + 3, current_row_y + 7, label)
        
        v_rect_w = LEFT_WIDTH - label_w
        if is_sig_row:
            v_rect_w = info_w
            if i == 2: # Draw Signature box spanning two rows (3 & 4)
                c.rect(MARGIN + label_w + info_w, current_row_y - row_h, sig_w, row_h * 2)
                # Text "SIGNATURE" removed as requested to be transparent
        
        # Value Box
        c.rect(MARGIN + label_w, current_row_y, v_rect_w, row_h)
        c.setFont("Helvetica", 7)
        c.drawString(MARGIN + label_w + 5, current_row_y + 7, val)
        curr_y -= row_h
        
    draw_student_id_section(c, MARGIN + LEFT_WIDTH, start_y, RIGHT_WIDTH, header_height)
    return start_y - header_height

def draw_question_box(c, x, y, w, h, q_num, max_points):
    c.rect(x, y - h, w, h); c.line(x, y - 20, x + w, y - 20)
    c.setFont("Helvetica-Bold", 9); c.drawCentredString(x + (w/2), y - 13, f"Q{q_num} ({max_points}p)")
    box_w, box_h = w - 8.0, h - 20.0 - 18.0; bx, by = x + 4.0, y - 20.0 - 4.0 - box_h
    c.saveState(); c.setStrokeColor(colors.lightgrey); c.roundRect(bx, by, box_w, box_h, 4.0, stroke=1, fill=0); c.restoreState()
    c.setFont("Helvetica", 6); c.drawCentredString(bx + (box_w/2), by - 6, f"0-{max_points}")

# --- ENDPOINTS ---

@app.post("/api/generate-cover", response_model=ExamCoverResponse)
async def generate_cover_endpoint(metadata: ExamMetadata, db: Session = Depends(get_db)):
    try:
        exam_id = f"{metadata.course_code}-{str(uuid.uuid4())[:8]}"
        
        # 1. Pre-calculate layout
        layout_json_dict = calculate_layout_json(metadata, exam_id)
        
        # Instead of embedding all data, embed ONLY the exam_id to keep the QR code simple and low resolution
        qr_data_str = exam_id
        
        # Save the full layout structure exactly into the Database
        layout_data = layout_json_dict
        
        # 3. Generate PDF
        buffer = io.BytesIO(); c = canvas.Canvas(buffer, pagesize=A4)
        qr = qrcode.QRCode(box_size=4, border=0)
        qr.add_data(qr_data_str); qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_buf = io.BytesIO(); qr_img.save(qr_buf, format="PNG"); qr_buf.seek(0)
        
        header_y = draw_tabular_header_with_qr(c, MARGIN, A4_HEIGHT - MARGIN, A4_WIDTH, metadata.dict(), qr_buf)
        full_w = A4_WIDTH - (2 * MARGIN)
        box_w, box_h, spacing = (full_w - (4 * 3*mm)) / 5, 35*mm, 3*mm
        curr_x, curr_y = MARGIN, header_y - 10*mm
        for i in range(metadata.question_count):
            if curr_x + box_w > A4_WIDTH - MARGIN + 1: curr_x, curr_y = MARGIN, curr_y - (box_h + 10*mm)
            q_max = metadata.questions_data[i].max_points if i < len(metadata.questions_data) else 10
            draw_question_box(c, curr_x, curr_y, box_w, box_h, i+1, q_max)
            curr_x += box_w + spacing
            
        c.showPage(); c.save(); buffer.seek(0)
        
        db_exam = models.Exam(id=exam_id, course_code=metadata.course_code, course_name=metadata.course_name, instructor_name=metadata.instructor_name, question_count=metadata.question_count, layout_data=layout_data)
        db.add(db_exam); db.commit(); db.refresh(db_exam)
        
        for i in range(metadata.question_count):
            topic = "General"
            max_p = 10
            string_tag = ""
            if i < len(metadata.questions_data):
                topic = metadata.questions_data[i].topic
                max_p = metadata.questions_data[i].max_points
                string_tag = metadata.questions_data[i].string_tag
            db_question = models.Question(exam_id=exam_id, question_number=i+1, topic=topic, max_points=max_p, string_tag=string_tag)
            db.add(db_question)
        db.commit()
        
        return ExamCoverResponse(exam_id=exam_id, layout_data=layout_data, pdf_base64=base64.b64encode(buffer.read()).decode("utf-8"))
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scan-paper")
async def scan_paper(file: UploadFile = File(...), db: Session = Depends(get_db)):
    image = await process_upload_to_image(file)
    if image is None: raise HTTPException(status_code=400, detail="Invalid image or PDF file")
    
    # 1. Automatic QR Code Detection and Parsing
    qr_data, qr_points = reader.detect_qr_code(image)
    if not qr_data: raise HTTPException(status_code=400, detail="Could not read QR code. Ensure it is clearly visible.")
    
    exam_id = qr_data
    
    db_exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not db_exam: raise HTTPException(status_code=404, detail=f"Exam layout not found for ID: {exam_id}")
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    annotated = image.copy()
    
    qr_layout = db_exam.layout_data
    
    # 2. Compute Perspective Transform Matrix (M)
    M = None
    if qr_layout and "qr" in qr_layout and qr_points is not None and qr_points.shape == (1, 4, 2):
        img_pts = qr_points[0].astype(np.float32)
        
        # Order points: TL, TR, BR, BL
        s = img_pts.sum(axis=1)
        d = np.diff(img_pts, axis=1)
        ordered_img_pts = np.zeros((4, 2), dtype=np.float32)
        ordered_img_pts[0] = img_pts[np.argmin(s)] # TL
        ordered_img_pts[2] = img_pts[np.argmax(s)] # BR
        ordered_img_pts[1] = img_pts[np.argmin(d)] # TR
        ordered_img_pts[3] = img_pts[np.argmax(d)] # BL
        
        px, py, pw, ph = qr_layout["qr"]
        pdf_pts = np.float32([
            [px, py],
            [px + pw, py],
            [px + pw, py + ph],
            [px, py + ph]
        ])
        M = cv2.getPerspectiveTransform(pdf_pts, ordered_img_pts)

    def get_mapped_box(pdf_box):
        """Applies matrix M to a PDF box to get its physical Image pixel coordinates."""
        if M is None:
            return {"x": int(pdf_box[0]), "y": int(pdf_box[1]), "width": int(pdf_box[2]), "height": int(pdf_box[3])}
        x, y, w, h = pdf_box
        pts = np.float32([[[x, y]], [[x + w, y]], [[x + w, y + h]], [[x, y + h]]])
        mapped = cv2.perspectiveTransform(pts, M).reshape(-1, 2)
        min_x, min_y = np.min(mapped, axis=0)
        max_x, max_y = np.max(mapped, axis=0)
        return {"x": int(min_x), "y": int(min_y), "width": int(max_x - min_x), "height": int(max_y - min_y)}

    # 3. Process Student ID (Hybrid OMR)
    sid_pdf_box = qr_layout["sid"]
    sid_box = get_mapped_box(sid_pdf_box)
    
    cv2.rectangle(annotated, (sid_box["x"], sid_box["y"]), 
                  (sid_box["x"] + sid_box["width"], sid_box["y"] + sid_box["height"]), (255, 0, 0), 2)
    
    luma_refs = {"white": np.percentile(gray, 95), "black": np.percentile(gray, 5), "grey": np.mean(gray)}
    
    student_id, cols, rows = "", 10, 10
    # --- PIXEL PERFECT OMR GEOMETRY ---
    scale_ratio = sid_box["width"] / sid_pdf_box[2] if sid_pdf_box[2] > 0 else 1.0
    pdf_left_offset = (sid_pdf_box[2] - 147) / 2 # Center the 147pt grid inside the box
    
    for c in range(cols):
        col_scores = []
        # Calculate center X for this column in PDF points first, then scale
        # col_start = left_offset + c * (box_w + gap) + (box_w - bubble_size)/2
        # center_x = col_start + bubble_size/2 = left_offset + c*15 + 6
        pdf_cx = pdf_left_offset + (c * 15) + 6
        cx_pixels = int(sid_box["x"] + (pdf_cx * scale_ratio))
        
        for r in range(rows):
            # Calculate center Y for this row in PDF points (top offset is 34)
            # row_center = top_offset + (r+1)*13.5 - 4.5
            pdf_cy = 34 + ((r + 1) * 13.5) - 4.5
            cy_pixels = int(sid_box["y"] + (pdf_cy * scale_ratio))
            
            scan_radius = int(4.5 * scale_ratio) # 45% of 10pt approx
            
            bubble_res = reader.scan_omr_circle(gray, cx_pixels, cy_pixels, scan_radius, luma_refs)
            col_scores.append({
                "digit": r, 
                "score": bubble_res["score"], 
                "center": bubble_res["adj_center"],
                "radius": scan_radius
            })
            
            # Visual Debug: Tiny Red dot for EXACT grid center
            cv2.circle(annotated, (cx_pixels, cy_pixels), 1, (0, 0, 255), -1)
        
        # Decision Logic (The Secret Sauce)
        col_scores.sort(key=lambda x: x["score"], reverse=True)
        top1 = col_scores[0]
        top2 = col_scores[1]
        
        picked_digit = "?"
        if top1["score"] > 0.30: # Base Threshold
            picked_digit = str(top1["digit"])
            # --- Visual Debug: Green circle for PICKED digit ---
            adj_cx, adj_cy = int(top1["center"][0]), int(top1["center"][1])
            cv2.circle(annotated, (adj_cx, adj_cy), top1["radius"], (0, 255, 0), 2)
        elif 0.22 <= top1["score"] <= 0.30: # Light Threshold
            if (top1["score"] - top2["score"]) > 0.12: # Significant Gap
                picked_digit = str(top1["digit"])
                # --- Visual Debug: Green circle for PICKED digit ---
                adj_cx, adj_cy = int(top1["center"][0]), int(top1["center"][1])
                cv2.circle(annotated, (adj_cx, adj_cy), top1["radius"], (0, 255, 0), 2)
        
        student_id += picked_digit

    cv2.putText(annotated, f"ID: {student_id}", (sid_box["x"], sid_box["y"] - 10), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)

    # 4. Process Question Scores
    results = []
    
    for i, qbox in enumerate(qr_layout["q"]):
        coords = get_mapped_box(qbox)
        roi = reader.crop_roi_safely(image, coords["x"], coords["y"], coords["width"], coords["height"], margin_pct=0.15)
        # Using the advanced handwriting engine with a default max_points of 10
        score = reader.predict_score(roi, max_points=10)
        results.append({"question": i+1, "score": score})
        
        cv2.rectangle(annotated, (coords["x"], coords["y"]), 
                      (coords["x"] + coords["width"], coords["y"] + coords["height"]), (0, 200, 0), 2)
        cv2.putText(annotated, str(score), (coords["x"] + 5, coords["y"] + 25), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # 5. Save and Return
    result_filename = f"scan_result_{uuid.uuid4()}.jpg"
    result_path = os.path.join(STATIC_DIR, result_filename)
    cv2.imwrite(result_path, annotated)

    # Also encode as base64 for reliable frontend display
    _, img_encoded = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
    annotated_b64 = base64.b64encode(img_encoded.tobytes()).decode('utf-8')

    db_paper = models.ScannedPaper(exam_id=exam_id, student_number=student_id, image_url=f"/static/{result_filename}", status=models.ProcessingStatus.COMPLETED)
    db.add(db_paper); db.commit(); db.refresh(db_paper)
    for res in results:
        db.add(models.Score(scanned_paper_id=db_paper.id, question_number=res["question"], points_awarded=res["score"], confidence_score=1.0))
    db.commit()
    
    return {
        "exam_id": exam_id, 
        "paper_id": db_paper.id, 
        "student_id": student_id, 
        "scores": results,
        "annotated_image_url": f"/static/{result_filename}",
        "annotated_image_base64": annotated_b64
    }

# --- SINAV API'LERİ ---

@app.get("/api/exams/{exam_id}/results")
async def get_exam_results(exam_id: str, db: Session = Depends(get_db)):
    """Sınava giren tüm öğrencilerin detaylı sonuçları (LLM beslemesi için tasarlanmıştır)."""
    from sqlalchemy.orm import joinedload
    
    db_exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not db_exam:
        raise HTTPException(status_code=404, detail=f"Exam not found: {exam_id}")
    
    # Soruları çek
    questions = db.query(models.Question).filter(models.Question.exam_id == exam_id).order_by(models.Question.question_number).all()
    questions_list = [
        {
            "question_number": q.question_number,
            "topic": q.topic,
            "max_points": q.max_points,
            "string_tag": q.string_tag or ""
        }
        for q in questions
    ]
    
    # Question lookup for fast access
    q_map = {q.question_number: q for q in questions}
    total_max = sum(q.max_points for q in questions)
    
    # Tüm kağıtları ve skorları çek
    papers = db.query(models.ScannedPaper).options(
        joinedload(models.ScannedPaper.scores),
        joinedload(models.ScannedPaper.student)
    ).filter(models.ScannedPaper.exam_id == exam_id).all()
    
    students_list = []
    all_totals = []
    
    for p in papers:
        student_scores = []
        student_total = 0
        for score in sorted(p.scores, key=lambda s: s.question_number):
            pts = score.points_awarded or 0
            student_total += pts
            q = q_map.get(score.question_number)
            student_scores.append({
                "question_number": score.question_number,
                "points_awarded": pts,
                "max_points": q.max_points if q else 10,
                "string_tag": (q.string_tag or "") if q else "",
                "topic": (q.topic or "") if q else ""
            })
        
        all_totals.append(student_total)
        students_list.append({
            "student_number": p.student_number or "Unknown",
            "name": p.student.name if p.student else None,
            "email": p.student.email if p.student else None,
            "total_score": student_total,
            "total_max": total_max,
            "percentage": round((student_total / total_max * 100), 1) if total_max > 0 else 0,
            "scores": student_scores
        })
    
    # Sınıf istatistikleri
    class_stats = {}
    if all_totals:
        class_stats = {
            "student_count": len(all_totals),
            "average_score": round(sum(all_totals) / len(all_totals), 1),
            "average_percentage": round(sum(all_totals) / len(all_totals) / total_max * 100, 1) if total_max > 0 else 0,
            "max_score": max(all_totals),
            "min_score": min(all_totals)
        }
    
    return {
        "exam_id": db_exam.id,
        "course_code": db_exam.course_code,
        "course_name": db_exam.course_name,
        "instructor_name": db_exam.instructor_name,
        "question_count": db_exam.question_count,
        "questions": questions_list,
        "students": students_list,
        "class_stats": class_stats
    }


@app.get("/api/students/{student_number}/exam-results")
async def get_student_exam_results(student_number: str, db: Session = Depends(get_db)):
    """Öğrencinin girdiği tüm sınavların detaylı sonuçları (soru bazında puan + string_tag)."""
    from sqlalchemy.orm import joinedload
    
    student = db.query(models.Student).filter(models.Student.student_number == student_number).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"Student not found: {student_number}")
    
    papers = db.query(models.ScannedPaper).options(
        joinedload(models.ScannedPaper.scores),
        joinedload(models.ScannedPaper.exam)
    ).filter(models.ScannedPaper.student_number == student_number).all()
    
    # Batch-load tüm ilgili soruları
    exam_ids = list(set(p.exam_id for p in papers))
    q_map = {}
    if exam_ids:
        questions = db.query(models.Question).filter(models.Question.exam_id.in_(exam_ids)).all()
        for q in questions:
            q_map[(q.exam_id, q.question_number)] = q
    
    exams_list = []
    all_percentages = []
    string_tag_perf = {}  # string_tag → {earned, max, count}
    
    for p in papers:
        exam_scores = []
        paper_total = 0
        paper_max = 0
        
        for score in sorted(p.scores, key=lambda s: s.question_number):
            pts = score.points_awarded or 0
            q = q_map.get((p.exam_id, score.question_number))
            max_p = q.max_points if q else 10
            tag = (q.string_tag or "") if q else ""
            topic = (q.topic or "") if q else ""
            
            paper_total += pts
            paper_max += max_p
            
            exam_scores.append({
                "question_number": score.question_number,
                "points_awarded": pts,
                "max_points": max_p,
                "string_tag": tag,
                "topic": topic
            })
            
            # String tag performans takibi
            if tag:
                if tag not in string_tag_perf:
                    string_tag_perf[tag] = {"total_earned": 0, "total_max": 0, "appearances": 0}
                string_tag_perf[tag]["total_earned"] += pts
                string_tag_perf[tag]["total_max"] += max_p
                string_tag_perf[tag]["appearances"] += 1
        
        pct = round((paper_total / paper_max * 100), 1) if paper_max > 0 else 0
        all_percentages.append(pct)
        
        exams_list.append({
            "exam_id": p.exam_id,
            "course_code": p.exam.course_code if p.exam else "Unknown",
            "course_name": p.exam.course_name if p.exam else "Unknown",
            "date": str(p.created_at) if p.created_at else None,
            "total_score": paper_total,
            "total_max": paper_max,
            "percentage": pct,
            "scores": exam_scores
        })
    
    # String tag performanslarına yüzde ekle
    for tag, perf in string_tag_perf.items():
        perf["percentage"] = round((perf["total_earned"] / perf["total_max"] * 100), 1) if perf["total_max"] > 0 else 0
    
    return {
        "student": {
            "student_number": student.student_number,
            "name": student.name,
            "email": student.email
        },
        "total_exams": len(exams_list),
        "overall_average_percentage": round(sum(all_percentages) / len(all_percentages), 1) if all_percentages else 0,
        "exams": exams_list,
        "string_tag_performance": string_tag_perf
    }


@app.post("/predict")
async def predict_handwriting(file: UploadFile = File(...), max_points: int = 100):
    """Predicts score from a single snippet using the integrated advanced handwriting engine."""
    image = await process_upload_to_image(file)
    if image is None: raise HTTPException(status_code=400, detail="Invalid image or PDF file")
    score = reader.predict_score(image, max_points=max_points)
    return {"score": score}

@app.get("/api/predict/status")
async def predict_status():
    return {"status": "running", "engine": reader.hw_recognizer.engine}

# --- LOCAL REPORT GENERATION ENDPOINTS ---

@app.post("/api/students/{student_number}/ai-report")
async def generate_student_ai_report(student_number: str, body: Optional[AIStudentReportRequest] = None, db: Session = Depends(get_db)):
    """Öğrenci özelinde yerel (programatik) rapor + quiz üretir."""
    print(f"[Report] Generating student report for {student_number}...")
    from sqlalchemy.orm import joinedload
    
    if body is None:
        body = AIStudentReportRequest()
    
    student = db.query(models.Student).filter(models.Student.student_number == student_number).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"Student not found: {student_number}")
    
    papers = db.query(models.ScannedPaper).options(
        joinedload(models.ScannedPaper.scores),
        joinedload(models.ScannedPaper.exam)
    ).filter(models.ScannedPaper.student_number == student_number).all()
    
    if not papers:
        raise HTTPException(status_code=404, detail="Bu öğrencinin sınav verisi bulunamadı.")
    
    # Batch-load questions
    exam_ids = list(set(p.exam_id for p in papers))
    q_map = {}
    if exam_ids:
        questions = db.query(models.Question).filter(models.Question.exam_id.in_(exam_ids)).all()
        for q in questions:
            q_map[(q.exam_id, q.question_number)] = q
    
    exams_list = []
    all_percentages = []
    string_tag_perf = {}
    
    for p in papers:
        exam_scores = []
        paper_total = 0
        paper_max = 0
        
        for score in sorted(p.scores, key=lambda s: s.question_number):
            pts = score.points_awarded or 0
            q = q_map.get((p.exam_id, score.question_number))
            max_p = q.max_points if q else 10
            tag = (q.string_tag or "") if q else ""
            topic = (q.topic or "") if q else ""
            
            paper_total += pts
            paper_max += max_p
            
            exam_scores.append({
                "question_number": score.question_number,
                "points_awarded": pts,
                "max_points": max_p,
                "string_tag": tag,
                "topic": topic
            })
            
            if tag:
                if tag not in string_tag_perf:
                    string_tag_perf[tag] = {"total_earned": 0, "total_max": 0, "appearances": 0}
                string_tag_perf[tag]["total_earned"] += pts
                string_tag_perf[tag]["total_max"] += max_p
                string_tag_perf[tag]["appearances"] += 1
        
        pct = round((paper_total / paper_max * 100), 1) if paper_max > 0 else 0
        all_percentages.append(pct)
        
        exams_list.append({
            "exam_id": p.exam_id,
            "course_code": p.exam.course_code if p.exam else "Unknown",
            "course_name": p.exam.course_name if p.exam else "Unknown",
            "date": str(p.created_at) if p.created_at else None,
            "total_score": paper_total,
            "total_max": paper_max,
            "percentage": pct,
            "scores": exam_scores
        })
    
    for tag, perf in string_tag_perf.items():
        perf["percentage"] = round((perf["total_earned"] / perf["total_max"] * 100), 1) if perf["total_max"] > 0 else 0
    
    llm_input = {
        "student": {
            "student_number": student.student_number,
            "name": student.name,
            "email": student.email
        },
        "overall_average_percentage": round(sum(all_percentages) / len(all_percentages), 1) if all_percentages else 0,
        "total_exams": len(exams_list),
        "exams": exams_list,
        "string_tag_performance": string_tag_perf
    }
    
    result = generate_local_student_report(llm_input, include_quiz=body.include_quiz)
    
    return {
        "student_number": student.student_number,
        "student_name": student.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report": result.get("report", {}),
        "quiz": result.get("quiz", []) if body.include_quiz else None,
        "html_report": result.get("html_report", "")
    }


@app.post("/api/exams/{exam_id}/ai-report")
async def generate_class_ai_report(exam_id: str, body: Optional[AIClassReportRequest] = None, db: Session = Depends(get_db)):
    """Sınıf geneli yerel (programatik) rapor üretir."""
    print(f"[Report] Generating class report for exam {exam_id}...")
    from sqlalchemy.orm import joinedload
    
    if body is None:
        body = AIClassReportRequest()
    
    db_exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    if not db_exam:
        raise HTTPException(status_code=404, detail=f"Exam not found: {exam_id}")
    
    questions = db.query(models.Question).filter(models.Question.exam_id == exam_id).order_by(models.Question.question_number).all()
    q_map = {q.question_number: q for q in questions}
    total_max = sum(q.max_points for q in questions)
    
    papers = db.query(models.ScannedPaper).options(
        joinedload(models.ScannedPaper.scores),
        joinedload(models.ScannedPaper.student)
    ).filter(models.ScannedPaper.exam_id == exam_id).all()
    
    if not papers:
        raise HTTPException(status_code=404, detail="Bu sınava ait taranmış kağıt bulunamadı.")
    
    students_data = []
    for p in papers:
        student_scores = []
        student_total = 0
        for score in sorted(p.scores, key=lambda s: s.question_number):
            pts = score.points_awarded or 0
            student_total += pts
            q = q_map.get(score.question_number)
            student_scores.append({
                "question_number": score.question_number,
                "points_awarded": pts,
                "max_points": q.max_points if q else 10,
                "string_tag": (q.string_tag or "") if q else "",
                "topic": (q.topic or "") if q else ""
            })
        
        students_data.append({
            "student_number": p.student_number or "Unknown",
            "name": p.student.name if p.student else None,
            "total_score": student_total,
            "total_max": total_max,
            "percentage": round((student_total / total_max * 100), 1) if total_max > 0 else 0,
            "scores": student_scores
        })
    
    llm_input = {
        "exam_id": db_exam.id,
        "course_code": db_exam.course_code,
        "course_name": db_exam.course_name,
        "instructor_name": db_exam.instructor_name,
        "question_count": db_exam.question_count,
        "questions": [
            {"question_number": q.question_number, "topic": q.topic, "max_points": q.max_points, "string_tag": q.string_tag or ""}
            for q in questions
        ],
        "students": students_data
    }
    
    result = generate_local_class_report(llm_input)
    
    return {
        "exam_id": db_exam.id,
        "course_code": db_exam.course_code,
        "course_name": db_exam.course_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report": result.get("report", {})
    }


@app.get("/report", response_class=HTMLResponse)
async def get_report_page():
    if not os.path.exists("report.html"):
        raise HTTPException(status_code=404, detail="report.html not found")
    with open("report.html", "r") as f:
        return f.read()


