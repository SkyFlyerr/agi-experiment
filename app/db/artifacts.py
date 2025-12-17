"""Artifact operations."""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID

from .models import MessageArtifact, ArtifactKind
from .queries import (
    INSERT_ARTIFACT,
    GET_ARTIFACTS_FOR_MESSAGE,
    UPDATE_ARTIFACT_CONTENT,
)
from . import get_db

logger = logging.getLogger(__name__)


async def store_artifact(
    message_id: UUID,
    kind: ArtifactKind,
    content_json: Optional[Dict[str, Any]] = None,
    uri: Optional[str] = None,
) -> MessageArtifact:
    """
    Store a new artifact for a message.

    Args:
        message_id: Message UUID
        kind: Artifact kind (voice_transcript, image_json, etc.)
        content_json: Artifact content as JSON
        uri: Optional URI reference (e.g., file path, S3 URL)

    Returns:
        Created MessageArtifact instance
    """
    db = get_db()

    try:
        # Convert enum to string value
        kind_value = kind.value if isinstance(kind, ArtifactKind) else kind

        row = await db.fetch_one(
            INSERT_ARTIFACT,
            message_id,
            kind_value,
            content_json,
            uri,
        )

        logger.info(
            f"Stored artifact {row['id']} for message {message_id} (kind={kind_value})"
        )
        return MessageArtifact(**row)

    except Exception as e:
        logger.error(
            f"Error storing artifact for message {message_id} (kind={kind}): {e}"
        )
        raise


async def get_artifacts_for_message(message_id: UUID) -> List[MessageArtifact]:
    """
    Get all artifacts for a message.

    Args:
        message_id: Message UUID

    Returns:
        List of MessageArtifact instances, ordered by created_at ASC
    """
    db = get_db()

    try:
        rows = await db.fetch_all(GET_ARTIFACTS_FOR_MESSAGE, message_id)

        artifacts = [MessageArtifact(**row) for row in rows]
        logger.debug(f"Fetched {len(artifacts)} artifacts for message {message_id}")
        return artifacts

    except Exception as e:
        logger.error(f"Error fetching artifacts for message {message_id}: {e}")
        raise


async def update_artifact(
    artifact_id: UUID,
    content_json: Dict[str, Any],
) -> MessageArtifact:
    """
    Update artifact content.

    Args:
        artifact_id: Artifact UUID
        content_json: Updated content JSON

    Returns:
        Updated MessageArtifact instance
    """
    db = get_db()

    try:
        row = await db.fetch_one(
            UPDATE_ARTIFACT_CONTENT,
            artifact_id,
            content_json,
        )

        if not row:
            raise ValueError(f"Artifact not found: {artifact_id}")

        logger.info(f"Updated artifact {artifact_id}")
        return MessageArtifact(**row)

    except Exception as e:
        logger.error(f"Error updating artifact {artifact_id}: {e}")
        raise


__all__ = [
    "store_artifact",
    "get_artifacts_for_message",
    "update_artifact",
]
