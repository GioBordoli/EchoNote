import os
import uuid
from datetime import datetime, date
from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime, Date, ForeignKey, CheckConstraint, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.dialects.postgresql import UUID
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

Base = declarative_base()

# Database Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to transcripts
    transcripts = relationship("Transcript", back_populates="user", cascade="all, delete-orphan")
    usage = relationship("Usage", back_populates="user", cascade="all, delete-orphan")

class Transcript(Base):
    __tablename__ = "transcripts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    language = Column(String(2), nullable=False)
    original_filename = Column(String)
    gcs_uri = Column(String)
    status = Column(String, CheckConstraint("status IN ('pending','processing','done','error')"), default='pending')
    duration_seconds = Column(Integer)
    speaker_count = Column(Integer)
    transcript_text = Column(Text)
    summary_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # Relationship to user
    user = relationship("User", back_populates="transcripts")

class Usage(Base):
    __tablename__ = "usage"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    period_start = Column(Date, primary_key=True)
    seconds_transcribed = Column(Integer, default=0)
    
    # Relationship to user
    user = relationship("User", back_populates="usage")

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/meeting_transcription")
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper functions
def get_user_by_email(db: Session, email: str):
    """Get user by email"""
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, email: str, password_hash: str):
    """Create a new user"""
    user = User(email=email, password_hash=password_hash)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_transcript_by_id(db: Session, transcript_id: str, user_id: str):
    """Get transcript by ID for a specific user"""
    return db.query(Transcript).filter(
        Transcript.id == transcript_id,
        Transcript.user_id == user_id
    ).first()

def get_user_transcripts(db: Session, user_id: str):
    """Get all transcripts for a user"""
    return db.query(Transcript).filter(Transcript.user_id == user_id).all()

def create_transcript(db: Session, user_id: str, language: str, original_filename: str, gcs_uri: str):
    """Create a new transcript record"""
    transcript = Transcript(
        user_id=user_id,
        language=language,
        original_filename=original_filename,
        gcs_uri=gcs_uri,
        status='pending'
    )
    db.add(transcript)
    db.commit()
    db.refresh(transcript)
    return transcript

def update_transcript_status(db: Session, transcript_id: str, status: str, **kwargs):
    """Update transcript status and other fields"""
    transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
    if transcript:
        transcript.status = status
        for key, value in kwargs.items():
            if hasattr(transcript, key):
                setattr(transcript, key, value)
        if status == 'done':
            transcript.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(transcript)
    return transcript

def update_usage(db: Session, user_id: str, seconds_transcribed: int):
    """Update or create usage record for the current period"""
    today = date.today()
    # Get first day of current month
    period_start = today.replace(day=1)
    
    usage = db.query(Usage).filter(
        Usage.user_id == user_id,
        Usage.period_start == period_start
    ).first()
    
    if usage:
        usage.seconds_transcribed += seconds_transcribed
    else:
        usage = Usage(
            user_id=user_id,
            period_start=period_start,
            seconds_transcribed=seconds_transcribed
        )
        db.add(usage)
    
    db.commit()
    db.refresh(usage)
    return usage
