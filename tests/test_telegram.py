"""Tests for Telegram webhook ingestion."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4

from aiogram.types import Update, Message, Chat, User, CallbackQuery, PhotoSize
from fastapi.testclient import TestClient

from app.telegram.normalizer import (
    normalize_update,
    normalize_message,
    normalize_callback,
    NormalizedMessage,
    NormalizedCallback,
)
from app.telegram.responses import (
    escape_html,
    split_long_message,
    create_approval_keyboard,
)
from app.db.models import MessageRole


# Fixtures

@pytest.fixture
def mock_telegram_user():
    """Mock Telegram user."""
    return User(id=12345, is_bot=False, first_name="Test User")


@pytest.fixture
def mock_telegram_chat():
    """Mock Telegram chat."""
    return Chat(id=67890, type="private")


@pytest.fixture
def mock_telegram_message(mock_telegram_user, mock_telegram_chat):
    """Mock Telegram message."""
    return Message(
        message_id=111,
        date=datetime.now(),
        chat=mock_telegram_chat,
        from_user=mock_telegram_user,
        text="Hello, bot!"
    )


@pytest.fixture
def mock_telegram_voice_message(mock_telegram_user, mock_telegram_chat):
    """Mock Telegram voice message."""
    from aiogram.types import Voice

    voice = Voice(
        file_id="voice_file_id_123",
        file_unique_id="unique_voice_123",
        duration=5
    )

    return Message(
        message_id=222,
        date=datetime.now(),
        chat=mock_telegram_chat,
        from_user=mock_telegram_user,
        voice=voice
    )


@pytest.fixture
def mock_telegram_photo_message(mock_telegram_user, mock_telegram_chat):
    """Mock Telegram photo message."""
    photo = PhotoSize(
        file_id="photo_file_id_456",
        file_unique_id="unique_photo_456",
        width=800,
        height=600
    )

    return Message(
        message_id=333,
        date=datetime.now(),
        chat=mock_telegram_chat,
        from_user=mock_telegram_user,
        photo=[photo],
        caption="Check this out!"
    )


@pytest.fixture
def mock_callback_query(mock_telegram_user, mock_telegram_message):
    """Mock Telegram callback query."""
    return CallbackQuery(
        id="callback_123",
        from_user=mock_telegram_user,
        chat_instance="chat_instance_123",
        message=mock_telegram_message,
        data="approval:12345678-1234-1234-1234-123456789abc"
    )


# Test Normalizer

def test_normalize_text_message(mock_telegram_message):
    """Test normalizing a text message."""
    update = Update(update_id=1, message=mock_telegram_message)

    normalized_msg, normalized_callback = normalize_update(update)

    assert normalized_callback is None
    assert normalized_msg is not None
    assert isinstance(normalized_msg, NormalizedMessage)
    assert normalized_msg.text == "Hello, bot!"
    assert normalized_msg.user_id == "12345"
    assert normalized_msg.chat_id == "67890"
    assert normalized_msg.message_id == "111"
    assert normalized_msg.role == MessageRole.USER
    assert normalized_msg.media_type is None


def test_normalize_voice_message(mock_telegram_voice_message):
    """Test normalizing a voice message."""
    update = Update(update_id=2, message=mock_telegram_voice_message)

    normalized_msg, _ = normalize_update(update)

    assert normalized_msg is not None
    assert normalized_msg.media_type == "voice"
    assert normalized_msg.media_file_id == "voice_file_id_123"


def test_normalize_photo_message(mock_telegram_photo_message):
    """Test normalizing a photo message."""
    update = Update(update_id=3, message=mock_telegram_photo_message)

    normalized_msg, _ = normalize_update(update)

    assert normalized_msg is not None
    assert normalized_msg.media_type == "photo"
    assert normalized_msg.media_file_id == "photo_file_id_456"
    assert normalized_msg.text == "Check this out!"  # Caption


def test_normalize_callback_query(mock_callback_query):
    """Test normalizing a callback query."""
    update = Update(update_id=4, callback_query=mock_callback_query)

    normalized_msg, normalized_callback = normalize_update(update)

    assert normalized_msg is None
    assert normalized_callback is not None
    assert isinstance(normalized_callback, NormalizedCallback)
    assert normalized_callback.callback_id == "callback_123"
    assert normalized_callback.callback_data == "approval:12345678-1234-1234-1234-123456789abc"
    assert normalized_callback.user_id == "12345"
    assert normalized_callback.chat_id == "67890"


# Test Response Formatting

def test_escape_html():
    """Test HTML escaping."""
    text = "Hello <world> & friends"
    escaped = escape_html(text)

    assert escaped == "Hello &lt;world&gt; &amp; friends"


def test_split_long_message():
    """Test splitting long messages."""
    # Short message (no split)
    short_text = "Hello, world!"
    chunks = split_long_message(short_text)
    assert len(chunks) == 1
    assert chunks[0] == short_text

    # Long message (requires split)
    long_text = "Line\n" * 1000  # ~5000 chars
    chunks = split_long_message(long_text, max_length=1000)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 1000


def test_create_approval_keyboard():
    """Test approval keyboard creation."""
    approval_id = uuid4()
    keyboard = create_approval_keyboard(approval_id)

    assert keyboard is not None
    assert len(keyboard.inline_keyboard) == 1
    assert len(keyboard.inline_keyboard[0]) == 1

    button = keyboard.inline_keyboard[0][0]
    assert button.text == "✅ OK"
    assert button.callback_data == f"approval:{approval_id}"


# Test Webhook Handler

@pytest.mark.asyncio
async def test_webhook_endpoint_success():
    """Test webhook endpoint with valid update."""
    from app.routes.webhook import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router, prefix="/webhook")

    client = TestClient(app)

    # Mock update payload
    update_payload = {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "date": int(datetime.now().timestamp()),
            "chat": {
                "id": 12345,
                "type": "private"
            },
            "from": {
                "id": 67890,
                "is_bot": False,
                "first_name": "Test"
            },
            "text": "Hello, bot!"
        }
    }

    # Mock ingestion
    with patch("app.telegram.webhook.ingest_telegram_update", new_callable=AsyncMock):
        response = client.post("/webhook/telegram", json=update_payload)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_webhook_endpoint_with_secret():
    """Test webhook endpoint with secret verification."""
    from app.routes.webhook import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router, prefix="/webhook")

    client = TestClient(app)

    update_payload = {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "date": int(datetime.now().timestamp()),
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 67890, "is_bot": False, "first_name": "Test"},
            "text": "Hello"
        }
    }

    # Mock settings with secret
    with patch("app.telegram.webhook.settings") as mock_settings:
        mock_settings.TELEGRAM_WEBHOOK_SECRET = "test_secret_123"

        # Valid secret
        with patch("app.telegram.webhook.ingest_telegram_update", new_callable=AsyncMock):
            response = client.post(
                "/webhook/telegram",
                json=update_payload,
                headers={"X-Telegram-Bot-Api-Secret-Token": "test_secret_123"}
            )
        assert response.status_code == 200

        # Invalid secret
        response = client.post(
            "/webhook/telegram",
            json=update_payload,
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong_secret"}
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_webhook_endpoint_invalid_payload():
    """Test webhook endpoint with invalid payload."""
    from app.routes.webhook import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router, prefix="/webhook")

    client = TestClient(app)

    # Invalid payload (missing required fields)
    invalid_payload = {
        "update_id": 123456789
        # Missing message/callback_query
    }

    response = client.post("/webhook/telegram", json=invalid_payload)

    # Should still return 200 to prevent Telegram retries
    assert response.status_code == 200


# Test Media Handling

@pytest.mark.asyncio
async def test_download_media():
    """Test media download."""
    from app.telegram.media import download_media
    from aiogram.types import File as TelegramFile

    message_id = uuid4()

    # Mock bot
    mock_bot = AsyncMock()
    mock_file_info = TelegramFile(
        file_id="test_file_id",
        file_unique_id="unique_id",
        file_size=1024,
        file_path="voice/file_123.ogg"
    )
    mock_bot.get_file.return_value = mock_file_info
    mock_bot.download_file.return_value = None

    with patch("app.telegram.media.get_bot", return_value=mock_bot):
        metadata = await download_media("test_file_id", "voice", message_id)

    assert metadata is not None
    assert metadata.file_id == "test_file_id"
    assert metadata.file_type == "voice"
    assert metadata.file_size == 1024
    assert metadata.file_path.endswith(".ogg")


# Test Callback Handling

@pytest.mark.asyncio
async def test_handle_approval_callback():
    """Test handling approval callback."""
    from app.telegram.callbacks import handle_approval_callback

    approval_id = uuid4()
    job_id = uuid4()

    normalized_callback = NormalizedCallback(
        callback_id="callback_123",
        callback_data=f"approval:{approval_id}",
        user_id="12345",
        chat_id="67890",
        message_id="111",
        timestamp=datetime.now(),
        raw_payload={}
    )

    # Mock database and bot
    mock_db = MagicMock()
    mock_db.fetch_one = AsyncMock(side_effect=[
        {"id": approval_id, "job_id": job_id, "proposal_text": "Test proposal"},  # Approval
        {"id": job_id, "mode": "classify"}  # Job
    ])
    mock_db.execute = AsyncMock()

    mock_bot = AsyncMock()

    with patch("app.telegram.callbacks.get_db", return_value=mock_db), \
         patch("app.telegram.callbacks.get_bot", return_value=mock_bot):
        await handle_approval_callback(normalized_callback)

    # Verify approval was resolved
    assert mock_db.fetch_one.call_count >= 1

    # Verify bot updated message
    assert mock_bot.edit_message_reply_markup.called
    assert mock_bot.edit_message_text.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
