import os
import tempfile
import logging
from google.cloud import speech_v1 as speech
from google.cloud import storage
from pydub import AudioSegment
from pydub.silence import split_on_silence
import io
from typing import List, Dict, Any
import uuid

logger = logging.getLogger(__name__)

# Initialize Google Cloud clients
speech_client = speech.SpeechClient()
storage_client = storage.Client()

# Configuration
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "meeting-transcription-audio")
MAX_CHUNK_DURATION_MS = 5 * 60 * 1000  # 5 minutes in milliseconds

def upload_audio_to_gcs(audio_file, filename: str) -> str:
    """Upload audio file to Google Cloud Storage"""
    try:
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob_name = f"audio/{uuid.uuid4()}/{filename}"
        blob = bucket.blob(blob_name)
        
        # Reset file pointer and upload
        audio_file.seek(0)
        blob.upload_from_file(audio_file, content_type="audio/mpeg")
        
        gcs_uri = f"gs://{GCS_BUCKET_NAME}/{blob_name}"
        logger.info(f"Audio uploaded to GCS: {gcs_uri}")
        return gcs_uri
        
    except Exception as e:
        logger.error(f"Failed to upload audio to GCS: {str(e)}")
        raise

def convert_and_split_audio(audio_file) -> List[bytes]:
    """Convert audio to FLAC and split into chunks"""
    try:
        # Load audio file
        audio_file.seek(0)
        audio = AudioSegment.from_file(audio_file)
        
        # Convert to FLAC format
        audio = audio.set_frame_rate(16000).set_channels(1)
        
        # Split into chunks if longer than max duration
        chunks = []
        if len(audio) <= MAX_CHUNK_DURATION_MS:
            # Audio is short enough, use as single chunk
            buffer = io.BytesIO()
            audio.export(buffer, format="flac")
            chunks.append(buffer.getvalue())
        else:
            # Split on silence
            audio_chunks = split_on_silence(
                audio,
                min_silence_len=1000,  # 1 second
                silence_thresh=audio.dBFS - 14,
                keep_silence=500  # 0.5 second
            )
            
            # Group chunks to stay under max duration
            current_chunk = AudioSegment.empty()
            for chunk in audio_chunks:
                if len(current_chunk) + len(chunk) <= MAX_CHUNK_DURATION_MS:
                    current_chunk += chunk
                else:
                    if len(current_chunk) > 0:
                        buffer = io.BytesIO()
                        current_chunk.export(buffer, format="flac")
                        chunks.append(buffer.getvalue())
                    current_chunk = chunk
            
            # Add remaining chunk
            if len(current_chunk) > 0:
                buffer = io.BytesIO()
                current_chunk.export(buffer, format="flac")
                chunks.append(buffer.getvalue())
        
        logger.info(f"Audio split into {len(chunks)} chunks")
        return chunks
        
    except Exception as e:
        logger.error(f"Failed to process audio: {str(e)}")
        raise

def transcribe_audio_chunk(audio_chunk: bytes, language: str) -> Dict[str, Any]:
    """Transcribe a single audio chunk with speaker diarization"""
    try:
        # Configure recognition
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.FLAC,
            sample_rate_hertz=16000,
            language_code=language,
            enable_speaker_diarization=True,
            diarization_speaker_count_min=1,
            diarization_speaker_count_max=10,
            enable_automatic_punctuation=True,
            model="video"  # Use video model for better diarization
        )
        
        audio = speech.RecognitionAudio(content=audio_chunk)
        
        # Perform transcription
        operation = speech_client.long_running_recognize(config=config, audio=audio)
        response = operation.result(timeout=900)  # 15 minutes timeout
        
        # Process results
        segments = []
        speaker_count = 0
        
        for result in response.results:
            alternative = result.alternatives[0]
            
            # Extract speaker-tagged segments
            for word_info in alternative.words:
                speaker_tag = word_info.speaker_tag
                if speaker_tag > speaker_count:
                    speaker_count = speaker_tag
                
                segments.append({
                    "word": word_info.word,
                    "start_time": word_info.start_time.total_seconds(),
                    "end_time": word_info.end_time.total_seconds(),
                    "speaker": speaker_tag
                })
        
        return {
            "segments": segments,
            "speaker_count": speaker_count,
            "transcript": " ".join([seg["word"] for seg in segments])
        }
        
    except Exception as e:
        logger.error(f"Failed to transcribe audio chunk: {str(e)}")
        raise

def merge_transcript_chunks(chunks_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge transcription results from multiple chunks"""
    try:
        all_segments = []
        total_duration = 0
        max_speaker_count = 0
        
        for chunk_result in chunks_results:
            # Adjust timing offsets for each chunk
            for segment in chunk_result["segments"]:
                segment["start_time"] += total_duration
                segment["end_time"] += total_duration
                all_segments.append(segment)
            
            if chunk_result["segments"]:
                total_duration = max(seg["end_time"] for seg in chunk_result["segments"])
            
            max_speaker_count = max(max_speaker_count, chunk_result["speaker_count"])
        
        # Group segments by speaker and time
        transcript_text = ""
        current_speaker = None
        
        for segment in sorted(all_segments, key=lambda x: x["start_time"]):
            if segment["speaker"] != current_speaker:
                if current_speaker is not None:
                    transcript_text += "\n"
                transcript_text += f"Speaker {segment['speaker']}: "
                current_speaker = segment["speaker"]
            transcript_text += segment["word"] + " "
        
        return {
            "transcript_text": transcript_text.strip(),
            "speaker_count": max_speaker_count,
            "duration_seconds": int(total_duration)
        }
        
    except Exception as e:
        logger.error(f"Failed to merge transcript chunks: {str(e)}")
        raise

async def transcribe_audio_file(audio_file, language: str, original_filename: str) -> Dict[str, Any]:
    """Main function to transcribe an audio file"""
    try:
        logger.info(f"Starting transcription for file: {original_filename}")
        
        # Upload to GCS
        gcs_uri = upload_audio_to_gcs(audio_file, original_filename)
        
        # Convert and split audio
        audio_chunks = convert_and_split_audio(audio_file)
        
        # Transcribe each chunk
        chunk_results = []
        for i, chunk in enumerate(audio_chunks):
            logger.info(f"Transcribing chunk {i+1}/{len(audio_chunks)}")
            result = transcribe_audio_chunk(chunk, language)
            chunk_results.append(result)
        
        # Merge results
        final_result = merge_transcript_chunks(chunk_results)
        final_result["gcs_uri"] = gcs_uri
        
        logger.info(f"Transcription completed for {original_filename}")
        return final_result
        
    except Exception as e:
        logger.error(f"Transcription failed for {original_filename}: {str(e)}")
        raise
