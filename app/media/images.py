"""Image processing and analysis using Claude Vision API."""

import logging
import base64
from typing import Dict, Any, List, Optional

from app.config import settings
from .utils import (
    get_file_extension,
    get_mime_type,
    validate_file_size,
    resize_image_if_needed,
)

logger = logging.getLogger(__name__)

# Supported image formats
SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


async def process_image(
    file_path: str,
) -> Dict[str, Any]:
    """
    Analyze image using Claude Vision API.

    Args:
        file_path: Path to image file

    Returns:
        Dictionary with image analysis:
        {
            'status': 'success' | 'error',
            'description': str (if success),
            'objects': List[str],
            'text': str (if OCR),
            'confidence': float,
            'format': str,
            'dimensions': [width, height],
            'error': str (if error),
        }
    """
    try:
        # Validate file size (Claude Vision API limit is 20MB per image)
        if not validate_file_size(file_path, 20):
            return {
                "status": "error",
                "error": "File size exceeds 20MB limit",
            }

        # Validate format
        ext = get_file_extension(file_path)
        if ext not in SUPPORTED_IMAGE_FORMATS:
            return {
                "status": "error",
                "error": f"Unsupported format: {ext}",
                "supported_formats": list(SUPPORTED_IMAGE_FORMATS),
            }

        # Get image dimensions
        dimensions = await _get_image_dimensions(file_path)

        # Resize if needed (max 1024px on longest side)
        resized_path = file_path
        if dimensions and (dimensions[0] > 1024 or dimensions[1] > 1024):
            import tempfile
            temp_fd, temp_path = tempfile.mkstemp(suffix=ext)
            try:
                if resize_image_if_needed(file_path, temp_path, max_size=1024):
                    resized_path = temp_path
                    # Update dimensions
                    dimensions = await _get_image_dimensions(resized_path)
            finally:
                if temp_fd:
                    import os
                    os.close(temp_fd)

        # Analyze with Claude Vision
        result = await _analyze_with_vision_api(resized_path)

        if result["status"] == "success":
            result["format"] = ext
            if dimensions:
                result["dimensions"] = list(dimensions)

        return result

    except Exception as e:
        logger.error(f"Error processing image: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


async def _get_image_dimensions(file_path: str) -> Optional[tuple]:
    """Get image width and height."""
    try:
        from PIL import Image

        with Image.open(file_path) as img:
            return (img.width, img.height)
    except Exception as e:
        logger.warning(f"Could not get image dimensions: {e}")
        return None


async def _analyze_with_vision_api(file_path: str) -> Dict[str, Any]:
    """
    Analyze image using Claude Vision API.

    Args:
        file_path: Path to image file

    Returns:
        Analysis result dictionary
    """
    try:
        from anthropic import Anthropic

        # Read image and encode to base64
        with open(file_path, "rb") as f:
            image_data = f.read()

        image_base64 = base64.standard_b64encode(image_data).decode("utf-8")
        mime_type = get_mime_type(file_path)

        # Create Anthropic client
        client = Anthropic(api_key=settings.CLAUDE_CODE_OAUTH_TOKEN)

        # Call Claude Vision API
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": image_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": """Analyze this image and provide:
1. A concise description (1-2 sentences)
2. A list of main objects/entities visible (5-10 items)
3. Any text visible in the image (if present)

Format your response as JSON with keys: description, objects (array), text (or empty string if none)""",
                        },
                    ],
                }
            ],
        )

        # Parse response
        response_text = message.content[0].text

        # Try to parse JSON response
        import json

        try:
            # Extract JSON from response (might have markdown code blocks)
            json_str = response_text
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()

            analysis = json.loads(json_str)

            result = {
                "status": "success",
                "description": analysis.get("description", ""),
                "objects": analysis.get("objects", []),
                "text": analysis.get("text", ""),
                "confidence": 0.9,  # Claude doesn't provide explicit confidence
            }

            logger.info(f"Analyzed image with Claude Vision")
            return result

        except json.JSONDecodeError:
            # Return raw text if JSON parsing fails
            return {
                "status": "success",
                "description": response_text,
                "objects": [],
                "text": "",
                "confidence": 0.7,
            }

    except ImportError:
        logger.error("Anthropic package not installed")
        return {
            "status": "error",
            "error": "Anthropic package not installed",
        }

    except Exception as e:
        logger.error(f"Vision API error: {e}")
        return {
            "status": "error",
            "error": f"Vision analysis failed: {str(e)}",
        }


__all__ = ["process_image"]
