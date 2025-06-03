# main.py
from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, status, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import uuid
import logging
import os
from datetime import datetime

# Local imports
from database import (
    get_db, create_tables, User, Transcript,
    get_user_transcripts, get_transcript_by_id,
    create_transcript, update_transcript_status, update_usage
)
from auth import auth_router, get_current_user
from transcriber import transcribe_audio_file
from summarizer import generate_summary_and_action_items

# Setup logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Meeting Transcription API",
    description="Backend API for meeting transcription with speaker diarization",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for responses
class TranscriptListItem(BaseModel):
    id: str
    original_filename: str
    language: str
    status: str
    duration_seconds: Optional[int]
    speaker_count: Optional[int]
    created_at: datetime
    completed_at: Optional[datetime]

class TranscriptDetail(BaseModel):
    id: str
    original_filename: str
    language: str
    status: str
    duration_seconds: Optional[int]
    speaker_count: Optional[int]
    transcript_text: Optional[str]
    summary_text: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

class AudioUploadResponse(BaseModel):
    job_id: str
    message: str

# Create database tables on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database tables"""
    try:
        create_tables()
        logger.info("Application started successfully")
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        raise

# Health check endpoint
@app.get("/", tags=["health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "Meeting Transcription API is running",
        "timestamp": datetime.utcnow().isoformat()
    }

# Background task for processing audio
async def process_audio_background(
    transcript_id: str,
    audio_file_content: bytes,
    original_filename: str,
    language: str,
    db_session: Session
):
    """Background task to process audio transcription"""
    try:
        logger.info(f"Starting background processing for transcript {transcript_id}")
        
        # Update status to processing
        update_transcript_status(db_session, transcript_id, "processing")
        
        # Create a temporary file-like object from bytes
        import io
        audio_file = io.BytesIO(audio_file_content)
        
        # Transcribe audio
        result = await transcribe_audio_file(audio_file, language, original_filename)
        
        # Generate summary
        summary_result = await generate_summary_and_action_items(
            result["transcript_text"], language
        )
        
        # Update transcript with results
        update_transcript_status(
            db_session,
            transcript_id,
            "done",
            transcript_text=result["transcript_text"],
            summary_text=summary_result["summary_text"],
            duration_seconds=result["duration_seconds"],
            speaker_count=result["speaker_count"],
            gcs_uri=result["gcs_uri"]
        )
        
        # Update usage statistics
        transcript = db_session.query(Transcript).filter(Transcript.id == transcript_id).first()
        if transcript:
            update_usage(db_session, str(transcript.user_id), result["duration_seconds"])
        
        logger.info(f"Successfully processed transcript {transcript_id}")
        
    except Exception as e:
        logger.error(f"Background processing failed for transcript {transcript_id}: {str(e)}")
        # Update status to error
        update_transcript_status(db_session, transcript_id, "error")

# Include auth router
app.include_router(auth_router)

# Audio upload endpoint
@app.post("/audio", response_model=AudioUploadResponse, tags=["transcription"])
async def upload_audio(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    language: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload audio file for transcription"""
    
    # Validate language
    if language not in ["it", "en"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Language must be 'it' or 'en'"
        )
    
    # Validate file type
    allowed_types = ["audio/mpeg", "audio/mp4", "audio/wav", "audio/flac", "audio/m4a"]
    if audio.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed types: {', '.join(allowed_types)}"
        )
    
    try:
        # Read audio file content
        audio_content = await audio.read()
        
        # Create transcript record
        transcript = create_transcript(
            db,
            str(current_user.id),
            language,
            audio.filename,
            ""  # GCS URI will be updated during processing
        )
        
        # Start background processing
        background_tasks.add_task(
            process_audio_background,
            str(transcript.id),
            audio_content,
            audio.filename,
            language,
            db
        )
        
        logger.info(f"Audio upload initiated for user {current_user.id}, transcript {transcript.id}")
        
        return AudioUploadResponse(
            job_id=str(transcript.id),
            message="Audio upload successful. Transcription started."
        )
        
    except Exception as e:
        logger.error(f"Audio upload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Audio upload failed"
        )

# Get user's transcripts
@app.get("/transcripts", response_model=List[TranscriptListItem], tags=["transcription"])
async def get_transcripts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all transcripts for the current user"""
    try:
        transcripts = get_user_transcripts(db, str(current_user.id))
        
        result = []
        for transcript in transcripts:
            result.append(TranscriptListItem(
                id=str(transcript.id),
                original_filename=transcript.original_filename,
                language=transcript.language,
                status=transcript.status,
                duration_seconds=transcript.duration_seconds,
                speaker_count=transcript.speaker_count,
                created_at=transcript.created_at,
                completed_at=transcript.completed_at
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to retrieve transcripts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve transcripts"
        )

# Get specific transcript
@app.get("/transcripts/{transcript_id}", response_model=TranscriptDetail, tags=["transcription"])
async def get_transcript(
    transcript_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific transcript details"""
    try:
        transcript = get_transcript_by_id(db, transcript_id, str(current_user.id))
        
        if not transcript:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transcript not found"
            )
        
        return TranscriptDetail(
            id=str(transcript.id),
            original_filename=transcript.original_filename,
            language=transcript.language,
            status=transcript.status,
            duration_seconds=transcript.duration_seconds,
            speaker_count=transcript.speaker_count,
            transcript_text=transcript.transcript_text,
            summary_text=transcript.summary_text,
            created_at=transcript.created_at,
            completed_at=transcript.completed_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve transcript {transcript_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve transcript"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
        log_level="info"
    )
