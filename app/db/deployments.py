"""Deployment operations."""

import logging
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from .models import Deployment, DeploymentStatus
from .queries import (
    CREATE_DEPLOYMENT,
    UPDATE_DEPLOYMENT_STATUS,
    GET_LATEST_DEPLOYMENT,
    GET_DEPLOYMENT_BY_ID,
    GET_RECENT_DEPLOYMENTS,
)
from . import get_db

logger = logging.getLogger(__name__)


async def create_deployment(
    git_sha: str,
    branch: str,
) -> Deployment:
    """
    Create a new deployment record.

    Args:
        git_sha: Git commit SHA being deployed
        branch: Git branch name

    Returns:
        Created Deployment instance
    """
    db = get_db()

    try:
        row = await db.fetch_one(
            CREATE_DEPLOYMENT,
            git_sha,
            branch,
        )

        logger.info(
            f"Created deployment {row['id']} (sha={git_sha[:8]}, branch={branch})"
        )
        return Deployment(**row)

    except Exception as e:
        logger.error(
            f"Error creating deployment (sha={git_sha}, branch={branch}): {e}"
        )
        raise


async def update_deployment_status(
    deployment_id: UUID,
    status: DeploymentStatus,
    report_text: Optional[str] = None,
) -> Deployment:
    """
    Update deployment status.

    Args:
        deployment_id: Deployment UUID
        status: New deployment status
        report_text: Optional deployment report/log

    Returns:
        Updated Deployment instance
    """
    db = get_db()

    try:
        # Convert enum to string value
        status_value = status.value if isinstance(status, DeploymentStatus) else status

        # Set finished_at if status is terminal
        finished_at = None
        if status in [
            DeploymentStatus.HEALTHY,
            DeploymentStatus.ROLLED_BACK,
            DeploymentStatus.FAILED,
        ]:
            finished_at = datetime.utcnow()

        row = await db.fetch_one(
            UPDATE_DEPLOYMENT_STATUS,
            deployment_id,
            status_value,
            finished_at,
            report_text,
        )

        if not row:
            raise ValueError(f"Deployment not found: {deployment_id}")

        logger.info(f"Updated deployment {deployment_id} status to {status_value}")
        return Deployment(**row)

    except Exception as e:
        logger.error(f"Error updating deployment {deployment_id} status: {e}")
        raise


async def get_latest_deployment() -> Optional[Deployment]:
    """
    Get the most recent deployment.

    Returns:
        Deployment instance or None if no deployments exist
    """
    db = get_db()

    try:
        row = await db.fetch_one(GET_LATEST_DEPLOYMENT)

        if row:
            logger.debug(f"Found latest deployment: {row['id']}")
            return Deployment(**row)

        logger.debug("No deployments found")
        return None

    except Exception as e:
        logger.error(f"Error fetching latest deployment: {e}")
        raise


async def get_deployment_by_id(deployment_id: UUID) -> Optional[Deployment]:
    """
    Get deployment by ID.

    Args:
        deployment_id: Deployment UUID

    Returns:
        Deployment instance or None if not found
    """
    db = get_db()

    try:
        row = await db.fetch_one(GET_DEPLOYMENT_BY_ID, deployment_id)

        if row:
            logger.debug(f"Found deployment: {deployment_id}")
            return Deployment(**row)

        logger.debug(f"Deployment not found: {deployment_id}")
        return None

    except Exception as e:
        logger.error(f"Error fetching deployment {deployment_id}: {e}")
        raise


async def get_recent_deployments(limit: int = 10) -> List[Deployment]:
    """
    Get recent deployments.

    Args:
        limit: Maximum number of deployments to fetch (default: 10)

    Returns:
        List of Deployment instances, ordered by started_at DESC
    """
    db = get_db()

    try:
        rows = await db.fetch_all(GET_RECENT_DEPLOYMENTS, limit)

        deployments = [Deployment(**row) for row in rows]
        logger.debug(f"Fetched {len(deployments)} recent deployments")
        return deployments

    except Exception as e:
        logger.error(f"Error fetching recent deployments: {e}")
        raise


__all__ = [
    "create_deployment",
    "update_deployment_status",
    "get_latest_deployment",
    "get_deployment_by_id",
    "get_recent_deployments",
]
