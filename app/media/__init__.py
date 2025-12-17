"""Media processing module for async voice, image, and document processing.

This module provides asynchronous media processing capabilities:
- Voice transcription (Whisper API)
- Image analysis (Claude Vision)
- Document text extraction (PDF, DOCX, TXT)
- Background async processing queue
"""

import logging

logger = logging.getLogger(__name__)

__all__ = [
    "voice",
    "images",
    "documents",
    "utils",
    "processor",
]
