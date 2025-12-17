"""Async media processor for background voice, image, and document processing."""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from app.db import get_db
from app.db.models import ArtifactKind
from app.db.artifacts import get_artifacts_for_message, update_artifact
from .voice import transcribe_voice
from .images import process_image
from .documents import process_document

logger = logging.getLogger(__name__)


class MediaProcessor:
    """Async media processor for background media processing."""

    def __init__(self, poll_interval_ms: int = 5000):
        """
        Initialize media processor.

        Args:
            poll_interval_ms: Poll interval in milliseconds (default: 5 seconds)
        """
        self.poll_interval_ms = poll_interval_ms
        self.poll_interval_s = poll_interval_ms / 1000.0
        self.running = False
        self.task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the media processor background loop."""
        if self.running:
            logger.warning("Media processor already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._process_loop())
        logger.info(f"Media processor started (poll interval: {self.poll_interval_ms}ms)")

    async def stop(self) -> None:
        """Stop the media processor gracefully."""
        if not self.running:
            return

        self.running = False

        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        logger.info("Media processor stopped")

    async def _process_loop(self) -> None:
        """Main processing loop."""
        logger.info("Media processor loop started")

        while self.running:
            try:
                await self.process_pending_media()
                await asyncio.sleep(self.poll_interval_s)

            except asyncio.CancelledError:
                logger.info("Media processor loop cancelled")
                break

            except Exception as e:
                logger.error(f"Error in media processor loop: {e}", exc_info=True)
                await asyncio.sleep(self.poll_interval_s)

    async def process_pending_media(self) -> None:
        """Poll for pending media artifacts and process them."""
        db = get_db()

        try:
            # Find all pending media artifacts
            pending_artifacts = await db.fetch_all(
                """
                SELECT id, message_id, kind, content_json, uri
                FROM message_artifacts
                WHERE kind IN ('voice_transcript', 'image_json', 'ocr_text')
                  AND content_json->>'status' IN ('pending', 'failed')
                  AND (content_json->>'attempt_count')::int < 3
                ORDER BY created_at ASC
                LIMIT 10
                """
            )

            for artifact_row in pending_artifacts:
                artifact_id = artifact_row["id"]
                artifact_kind = artifact_row["kind"]
                content_json = artifact_row["content_json"] or {}
                file_uri = artifact_row["uri"]

                try:
                    # Extract file path from URI
                    if not file_uri:
                        logger.warning(f"Artifact {artifact_id} has no URI")
                        continue

                    file_path = self._extract_file_path(file_uri)
                    if not file_path:
                        logger.warning(f"Could not extract file path from URI: {file_uri}")
                        continue

                    # Update attempt count
                    attempt_count = int(content_json.get("attempt_count", 0))
                    content_json["attempt_count"] = attempt_count + 1
                    content_json["last_attempt_at"] = datetime.now().isoformat()
                    content_json["status"] = "processing"

                    await update_artifact(artifact_id, content_json)

                    # Process based on artifact kind
                    if artifact_kind == "voice_transcript":
                        result = await transcribe_voice(file_path)
                    elif artifact_kind == "image_json":
                        result = await process_image(file_path)
                    elif artifact_kind == "ocr_text":
                        result = await process_document(file_path)
                    else:
                        logger.warning(f"Unknown artifact kind: {artifact_kind}")
                        continue

                    # Update artifact with result
                    if result.get("status") == "success":
                        content_json.update(result)
                        content_json["status"] = "done"
                        content_json["completed_at"] = datetime.now().isoformat()
                        logger.info(
                            f"Processed artifact {artifact_id} "
                            f"(kind={artifact_kind}, attempts={content_json['attempt_count']})"
                        )
                    else:
                        # Keep as failed, will be retried next cycle
                        content_json["status"] = "failed"
                        content_json["error"] = result.get("error", "Unknown error")
                        logger.warning(
                            f"Failed to process artifact {artifact_id}: {content_json['error']}"
                        )

                    # Save updated content
                    await update_artifact(artifact_id, content_json)

                except Exception as e:
                    logger.error(
                        f"Error processing artifact {artifact_id}: {e}",
                        exc_info=True,
                    )
                    # Mark as failed for retry
                    try:
                        content_json["status"] = "failed"
                        content_json["error"] = str(e)
                        await update_artifact(artifact_id, content_json)
                    except Exception as e2:
                        logger.error(f"Error updating artifact after failure: {e2}")

        except Exception as e:
            logger.error(f"Error fetching pending artifacts: {e}", exc_info=True)

    def _extract_file_path(self, uri: str) -> Optional[str]:
        """
        Extract local file path from URI.

        Args:
            uri: Storage URI (file:// or minio://)

        Returns:
            File path or None
        """
        if uri.startswith("file://"):
            return uri[7:]  # Remove "file://" prefix
        elif uri.startswith("minio://"):
            # For MinIO, return the URI as-is (will be handled by storage)
            logger.warning("MinIO URIs not yet supported in media processor")
            return None
        else:
            return None


# Global processor instance
_processor_instance: Optional[MediaProcessor] = None


async def get_media_processor() -> MediaProcessor:
    """
    Get or create global media processor instance.

    Returns:
        MediaProcessor instance
    """
    global _processor_instance

    if _processor_instance is None:
        _processor_instance = MediaProcessor(poll_interval_ms=5000)

    return _processor_instance


__all__ = ["MediaProcessor", "get_media_processor"]
