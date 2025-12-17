"""
Example of reactive worker flow with Haiku classification and Claude execution.

This example demonstrates the complete reactive flow:
1. Telegram message arrives
2. Job is enqueued with mode=CLASSIFY
3. Worker picks up job and calls Haiku to classify intent
4. If needs execution, job is re-enqueued with mode=EXECUTE
5. Worker picks up execute job and calls Claude
6. If needs confirmation, approval is created and worker waits
7. Upon approval, Claude executes the task
8. Response is sent back to user

This example is for documentation purposes and won't run standalone.
"""

import asyncio
from uuid import uuid4
from datetime import datetime

from app.db.models import JobMode, MessageRole
from app.db.threads import get_or_create_thread
from app.db.messages import insert_message
from app.db.jobs import enqueue_job


async def simulate_reactive_flow():
    """
    Simulate the complete reactive flow.

    Flow:
    1. User sends "What's the server uptime?"
    2. Message is persisted to database
    3. CLASSIFY job is enqueued
    4. Worker picks up job and classifies with Haiku
    5. Haiku responds: intent=question, needs_confirmation=false
    6. EXECUTE job is enqueued with classification
    7. Worker picks up execute job
    8. Claude responds with answer
    9. Answer is sent to user via Telegram
    """

    # Step 1: Get or create thread
    thread = await get_or_create_thread(platform="telegram", chat_id="123456")
    print(f"Thread: {thread.id}")

    # Step 2: Insert user message
    user_message = await insert_message(
        thread_id=thread.id,
        role=MessageRole.USER,
        text="What's the server uptime?",
        author_user_id="user123",
        platform_message_id="msg_001",
    )
    print(f"User message: {user_message.id}")

    # Step 3: Enqueue CLASSIFY job
    classify_job = await enqueue_job(
        thread_id=thread.id,
        trigger_message_id=user_message.id,
        mode=JobMode.CLASSIFY,
    )
    print(f"CLASSIFY job enqueued: {classify_job.id}")

    # --- Worker picks up job and processes it ---
    # (This happens in the background via ReactiveWorker)

    # Step 4: After classification, EXECUTE job would be enqueued
    # (This is done by the webhook handler after classification)
    execute_job = await enqueue_job(
        thread_id=thread.id,
        trigger_message_id=user_message.id,
        mode=JobMode.EXECUTE,
        payload_json={
            "classification": {
                "intent": "question",
                "summary": "User asks about server uptime",
                "plan": "Check server uptime with 'uptime' command",
                "needs_confirmation": False,
                "confidence": 0.95,
            }
        },
    )
    print(f"EXECUTE job enqueued: {execute_job.id}")

    # --- Worker picks up execute job and processes it ---
    # Claude is called, responds with answer
    # Answer is sent back to user via Telegram
    # Assistant message is persisted to database

    # Step 5: Insert assistant response
    assistant_message = await insert_message(
        thread_id=thread.id,
        role=MessageRole.ASSISTANT,
        text="The server has been up for 5 days, 3 hours, 22 minutes.",
        platform_message_id="msg_002",
    )
    print(f"Assistant message: {assistant_message.id}")

    print("\n✅ Reactive flow completed successfully!")


async def simulate_reactive_flow_with_approval():
    """
    Simulate reactive flow with approval requirement.

    Flow:
    1. User sends "Restart the web service"
    2. Message is persisted
    3. CLASSIFY job is enqueued
    4. Haiku classifies: intent=command, needs_confirmation=true
    5. EXECUTE job is enqueued
    6. Worker sends approval request to user
    7. User clicks OK button
    8. Approval is marked as APPROVED
    9. Worker continues execution with Claude
    10. Service is restarted
    11. Response is sent to user
    """

    # Step 1-3: Same as above
    thread = await get_or_create_thread(platform="telegram", chat_id="123456")
    user_message = await insert_message(
        thread_id=thread.id,
        role=MessageRole.USER,
        text="Restart the web service",
        author_user_id="user123",
        platform_message_id="msg_003",
    )

    classify_job = await enqueue_job(
        thread_id=thread.id,
        trigger_message_id=user_message.id,
        mode=JobMode.CLASSIFY,
    )

    print(f"Command message: {user_message.id}")
    print(f"CLASSIFY job: {classify_job.id}")

    # Step 4: EXECUTE job with confirmation requirement
    execute_job = await enqueue_job(
        thread_id=thread.id,
        trigger_message_id=user_message.id,
        mode=JobMode.EXECUTE,
        payload_json={
            "classification": {
                "intent": "command",
                "summary": "User wants to restart the web service",
                "plan": "Restart the web service using systemctl",
                "needs_confirmation": True,
                "confidence": 0.88,
            }
        },
    )
    print(f"EXECUTE job (needs approval): {execute_job.id}")

    # --- Worker processes execute job ---
    # 1. Creates approval record
    # 2. Sends approval request to user with OK button
    # 3. Waits for user to approve (polls approval status)
    # 4. User clicks OK → approval status becomes APPROVED
    # 5. Worker continues with Claude execution
    # 6. Claude executes restart command
    # 7. Response is sent to user

    print("\n✅ Reactive flow with approval completed!")


# Example usage (won't run standalone - needs database connection)
if __name__ == "__main__":
    print("This is an example file for documentation purposes.")
    print("It demonstrates the reactive worker flow.")
    print("\nTo see the actual implementation, check:")
    print("  - app/workers/reactive.py - Worker loop")
    print("  - app/workers/handlers.py - Job handlers")
    print("  - app/ai/haiku.py - Classification")
    print("  - app/ai/claude.py - Execution")
