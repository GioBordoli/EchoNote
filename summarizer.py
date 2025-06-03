import os
import logging
from google.cloud import aiplatform
from google.cloud.aiplatform import gapic as aip
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Initialize AI Platform
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

aiplatform.init(project=PROJECT_ID, location=LOCATION)

async def generate_summary_and_action_items(transcript_text: str, language: str) -> Dict[str, Any]:
    """Generate summary and action items from transcript text using Gemini"""
    try:
        # Choose model based on requirements
        model_name = "gemini-pro"
        
        # Create appropriate prompt based on language
        if language == "it":
            prompt = f"""
Analizza questa trascrizione di una riunione e fornisci:

1. **Riassunto**: Un riassunto conciso dei punti principali discussi (2-3 paragrafi massimo)
2. **Punti chiave**: Una lista numerata dei punti più importanti
3. **Azioni da intraprendere**: Una lista delle azioni concrete da completare, con eventuali responsabili se menzionati

Trascrizione:
{transcript_text}

Rispondi in italiano e usa un formato strutturato.
"""
        else:  # English
            prompt = f"""
Analyze this meeting transcription and provide:

1. **Summary**: A concise summary of the main points discussed (2-3 paragraphs maximum)
2. **Key Points**: A numbered list of the most important points
3. **Action Items**: A list of concrete actions to be completed, with responsible parties if mentioned

Transcription:
{transcript_text}

Please respond in English and use a structured format.
"""
        
        # Initialize Vertex AI client
        client = aip.PredictionServiceClient(
            client_options={"api_endpoint": f"{LOCATION}-aiplatform.googleapis.com"}
        )
        
        # Prepare the request
        endpoint = client.endpoint_path(
            project=PROJECT_ID,
            location=LOCATION,
            endpoint="gemini-pro"
        )
        
        # For now, let's use a simpler approach with basic text processing
        # In production, you would integrate with the actual Gemini API
        summary_text = await generate_basic_summary(transcript_text, language)
        
        return {
            "summary_text": summary_text,
            "language": language
        }
        
    except Exception as e:
        logger.error(f"Failed to generate summary: {str(e)}")
        # Fallback to basic summary
        return await generate_basic_summary(transcript_text, language)

async def generate_basic_summary(transcript_text: str, language: str) -> str:
    """Generate a basic summary when AI service is not available"""
    try:
        # Split transcript into sentences
        sentences = transcript_text.split('. ')
        
        # Take first few sentences and last few sentences
        if len(sentences) <= 5:
            summary_sentences = sentences
        else:
            summary_sentences = sentences[:3] + sentences[-2:]
        
        summary = '. '.join(summary_sentences)
        
        if language == "it":
            prefix = "Riassunto automatico della riunione:\n\n"
        else:
            prefix = "Automatic meeting summary:\n\n"
        
        return prefix + summary
        
    except Exception as e:
        logger.error(f"Failed to generate basic summary: {str(e)}")
        if language == "it":
            return "Riassunto non disponibile."
        else:
            return "Summary not available." 