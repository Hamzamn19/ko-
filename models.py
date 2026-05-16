import enum
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class ProcessingStatus(str, enum.Enum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    NEEDS_REVIEW = "NEEDS_REVIEW"

class Student(Base):
    __tablename__ = "students"
    
    student_number = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    papers = relationship("ScannedPaper", back_populates="student")

class Exam(Base):
    __tablename__ = "exams"

    id = Column(String, primary_key=True, index=True)
    course_code = Column(String, index=True)
    course_name = Column(String)
    instructor_name = Column(String)
    question_count = Column(Integer)
    layout_data = Column(JSON)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    scanned_papers = relationship("ScannedPaper", back_populates="exam")
    questions = relationship("Question", back_populates="exam", cascade="all, delete-orphan")

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(String, ForeignKey("exams.id"))
    question_number = Column(Integer)
    topic = Column(String, nullable=True)
    max_points = Column(Integer, default=10)

    exam = relationship("Exam", back_populates="questions")

class ScannedPaper(Base):
    __tablename__ = "scanned_papers"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(String, ForeignKey("exams.id"))
    student_number = Column(String, ForeignKey("students.student_number"), nullable=True, index=True)
    image_url = Column(String)
    status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PROCESSING)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    exam = relationship("Exam", back_populates="scanned_papers")
    student = relationship("Student", back_populates="papers")
    scores = relationship("Score", back_populates="scanned_paper")

class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, index=True)
    scanned_paper_id = Column(Integer, ForeignKey("scanned_papers.id"))
    question_number = Column(Integer, index=True)
    points_awarded = Column(Integer, nullable=True)
    confidence_score = Column(Float)
    
    scanned_paper = relationship("ScannedPaper", back_populates="scores")
