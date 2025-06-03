output "cloud_sql_connection_name" {
  description = "Cloud SQL connection name for Cloud Run"
  value       = google_sql_database_instance.pg.connection_name
}

output "storage_bucket_name" {
  description = "Google Cloud Storage bucket name for audio files"
  value       = google_storage_bucket.audio.name
}

output "service_account_email" {
  description = "Service account email for Cloud Run"
  value       = google_service_account.transcripts_api.email
}

output "database_url" {
  description = "Database connection URL for Cloud Run"
  value       = "postgresql+asyncpg://appuser:PASSWORD_FROM_SECRET@/transcripts?host=/cloudsql/${google_sql_database_instance.pg.connection_name}"
  sensitive   = true
} 