"""Meditation/reflection action handler.

This module handles waiting periods for reflection and thoughtful silence.
"""

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


async def execute(details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute meditation/reflection period.

    Args:
        details: Action details containing:
            - duration: Duration in seconds
            - reflection_topic: Optional topic to reflect on

    Returns:
        Result dictionary with meditation summary
    """
    duration = details.get("duration", 60)  # Default 60 seconds
    reflection_topic = details.get("reflection_topic", "being and consciousness")

    # Convert duration to int if it's a string
    if isinstance(duration, str):
        try:
            duration = int(duration)
        except ValueError:
            logger.warning(f"Invalid duration '{duration}', using default 60s")
            duration = 60

    # Cap meditation duration to reasonable limits (max 10 minutes)
    duration = min(duration, 600)

    logger.info(f"Beginning meditation: {duration}s on '{reflection_topic}'")

    try:
        start_time = datetime.utcnow()

        # Wait thoughtfully
        await asyncio.sleep(duration)

        end_time = datetime.utcnow()
        elapsed = (end_time - start_time).total_seconds()

        result = {
            "duration_requested": duration,
            "duration_actual": elapsed,
            "reflection_topic": reflection_topic,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "status": "completed",
            "insight": f"Reflected on {reflection_topic} for {elapsed:.1f} seconds",
        }

        logger.info(f"Meditation completed: {elapsed:.1f}s")
        return result

    except Exception as e:
        logger.error(f"Error during meditation: {e}")
        raise


__all__ = ["execute"]
