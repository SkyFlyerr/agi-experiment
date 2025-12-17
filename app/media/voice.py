"""Voice message transcription using OpenAI Whisper API or local model."""

import logging
from typing import Optional, Dict, Any

from app.config import settings
from .utils import get_file_extension, validate_file_size

logger = logging.getLogger(__name__)

# Supported voice formats
SUPPORTED_VOICE_FORMATS = {".ogg", ".mp3", ".wav", ".m4a", ".flac"}


async def transcribe_voice(
    file_path: str,
    language: str = "auto",
) -> Dict[str, Any]:
    """
    Transcribe voice message using OpenAI Whisper API.

    Args:
        file_path: Path to audio file
        language: Language code (auto for auto-detection, or specific: en, ru, etc.)

    Returns:
        Dictionary with transcription result:
        {
            'status': 'success' | 'error',
            'transcript': str (if success),
            'confidence': float (0-1, if available),
            'error': str (if error),
            'format': str,
            'duration_ms': int (if available),
        }
    """
    try:
        # Validate file size (Whisper API limit is 25MB)
        if not validate_file_size(file_path, 25):
            return {
                "status": "error",
                "error": "File size exceeds 25MB limit",
            }

        # Validate format
        ext = get_file_extension(file_path)
        if ext not in SUPPORTED_VOICE_FORMATS:
            return {
                "status": "error",
                "error": f"Unsupported format: {ext}",
                "supported_formats": list(SUPPORTED_VOICE_FORMATS),
            }

        # Use Whisper API from OpenAI
        return await _transcribe_with_whisper_api(file_path, language)

    except Exception as e:
        logger.error(f"Error transcribing voice: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


async def _transcribe_with_whisper_api(
    file_path: str,
    language: str = "auto",
) -> Dict[str, Any]:
    """
    Transcribe using OpenAI Whisper API.

    Args:
        file_path: Path to audio file
        language: Language code

    Returns:
        Transcription result dictionary
    """
    try:
        from openai import AsyncOpenAI

        api_key = settings.CLAUDE_CODE_OAUTH_TOKEN  # Fallback to Claude API key
        # You can also set OPENAI_API_KEY separately in environment

        client = AsyncOpenAI(api_key=api_key)

        with open(file_path, "rb") as audio_file:
            # Call Whisper API
            transcript_resp = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=None if language == "auto" else language,
                response_format="verbose_json",
            )

        result = {
            "status": "success",
            "transcript": transcript_resp.text,
            "format": get_file_extension(file_path),
        }

        # Add optional fields if available
        if hasattr(transcript_resp, "language"):
            result["language"] = transcript_resp.language

        logger.info(f"Transcribed voice message ({len(transcript_resp.text)} chars)")
        return result

    except ImportError:
        logger.error("OpenAI package not installed. Install with: pip install openai")
        return {
            "status": "error",
            "error": "OpenAI package not installed",
        }

    except Exception as e:
        logger.error(f"Whisper API error: {e}")
        return {
            "status": "error",
            "error": f"Transcription failed: {str(e)}",
        }


__all__ = ["transcribe_voice"]
