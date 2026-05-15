import enum
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class ProcessingStatus(str, enum.Enum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    NEEDS_REVIEW = "NEEDS_REVIEW"

class Exam(Base):
    __tablename__ = "exams"

    # We use the generated Unique Exam ID (e.g., PHY6202-a1b2c3d4) as the primary key
    id = Column(String, primary_key=True, index=True)
    course_code = Column(String, index=True)
    course_name = Column(String)
    instructor_name = Column(String)
    question_count = Column(Integer)
    layout_data = Column(JSON) # Stores the top-left coordinates mapped during Phase 1
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    scanned_papers = relationship("ScannedPaper", back_populates="exam")

class ScannedPaper(Base):
    __tablename__ = "scanned_papers"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(String, ForeignKey("exams.id"))
    student_number = Column(String, nullable=True, index=True) # Populated by Puq.ai
    image_url = Column(String)
    status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PROCESSING)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    exam = relationship("Exam", back_populates="scanned_papers")
    scores = relationship("Score", back_populates="scanned_paper")

class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, index=True)
    scanned_paper_id = Column(Integer, ForeignKey("scanned_papers.id"))
    
    # This specifically enables individual question statistics (e.g., success rate for Q3)
    question_number = Column(Integer, index=True)
    points_awarded = Column(Integer, nullable=True) # Nullable in case of NEED_REVIEW
    confidence_score = Column(Float) # The confidence level returned from Puq.ai
    
    # Relationships
    scanned_paper = relationship("ScannedPaper", back_populates="scores")
