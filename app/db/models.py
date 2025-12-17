"""Pydantic models for database tables."""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


# Enums for status fields
class MessageRole(str, Enum):
    """Message role enum."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ArtifactKind(str, Enum):
    """Artifact kind enum."""
    VOICE_TRANSCRIPT = "voice_transcript"
    IMAGE_JSON = "image_json"
    OCR_TEXT = "ocr_text"
    FILE_META = "file_meta"
    TOOL_RESULT = "tool_result"


class JobStatus(str, Enum):
    """Reactive job status enum."""
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELED = "canceled"


class JobMode(str, Enum):
    """Reactive job mode enum."""
    CLASSIFY = "classify"
    PLAN = "plan"
    EXECUTE = "execute"
    ANSWER = "answer"


class ApprovalStatus(str, Enum):
    """Approval status enum."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class TokenScope(str, Enum):
    """Token ledger scope enum."""
    PROACTIVE = "proactive"
    REACTIVE = "reactive"


class DeploymentStatus(str, Enum):
    """Deployment status enum."""
    BUILDING = "building"
    TESTING = "testing"
    DEPLOYING = "deploying"
    HEALTHY = "healthy"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


# Pydantic models for database tables
class ChatThread(BaseModel):
    """Chat thread model."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    platform: str = "telegram"
    chat_id: str
    created_at: datetime
    updated_at: datetime


class ChatMessage(BaseModel):
    """Chat message model."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    thread_id: UUID
    platform_message_id: Optional[str] = None
    role: MessageRole
    author_user_id: Optional[str] = None
    text: Optional[str] = None
    created_at: datetime
    raw_payload: Optional[Dict[str, Any]] = None


class MessageArtifact(BaseModel):
    """Message artifact model."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    message_id: UUID
    kind: ArtifactKind
    content_json: Optional[Dict[str, Any]] = None
    uri: Optional[str] = None
    created_at: datetime


class ReactiveJob(BaseModel):
    """Reactive job model."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    thread_id: UUID
    trigger_message_id: UUID
    status: JobStatus = JobStatus.QUEUED
    mode: JobMode
    payload_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class Approval(BaseModel):
    """Approval model."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    thread_id: UUID
    job_id: UUID
    proposal_text: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime
    resolved_at: Optional[datetime] = None


class TokenLedger(BaseModel):
    """Token ledger model."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scope: TokenScope
    provider: str
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_total: int = 0
    created_at: datetime
    meta_json: Optional[Dict[str, Any]] = None


class Deployment(BaseModel):
    """Deployment model."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    git_sha: str
    branch: str
    status: DeploymentStatus = DeploymentStatus.BUILDING
    started_at: datetime
    finished_at: Optional[datetime] = None
    report_text: Optional[str] = None


# Input models for creation (without generated fields)
class ChatThreadCreate(BaseModel):
    """Chat thread creation input."""
    platform: str = "telegram"
    chat_id: str


class ChatMessageCreate(BaseModel):
    """Chat message creation input."""
    thread_id: UUID
    platform_message_id: Optional[str] = None
    role: MessageRole
    author_user_id: Optional[str] = None
    text: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None


class MessageArtifactCreate(BaseModel):
    """Message artifact creation input."""
    message_id: UUID
    kind: ArtifactKind
    content_json: Optional[Dict[str, Any]] = None
    uri: Optional[str] = None


class ReactiveJobCreate(BaseModel):
    """Reactive job creation input."""
    thread_id: UUID
    trigger_message_id: UUID
    mode: JobMode
    payload_json: Optional[Dict[str, Any]] = None


class ApprovalCreate(BaseModel):
    """Approval creation input."""
    thread_id: UUID
    job_id: UUID
    proposal_text: str


class TokenLedgerCreate(BaseModel):
    """Token ledger creation input."""
    scope: TokenScope
    provider: str
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_total: int = 0
    meta_json: Optional[Dict[str, Any]] = None


class DeploymentCreate(BaseModel):
    """Deployment creation input."""
    git_sha: str
    branch: str


__all__ = [
    # Enums
    "MessageRole",
    "ArtifactKind",
    "JobStatus",
    "JobMode",
    "ApprovalStatus",
    "TokenScope",
    "DeploymentStatus",
    # Models
    "ChatThread",
    "ChatMessage",
    "MessageArtifact",
    "ReactiveJob",
    "Approval",
    "TokenLedger",
    "Deployment",
    # Create models
    "ChatThreadCreate",
    "ChatMessageCreate",
    "MessageArtifactCreate",
    "ReactiveJobCreate",
    "ApprovalCreate",
    "TokenLedgerCreate",
    "DeploymentCreate",
]
