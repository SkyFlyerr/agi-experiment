"""Common SQL query constants and prepared statements."""

# Chat Threads queries
GET_THREAD_BY_CHAT_ID = """
    SELECT id, platform, chat_id, created_at, updated_at
    FROM chat_threads
    WHERE platform = $1 AND chat_id = $2
    LIMIT 1
"""

GET_THREAD_BY_ID = """
    SELECT id, platform, chat_id, created_at, updated_at
    FROM chat_threads
    WHERE id = $1
    LIMIT 1
"""

CREATE_THREAD = """
    INSERT INTO chat_threads (platform, chat_id)
    VALUES ($1, $2)
    ON CONFLICT (platform, chat_id) DO UPDATE
    SET updated_at = NOW()
    RETURNING id, platform, chat_id, created_at, updated_at
"""

UPDATE_THREAD_TIMESTAMP = """
    UPDATE chat_threads
    SET updated_at = NOW()
    WHERE id = $1
    RETURNING id, platform, chat_id, created_at, updated_at
"""

# Chat Messages queries
INSERT_MESSAGE = """
    INSERT INTO chat_messages (thread_id, platform_message_id, role, author_user_id, text, raw_payload)
    VALUES ($1, $2, $3, $4, $5, $6)
    RETURNING id, thread_id, platform_message_id, role, author_user_id, text, created_at, raw_payload
"""

GET_RECENT_MESSAGES = """
    SELECT id, thread_id, platform_message_id, role, author_user_id, text, created_at, raw_payload
    FROM chat_messages
    WHERE thread_id = $1
    ORDER BY created_at DESC
    LIMIT $2
"""

GET_MESSAGE_BY_ID = """
    SELECT id, thread_id, platform_message_id, role, author_user_id, text, created_at, raw_payload
    FROM chat_messages
    WHERE id = $1
    LIMIT 1
"""

GET_MESSAGE_BY_PLATFORM_ID = """
    SELECT id, thread_id, platform_message_id, role, author_user_id, text, created_at, raw_payload
    FROM chat_messages
    WHERE thread_id = $1 AND platform_message_id = $2
    LIMIT 1
"""

# Message Artifacts queries
INSERT_ARTIFACT = """
    INSERT INTO message_artifacts (message_id, kind, content_json, uri)
    VALUES ($1, $2, $3, $4)
    RETURNING id, message_id, kind, content_json, uri, created_at
"""

GET_ARTIFACTS_FOR_MESSAGE = """
    SELECT id, message_id, kind, content_json, uri, created_at
    FROM message_artifacts
    WHERE message_id = $1
    ORDER BY created_at ASC
"""

UPDATE_ARTIFACT_CONTENT = """
    UPDATE message_artifacts
    SET content_json = $2
    WHERE id = $1
    RETURNING id, message_id, kind, content_json, uri, created_at
"""

# Reactive Jobs queries
ENQUEUE_JOB = """
    INSERT INTO reactive_jobs (thread_id, trigger_message_id, mode, payload_json)
    VALUES ($1, $2, $3, $4)
    RETURNING id, thread_id, trigger_message_id, status, mode, payload_json, created_at, started_at, finished_at
"""

POLL_PENDING_JOBS = """
    SELECT id, thread_id, trigger_message_id, status, mode, payload_json, created_at, started_at, finished_at
    FROM reactive_jobs
    WHERE status = 'queued'
    ORDER BY created_at ASC
    LIMIT $1
"""

UPDATE_JOB_STATUS = """
    UPDATE reactive_jobs
    SET status = $2, started_at = $3, finished_at = $4
    WHERE id = $1
    RETURNING id, thread_id, trigger_message_id, status, mode, payload_json, created_at, started_at, finished_at
"""

GET_JOB_BY_ID = """
    SELECT id, thread_id, trigger_message_id, status, mode, payload_json, created_at, started_at, finished_at
    FROM reactive_jobs
    WHERE id = $1
    LIMIT 1
"""

CANCEL_PENDING_JOBS_FOR_THREAD = """
    UPDATE reactive_jobs
    SET status = 'canceled'
    WHERE thread_id = $1 AND status = 'queued'
"""

# Approvals queries
CREATE_APPROVAL = """
    INSERT INTO approvals (thread_id, job_id, proposal_text)
    VALUES ($1, $2, $3)
    RETURNING id, thread_id, job_id, proposal_text, status, created_at, resolved_at
"""

GET_APPROVAL_BY_ID = """
    SELECT id, thread_id, job_id, proposal_text, status, created_at, resolved_at
    FROM approvals
    WHERE id = $1
    LIMIT 1
"""

RESOLVE_APPROVAL = """
    UPDATE approvals
    SET status = $2, resolved_at = NOW()
    WHERE id = $1
    RETURNING id, thread_id, job_id, proposal_text, status, created_at, resolved_at
"""

SUPERSEDE_PENDING_APPROVALS = """
    UPDATE approvals
    SET status = 'superseded', resolved_at = NOW()
    WHERE thread_id = $1 AND status = 'pending'
"""

GET_PENDING_APPROVAL_FOR_JOB = """
    SELECT id, thread_id, job_id, proposal_text, status, created_at, resolved_at
    FROM approvals
    WHERE job_id = $1 AND status = 'pending'
    LIMIT 1
"""

# Token Ledger queries
LOG_TOKENS = """
    INSERT INTO token_ledger (scope, provider, tokens_input, tokens_output, tokens_total, meta_json)
    VALUES ($1, $2, $3, $4, $5, $6)
    RETURNING id, scope, provider, tokens_input, tokens_output, tokens_total, created_at, meta_json
"""

GET_DAILY_TOKEN_USAGE = """
    SELECT scope, provider, SUM(tokens_total) as total_tokens
    FROM token_ledger
    WHERE DATE(created_at) = $1
    GROUP BY scope, provider
"""

GET_TOKEN_STATS_BY_SCOPE = """
    SELECT scope, SUM(tokens_input) as total_input, SUM(tokens_output) as total_output, SUM(tokens_total) as total_tokens
    FROM token_ledger
    WHERE created_at >= $1
    GROUP BY scope
"""

GET_TOKEN_STATS_BY_PROVIDER = """
    SELECT provider, SUM(tokens_input) as total_input, SUM(tokens_output) as total_output, SUM(tokens_total) as total_tokens
    FROM token_ledger
    WHERE created_at >= $1
    GROUP BY provider
"""

# Deployments queries
CREATE_DEPLOYMENT = """
    INSERT INTO deployments (git_sha, branch)
    VALUES ($1, $2)
    RETURNING id, git_sha, branch, status, started_at, finished_at, report_text
"""

UPDATE_DEPLOYMENT_STATUS = """
    UPDATE deployments
    SET status = $2, finished_at = $3, report_text = $4
    WHERE id = $1
    RETURNING id, git_sha, branch, status, started_at, finished_at, report_text
"""

GET_LATEST_DEPLOYMENT = """
    SELECT id, git_sha, branch, status, started_at, finished_at, report_text
    FROM deployments
    ORDER BY started_at DESC
    LIMIT 1
"""

GET_DEPLOYMENT_BY_ID = """
    SELECT id, git_sha, branch, status, started_at, finished_at, report_text
    FROM deployments
    WHERE id = $1
    LIMIT 1
"""

GET_RECENT_DEPLOYMENTS = """
    SELECT id, git_sha, branch, status, started_at, finished_at, report_text
    FROM deployments
    ORDER BY started_at DESC
    LIMIT $1
"""


__all__ = [
    # Threads
    "GET_THREAD_BY_CHAT_ID",
    "CREATE_THREAD",
    "UPDATE_THREAD_TIMESTAMP",
    # Messages
    "INSERT_MESSAGE",
    "GET_RECENT_MESSAGES",
    "GET_MESSAGE_BY_ID",
    "GET_MESSAGE_BY_PLATFORM_ID",
    # Artifacts
    "INSERT_ARTIFACT",
    "GET_ARTIFACTS_FOR_MESSAGE",
    "UPDATE_ARTIFACT_CONTENT",
    # Jobs
    "ENQUEUE_JOB",
    "POLL_PENDING_JOBS",
    "UPDATE_JOB_STATUS",
    "GET_JOB_BY_ID",
    "CANCEL_PENDING_JOBS_FOR_THREAD",
    # Approvals
    "CREATE_APPROVAL",
    "GET_APPROVAL_BY_ID",
    "RESOLVE_APPROVAL",
    "SUPERSEDE_PENDING_APPROVALS",
    "GET_PENDING_APPROVAL_FOR_JOB",
    # Tokens
    "LOG_TOKENS",
    "GET_DAILY_TOKEN_USAGE",
    "GET_TOKEN_STATS_BY_SCOPE",
    "GET_TOKEN_STATS_BY_PROVIDER",
    # Deployments
    "CREATE_DEPLOYMENT",
    "UPDATE_DEPLOYMENT_STATUS",
    "GET_LATEST_DEPLOYMENT",
    "GET_DEPLOYMENT_BY_ID",
    "GET_RECENT_DEPLOYMENTS",
]
