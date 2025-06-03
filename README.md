# Meeting Transcription Backend

A lightweight backend service that converts Italian or English meeting audio into accurate, speaker-diarized transcripts with automatic summaries.

## Features

- **Multi-language Support**: Italian and English transcription
- **Speaker Diarization**: Automatic speaker identification and labeling
- **Audio Processing**: Handles multiple audio formats (MP3, M4A, WAV, FLAC)
- **Automatic Summarization**: AI-generated meeting summaries and action items
- **User Authentication**: JWT-based authentication with email/password
- **Cloud Storage**: Secure audio storage with automatic cleanup
- **Async Processing**: Non-blocking audio processing with status updates
- **Usage Tracking**: Monitor transcription usage for billing

## Tech Stack

- **Framework**: FastAPI with Python 3.12
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Audio Processing**: Google Cloud Speech-to-Text API with speaker diarization
- **Storage**: Google Cloud Storage with 7-day TTL
- **AI Summary**: Google Cloud Vertex AI (Gemini)
- **Authentication**: JWT with Argon2 password hashing
- **Deployment**: Docker container for Cloud Run

## API Endpoints

### Authentication
- `POST /auth/signup` - User registration
- `POST /auth/login` - User login

### Transcription
- `POST /audio` - Upload audio file for transcription
- `GET /transcripts` - List user's transcripts
- `GET /transcripts/{id}` - Get specific transcript details

### Health
- `GET /` - Health check endpoint

## Quick Start

### Prerequisites
- Python 3.12+
- PostgreSQL database
- Google Cloud Project with enabled APIs:
  - Speech-to-Text API
  - Cloud Storage API
  - Vertex AI API

### Environment Variables

Create a `.env` file with the following variables:

```bash
# Database
DATABASE_URL=postgresql://username:password@localhost:5432/meeting_transcription

# JWT Authentication
JWT_SECRET_KEY=your-secure-secret-key

# Google Cloud
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GCS_BUCKET_NAME=meeting-transcription-audio

# Application
PORT=8000
DEBUG=false
```

### Installation

1. **Clone and install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up Google Cloud credentials:**
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
   ```

3. **Create Google Cloud Storage bucket:**
   ```bash
   gsutil mb gs://your-bucket-name
   gsutil lifecycle set lifecycle.json gs://your-bucket-name
   ```

4. **Run database migrations:**
   ```bash
   python -c "from database import create_tables; create_tables()"
   ```

5. **Start the server:**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

### Docker Deployment

1. **Build the image:**
   ```bash
   docker build -t meeting-transcription-backend .
   ```

2. **Run the container:**
   ```bash
   docker run -p 8000:8000 \
     -e DATABASE_URL="postgresql://..." \
     -e JWT_SECRET_KEY="..." \
     -e GOOGLE_CLOUD_PROJECT="..." \
     -e GCS_BUCKET_NAME="..." \
     -v /path/to/credentials.json:/app/credentials.json \
     -e GOOGLE_APPLICATION_CREDENTIALS="/app/credentials.json" \
     meeting-transcription-backend
   ```

## Usage Example

### 1. Register a user
```bash
curl -X POST "http://localhost:8000/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepassword"}'
```

### 2. Upload audio for transcription
```bash
curl -X POST "http://localhost:8000/audio" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "audio=@meeting.mp3" \
  -F "language=en"
```

### 3. Check transcription status
```bash
curl -X GET "http://localhost:8000/transcripts" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 4. Get transcript details
```bash
curl -X GET "http://localhost:8000/transcripts/{transcript_id}" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Audio Processing

- **Supported formats**: MP3, M4A, WAV, FLAC
- **Maximum duration**: No hard limit, processed in 5-minute chunks
- **Speaker diarization**: Automatic with up to 10 speakers
- **Processing time**: ~3 minutes for 60-minute meeting
- **Storage**: Raw audio kept for 7 days, then auto-deleted

## Database Schema

### Users Table
- `id` (UUID, Primary Key)
- `email` (String, Unique)
- `password_hash` (String)
- `created_at` (DateTime)

### Transcripts Table
- `id` (UUID, Primary Key)
- `user_id` (UUID, Foreign Key)
- `language` (String, 'it' or 'en')
- `original_filename` (String)
- `gcs_uri` (String)
- `status` (String: pending/processing/done/error)
- `duration_seconds` (Integer)
- `speaker_count` (Integer)
- `transcript_text` (Text)
- `summary_text` (Text)
- `created_at` (DateTime)
- `completed_at` (DateTime)

### Usage Table
- `user_id` (UUID, Primary Key)
- `period_start` (Date, Primary Key)
- `seconds_transcribed` (Integer)

## Configuration

Key configuration options in `config.py`:

- **JWT_EXPIRE_MINUTES**: Token expiration time (default: 7 days)
- **MAX_CHUNK_DURATION_MS**: Audio chunk size (default: 5 minutes)
- **ALLOWED_ORIGINS**: CORS configuration
- **DEBUG**: Enable debug mode

## Security Features

- JWT authentication with secure token generation
- Argon2 password hashing
- User isolation (users only see their own transcripts)
- HTTPS enforcement in production
- Input validation and sanitization
- Rate limiting (recommended for production)

## Monitoring & Logging

- Structured logging with timestamps
- Health check endpoint for uptime monitoring
- Request/response logging
- Error tracking and alerting
- Usage metrics for billing

## Deployment

### Google Cloud Run
1. Build and push to Artifact Registry
2. Deploy to Cloud Run with appropriate environment variables
3. Configure Cloud SQL for PostgreSQL
4. Set up IAM permissions for GCS and Speech API

### Infrastructure as Code
- Use Terraform for Google Cloud resources
- Include VPC, Cloud SQL, Cloud Storage, and IAM configurations
- Set up Cloud Monitoring for alerts

## Development

### Running Tests
```bash
pytest tests/
```

### Code Quality
```bash
black .
flake8 .
mypy .
```

### Database Migrations
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues and questions:
- Create an issue in the repository
- Check the project documentation
- Review the troubleshooting guide

---

**Note**: This is an MVP implementation. For production use, consider adding features like rate limiting, advanced monitoring, multi-tenant support, and additional security measures. 