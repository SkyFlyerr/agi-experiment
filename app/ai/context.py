"""Build conversation context for AI prompts."""

import logging
from typing import List
from uuid import UUID

from app.db.models import ChatMessage, ArtifactKind
from app.db.messages import fetch_recent_messages
from app.db.artifacts import get_artifacts_for_message

logger = logging.getLogger(__name__)


async def build_conversation_context(thread_id: UUID, limit: int = 30) -> List[ChatMessage]:
    """
    Build conversation context for AI processing.

    Fetches recent messages with artifacts and formats them for AI consumption.
    Artifacts are enriched with summaries (e.g., voice transcript previews).

    Args:
        thread_id: Thread UUID
        limit: Maximum number of messages to fetch (default: 30)

    Returns:
        List of ChatMessage instances with enriched text
    """
    try:
        # Fetch recent messages
        messages = await fetch_recent_messages(thread_id, limit=limit)

        # Reverse to chronological order (oldest first)
        messages = list(reversed(messages))

        # Enrich messages with artifact summaries
        enriched_messages = []
        for msg in messages:
            # Check if message has artifacts
            artifacts = await get_artifacts_for_message(msg.id)

            if artifacts:
                # Build artifact summary
                artifact_summaries = []
                for artifact in artifacts:
                    summary = _summarize_artifact(artifact.kind, artifact.content_json, artifact.uri)
                    if summary:
                        artifact_summaries.append(summary)

                # Append artifact summaries to message text
                if artifact_summaries:
                    enriched_text = msg.text or ""
                    if enriched_text:
                        enriched_text += "\n\n"
                    enriched_text += "\n".join(artifact_summaries)

                    # Create enriched message copy
                    msg_dict = msg.model_dump()
                    msg_dict['text'] = enriched_text
                    enriched_msg = ChatMessage(**msg_dict)
                    enriched_messages.append(enriched_msg)
                else:
                    enriched_messages.append(msg)
            else:
                enriched_messages.append(msg)

        logger.debug(f"Built context with {len(enriched_messages)} messages for thread {thread_id}")
        return enriched_messages

    except Exception as e:
        logger.error(f"Error building conversation context for thread {thread_id}: {e}")
        raise


def _summarize_artifact(kind: ArtifactKind, content_json: dict, uri: str | None) -> str | None:
    """
    Create a human-readable summary of an artifact.

    Args:
        kind: Artifact kind
        content_json: Artifact content JSON
        uri: Artifact URI (if any)

    Returns:
        Summary string or None
    """
    if not content_json:
        return None

    if kind == ArtifactKind.VOICE_TRANSCRIPT:
        # Voice transcript preview
        text = content_json.get("text", "")
        duration = content_json.get("duration_seconds", 0)
        preview = text[:200] + ("..." if len(text) > 200 else "")
        return f"[Voice message, {duration}s]: {preview}"

    elif kind == ArtifactKind.IMAGE_JSON:
        # Image description
        description = content_json.get("description", "")
        width = content_json.get("width", "?")
        height = content_json.get("height", "?")
        return f"[Image {width}x{height}]: {description}"

    elif kind == ArtifactKind.OCR_TEXT:
        # OCR text preview
        text = content_json.get("text", "")
        preview = text[:200] + ("..." if len(text) > 200 else "")
        return f"[OCR text]: {preview}"

    elif kind == ArtifactKind.FILE_META:
        # File metadata
        filename = content_json.get("filename", "unknown")
        size = content_json.get("size_bytes", 0)
        mime = content_json.get("mime_type", "")
        return f"[File: {filename}, {size} bytes, {mime}]"

    elif kind == ArtifactKind.TOOL_RESULT:
        # Tool execution result
        tool_name = content_json.get("tool", "unknown")
        status = content_json.get("status", "unknown")
        output = content_json.get("output", "")[:200]
        return f"[Tool {tool_name} ({status})]: {output}"

    return None


__all__ = [
    "build_conversation_context",
]
