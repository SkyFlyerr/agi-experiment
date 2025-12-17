# Media Processing - Phase 7

## Overview

Phase 7 implements comprehensive media processing with async support for voice transcription, image analysis, and document text extraction. The system is designed to handle media files without blocking the webhook endpoint.

## Architecture

### Components

```
Telegram Webhook
    ↓
Media Download (app/telegram/media.py)
    ↓
Create Artifact (status='pending')
    ↓
Return 200 OK
    ↓
Background: Media Processor (app/media/processor.py)
    ├── Voice Transcription (app/media/voice.py)
    ├── Image Analysis (app/media/images.py)
    └── Document Processing (app/media/documents.py)
    ↓
Update Artifact (status='done' or 'failed')
```

### Key Features

- **Non-blocking**: Webhook returns immediately, processing happens in background
- **Async processing**: Uses Python asyncio for efficient resource usage
- **Retry logic**: Failed processing retried up to 3 times
- **Storage abstraction**: Supports MinIO (S3-compatible) or local filesystem
- **Error handling**: Graceful degradation with detailed error messages
- **Monitoring**: Processing logs, attempt tracking, timestamp recording

## Supported Formats

### Voice Messages
- **.ogg** (Telegram default for voice messages)
- **.mp3** (MP3 audio)
- **.wav** (WAV audio)
- **.m4a** (M4A audio)
- **.flac** (FLAC audio)

**Size limit**: 25MB (Whisper API limit)

### Images
- **.jpg / .jpeg** (JPEG images)
- **.png** (PNG images)
- **.gif** (GIF images)
- **.webp** (WebP images)

**Size limit**: 20MB (Claude Vision API limit)
**Max dimensions**: 1024px (automatically resized if needed)

### Documents
- **.pdf** (PDF documents)
- **.docx** (Microsoft Word documents)
- **.txt** (Plain text files)

**Size limit**: 10MB (recommended)

## Configuration

### Environment Variables

```bash
# Storage backend (MinIO or local)
MINIO_ENABLED=false                    # Set to true to use MinIO
MINIO_ENDPOINT=minio.example.com:9000  # MinIO endpoint
MINIO_ACCESS_KEY=minioadmin            # MinIO access key
MINIO_SECRET_KEY=minioadmin            # MinIO secret key
MINIO_BUCKET=server-agent              # Default bucket name

# OpenAI API (for Whisper transcription)
OPENAI_API_KEY=sk-...                  # Optional; falls back to CLAUDE_CODE_OAUTH_TOKEN

# Claude API (for Vision analysis)
CLAUDE_CODE_OAUTH_TOKEN=...            # Required for image analysis
```

## Processing Pipeline

### Voice Messages

1. **Download**: Telegram media file downloaded to local storage
2. **Create artifact**: `kind=voice_transcript`, `status=pending`
3. **Webhook returns**: Immediate 200 OK to Telegram
4. **Background processing**:
   - MediaProcessor polls for pending artifacts
   - Validates audio format and size
   - Calls OpenAI Whisper API
   - Updates artifact with transcript
5. **Result**:
   ```json
   {
     "status": "success",
     "transcript": "User's spoken words...",
     "format": ".ogg",
     "language": "en"
   }
   ```

### Image Analysis

1. **Download**: Telegram media file downloaded to local storage
2. **Create artifact**: `kind=image_json`, `status=pending`
3. **Webhook returns**: Immediate 200 OK
4. **Background processing**:
   - MediaProcessor polls for pending artifacts
   - Validates image format and size
   - Resizes if dimensions exceed 1024px
   - Calls Claude Vision API
   - Extracts: description, objects, OCR text
5. **Result**:
   ```json
   {
     "status": "success",
     "description": "A cat sitting on a chair...",
     "objects": ["cat", "chair", "room"],
     "text": "Any visible text in image",
     "confidence": 0.95,
     "format": ".jpg",
     "dimensions": [1920, 1080]
   }
   ```

### Document Processing

1. **Download**: Telegram media file downloaded to local storage
2. **Create artifact**: `kind=ocr_text`, `status=pending`
3. **Webhook returns**: Immediate 200 OK
4. **Background processing**:
   - MediaProcessor polls for pending artifacts
   - Validates document format and size
   - Extracts text using:
     - **PDF**: pypdf library
     - **DOCX**: python-docx library
     - **TXT**: Direct file read
   - Updates artifact with extracted text
5. **Result**:
   ```json
   {
     "status": "success",
     "text": "Full extracted text content...",
     "word_count": 1234,
     "format": ".pdf",
     "page_count": 5
   }
   ```

## Storage Backends

### Local Filesystem (Default)

Files stored in `/tmp/server-agent-media/` organized by date:

```
/tmp/server-agent-media/
├── bucket1/
│   ├── 2024/12/18/
│   │   ├── file1.ogg
│   │   └── image1.jpg
│   └── 2024/12/19/
│       └── document.pdf
└── bucket2/
    └── 2024/12/18/
        └── audio.mp3
```

**Cleanup**: Files older than 7 days can be automatically deleted via `LocalStorage.cleanup_old_files()`

### MinIO (S3-Compatible)

For production use with MinIO or AWS S3:

```python
from app.storage.minio import MinIOStorage

storage = MinIOStorage(
    endpoint="minio.example.com:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    bucket="server-agent",
    use_ssl=True
)
await storage.connect()
```

**Features**:
- S3-compatible (works with AWS S3, DigitalOcean Spaces, etc.)
- Presigned URL generation for secure downloads
- Automatic bucket creation
- Connection pooling

## API Costs

### Voice Transcription (Whisper)
- **Cost**: $0.006 per minute of audio
- **Example**: 1 hour of audio = $0.36

### Image Analysis (Claude Vision)
- **Cost**: $0.003 per image (Sonnet 3.5, ~500 tokens typical)
- **Example**: 100 images = $0.30

### Document Processing
- **Cost**: Free (local processing with pypdf/python-docx)

## Database Schema

### Artifact Table

Artifacts store media processing results:

```sql
CREATE TABLE message_artifacts (
    id UUID PRIMARY KEY,
    message_id UUID NOT NULL REFERENCES chat_messages(id),
    kind VARCHAR(50) NOT NULL,  -- voice_transcript, image_json, ocr_text
    content_json JSONB,         -- Processing result
    uri TEXT,                   -- Storage URI (file:// or minio://)
    created_at TIMESTAMP NOT NULL
);
```

### Content JSON Fields

**Voice Transcript**:
```json
{
  "file_id": "telegram_file_id",
  "file_type": "voice",
  "file_size": 12345,
  "status": "success|failed|pending|processing",
  "transcript": "transcribed text",
  "language": "en",
  "attempt_count": 1,
  "created_at": "2024-12-18T10:30:00Z",
  "completed_at": "2024-12-18T10:31:00Z",
  "error": "error message if failed"
}
```

**Image JSON**:
```json
{
  "file_id": "telegram_file_id",
  "file_type": "photo",
  "status": "success|failed|pending|processing",
  "description": "detailed description",
  "objects": ["object1", "object2"],
  "text": "OCR text if present",
  "confidence": 0.95,
  "format": ".jpg",
  "dimensions": [1920, 1080],
  "attempt_count": 1,
  "error": "error message if failed"
}
```

**OCR Text**:
```json
{
  "file_id": "telegram_file_id",
  "file_type": "document",
  "status": "success|failed|pending|processing",
  "text": "extracted text",
  "word_count": 1234,
  "page_count": 5,
  "format": ".pdf",
  "attempt_count": 1,
  "error": "error message if failed"
}
```

## Processing States

### Artifact Status Lifecycle

```
pending → processing → done
       ↘           ↗
         failed (retry)
```

- **pending**: Awaiting processing
- **processing**: Currently being processed
- **done**: Successfully processed
- **failed**: Processing failed (can be retried)

### Retry Logic

- Maximum 3 attempts per artifact
- Retried on next MediaProcessor poll cycle
- Failed after 3 attempts → marked as failed (no more retries)

## Monitoring

### Logging

Processing events logged to console/files:

```
2024-12-18 10:30:45 - app.media.voice - INFO - Transcribed voice message (245 chars)
2024-12-18 10:31:02 - app.media.processor - INFO - Processed artifact xxx (kind=voice_transcript)
2024-12-18 10:31:15 - app.media.processor - WARNING - Failed to process artifact yyy: [error]
```

### Metrics

Access processing metrics:

```python
from app.db import get_db

db = get_db()

# Pending artifacts
pending = await db.fetch_all(
    "SELECT COUNT(*) FROM message_artifacts WHERE content_json->>'status' = 'pending'"
)

# Failed artifacts (need manual review)
failed = await db.fetch_all(
    "SELECT COUNT(*) FROM message_artifacts WHERE content_json->>'status' = 'failed' AND (content_json->>'attempt_count')::int >= 3"
)
```

## Usage Examples

### Handling Voice Message

```python
# When Telegram sends voice message:
1. Webhook receives update
2. download_media() called
3. Artifact created with status='pending'
4. Webhook returns 200 OK
5. ~1-5 seconds later, MediaProcessor processes
6. Artifact updated with transcript
7. Reactive worker picks up and responds to user
```

### Handling Image

```python
# When Telegram sends photo:
1. Webhook receives update
2. download_media() called
3. Artifact created with status='pending'
4. Webhook returns 200 OK
5. Image automatically resized if > 1024px
6. MediaProcessor calls Claude Vision API
7. Artifact updated with analysis
8. Reactive worker creates response
```

### Accessing Results in Reactive Worker

```python
from app.db.artifacts import get_artifacts_for_message

async def handle_message(message):
    # Get all artifacts for this message
    artifacts = await get_artifacts_for_message(message.id)

    for artifact in artifacts:
        if artifact.kind == "voice_transcript":
            transcript = artifact.content_json.get("transcript")
            # Process transcript

        elif artifact.kind == "image_json":
            objects = artifact.content_json.get("objects", [])
            description = artifact.content_json.get("description")
            # Process vision results

        elif artifact.kind == "ocr_text":
            text = artifact.content_json.get("text")
            # Process extracted text
```

## Troubleshooting

### Artifacts Stuck in "Pending"

**Symptom**: Media artifacts not being processed

**Causes**:
- MediaProcessor not running (check logs for "Media processor started")
- No pending artifacts query (check database directly)
- Processing loop crashed

**Solutions**:
1. Check logs: `docker-compose logs app | grep "Media processor"`
2. Verify database: `SELECT * FROM message_artifacts WHERE content_json->>'status' = 'pending'`
3. Restart service: `docker-compose restart app`

### Transcription Failures

**Symptom**: `status: "failed"` in artifact

**Causes**:
- OpenAI API rate limit or downtime
- Audio file corrupted or unsupported format
- File size > 25MB

**Solutions**:
1. Check error message: `content_json['error']`
2. Verify file format: `.ogg`, `.mp3`, `.wav`, `.m4a`
3. Check OpenAI API status: https://status.openai.com
4. Retry manually or wait for next cycle

### Image Analysis Slow

**Symptom**: Image processing takes 5+ seconds

**Causes**:
- Large image needing resizing
- Claude Vision API latency
- Network issues

**Solutions**:
1. Images are auto-resized, no action needed
2. Monitor Claude API latency
3. Check network connectivity

### MinIO Connection Issues

**Symptom**: "Failed to connect to MinIO"

**Causes**:
- MinIO endpoint unreachable
- Credentials incorrect
- Bucket permissions

**Solutions**:
1. Verify endpoint: `nc -zv minio.example.com 9000`
2. Check credentials in `.env`
3. Verify bucket exists: `mc ls minio/server-agent`

## Performance Considerations

### Processing Queue

- Polls every 5 seconds (configurable)
- Processes max 10 artifacts per cycle
- ~100ms per artifact (network overhead)
- Throughput: ~120 media items/minute in ideal conditions

### Memory Usage

- Each large image resized in memory (temporary BytesIO object)
- Typical peak: 20-50MB for concurrent processing
- PDF extraction loads entire document in memory

### Scalability

For high-volume media processing:

1. **Increase poll frequency**: `MediaProcessor(poll_interval_ms=1000)`
2. **Scale processing**: Run multiple MediaProcessor instances (requires Redis for coordination)
3. **Use MinIO**: Offload storage to S3-compatible backend
4. **Optimize models**: Use Whisper small/medium instead of large

## Future Enhancements

- [ ] Video processing (FFmpeg integration)
- [ ] Webhook-based processing notifications
- [ ] Processing priority queues
- [ ] Distributed processing with Redis
- [ ] Batch processing for multiple artifacts
- [ ] Custom model support (Hugging Face)
- [ ] Processing statistics dashboard
