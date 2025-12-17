#!/usr/bin/env python3
"""Example usage of the database layer for Server Agent vNext."""

import asyncio
import os
from datetime import datetime

# Import database initialization
from app.db import init_db, close_db

# Import operations
from app.db.threads import get_or_create_thread
from app.db.messages import insert_message, fetch_recent_messages
from app.db.artifacts import store_artifact, get_artifacts_for_message
from app.db.jobs import enqueue_job, poll_pending_jobs, update_job_status
from app.db.approvals import create_approval, resolve_approval
from app.db.tokens import log_tokens, get_token_stats
from app.db.deployments import create_deployment, update_deployment_status

# Import models
from app.db.models import (
    MessageRole,
    ArtifactKind,
    JobMode,
    JobStatus,
    ApprovalStatus,
    TokenScope,
    DeploymentStatus,
)


async def main():
    """Demonstrate database layer usage."""

    # Get database URL from environment
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://localhost/server_agent_vnext",
    )

    print("=" * 60)
    print("Server Agent vNext - Database Layer Example")
    print("=" * 60)

    # Initialize database
    print("\n1. Initializing database connection...")
    db = init_db(database_url, min_size=2, max_size=10)
    await db.connect()
    print("   ✓ Connected to database")

    try:
        # Create a thread
        print("\n2. Creating chat thread...")
        thread = await get_or_create_thread("telegram", "example_chat_123")
        print(f"   ✓ Thread created: {thread.id}")
        print(f"     Platform: {thread.platform}")
        print(f"     Chat ID: {thread.chat_id}")

        # Insert a user message
        print("\n3. Inserting user message...")
        user_message = await insert_message(
            thread_id=thread.id,
            role=MessageRole.USER,
            text="Hello! Can you help me with deployment?",
            author_user_id="user_456",
            platform_message_id="msg_789",
        )
        print(f"   ✓ Message created: {user_message.id}")
        print(f"     Role: {user_message.role.value}")
        print(f"     Text: {user_message.text}")

        # Store an artifact (e.g., voice transcript)
        print("\n4. Storing message artifact...")
        artifact = await store_artifact(
            message_id=user_message.id,
            kind=ArtifactKind.VOICE_TRANSCRIPT,
            content_json={
                "text": "Hello! Can you help me with deployment?",
                "confidence": 0.95,
                "language": "en-US",
            },
            uri="s3://bucket/audio/msg_789.mp3",
        )
        print(f"   ✓ Artifact created: {artifact.id}")
        print(f"     Kind: {artifact.kind.value}")
        print(f"     URI: {artifact.uri}")

        # Enqueue a reactive job
        print("\n5. Enqueuing reactive job...")
        job = await enqueue_job(
            thread_id=thread.id,
            trigger_message_id=user_message.id,
            mode=JobMode.CLASSIFY,
            payload_json={"intent": "deployment_help"},
        )
        print(f"   ✓ Job enqueued: {job.id}")
        print(f"     Mode: {job.mode.value}")
        print(f"     Status: {job.status.value}")

        # Poll for pending jobs
        print("\n6. Polling for pending jobs...")
        pending_jobs = await poll_pending_jobs(limit=5)
        print(f"   ✓ Found {len(pending_jobs)} pending jobs")

        # Update job status
        print("\n7. Updating job status to RUNNING...")
        updated_job = await update_job_status(
            job.id,
            JobStatus.RUNNING,
            started_at=datetime.utcnow(),
        )
        print(f"   ✓ Job status updated: {updated_job.status.value}")

        # Create an approval
        print("\n8. Creating approval request...")
        approval = await create_approval(
            thread_id=thread.id,
            job_id=job.id,
            proposal_text="Deploy to production server? This will restart the service.",
        )
        print(f"   ✓ Approval created: {approval.id}")
        print(f"     Status: {approval.status.value}")
        print(f"     Proposal: {approval.proposal_text}")

        # Resolve approval (simulate user approval)
        print("\n9. Resolving approval...")
        resolved_approval = await resolve_approval(
            approval.id,
            ApprovalStatus.APPROVED,
        )
        print(f"   ✓ Approval resolved: {resolved_approval.status.value}")

        # Log token usage
        print("\n10. Logging token usage...")
        token_entry = await log_tokens(
            scope=TokenScope.REACTIVE,
            provider="anthropic",
            tokens_input=150,
            tokens_output=75,
            meta_json={
                "model": "claude-3-sonnet-20240229",
                "job_id": str(job.id),
            },
        )
        print(f"   ✓ Token usage logged: {token_entry.id}")
        print(f"     Total tokens: {token_entry.tokens_total}")
        print(f"     Provider: {token_entry.provider}")

        # Get token statistics
        print("\n11. Fetching token statistics...")
        stats = await get_token_stats(days_back=1)
        print(f"   ✓ Token stats retrieved:")
        print(f"     Scopes: {len(stats['by_scope'])}")
        print(f"     Providers: {len(stats['by_provider'])}")

        # Create a deployment
        print("\n12. Creating deployment record...")
        deployment = await create_deployment(
            git_sha="abc123def456789",
            branch="main",
        )
        print(f"   ✓ Deployment created: {deployment.id}")
        print(f"     Git SHA: {deployment.git_sha}")
        print(f"     Status: {deployment.status.value}")

        # Update deployment status
        print("\n13. Updating deployment status...")
        updated_deployment = await update_deployment_status(
            deployment.id,
            DeploymentStatus.HEALTHY,
            report_text="Deployment completed successfully. All health checks passed.",
        )
        print(f"   ✓ Deployment status updated: {updated_deployment.status.value}")

        # Insert assistant response
        print("\n14. Inserting assistant response...")
        assistant_message = await insert_message(
            thread_id=thread.id,
            role=MessageRole.ASSISTANT,
            text="I've deployed the changes to production. The service is now healthy!",
        )
        print(f"   ✓ Assistant message created: {assistant_message.id}")

        # Fetch recent messages
        print("\n15. Fetching recent messages...")
        recent_messages = await fetch_recent_messages(thread.id, limit=10)
        print(f"   ✓ Found {len(recent_messages)} messages in thread")
        for msg in reversed(recent_messages):  # Show in chronological order
            print(f"     [{msg.role.value}] {msg.text[:50]}...")

        # Complete the job
        print("\n16. Completing the job...")
        completed_job = await update_job_status(
            job.id,
            JobStatus.DONE,
            finished_at=datetime.utcnow(),
        )
        print(f"   ✓ Job completed: {completed_job.status.value}")

        print("\n" + "=" * 60)
        print("✓ All operations completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Error occurred: {e}")
        raise

    finally:
        # Close database connection
        print("\nClosing database connection...")
        await close_db()
        print("✓ Database connection closed")


if __name__ == "__main__":
    asyncio.run(main())
