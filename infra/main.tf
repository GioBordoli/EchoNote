# Cloud SQL PostgreSQL instance
resource "google_sql_database_instance" "pg" {
  name             = "echonote-transcripts-db"
  database_version = "POSTGRES_15"
  region           = var.region

  settings {
    tier = "db-g1-small"
    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id
    }
    backup_configuration {
      enabled    = true
      start_time = "03:00"
    }
    database_flags {
      name  = "log_statement"
      value = "all"
    }
  }

  deletion_protection = false # Set to true in production
}

# Database
resource "google_sql_database" "database" {
  name     = "transcripts"
  instance = google_sql_database_instance.pg.name
}

# Database user
resource "google_sql_user" "app" {
  name     = "appuser"
  instance = google_sql_database_instance.pg.name
  password = var.db_password
}

# VPC for Cloud SQL private IP
resource "google_compute_network" "vpc" {
  name                    = "echonote-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = "echonote-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.vpc.id
}

# Private service connection for Cloud SQL
resource "google_compute_global_address" "private_ip_address" {
  name          = "private-ip-address"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_address.name]
}

# JWT Secret in Secret Manager
resource "google_secret_manager_secret" "jwt" {
  secret_id = "jwt-secret"
  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "jwt_value" {
  secret      = google_secret_manager_secret.jwt.id
  secret_data = "PLACEHOLDER_JWT_SECRET_CHANGE_ME"
}

# Database password secret
resource "google_secret_manager_secret" "db_password" {
  secret_id = "db-password"
  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "db_password_value" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = var.db_password
}

# Google Cloud Storage bucket for audio files
resource "google_storage_bucket" "audio" {
  name          = "${var.project_id}-audio"
  location      = var.region
  force_destroy = true

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 7 # 7-day TTL as specified in requirements
    }
  }

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD", "PUT", "POST", "DELETE"]
    response_header = ["*"]
    max_age_seconds = 3600
  }
}

# Service account for Cloud Run
resource "google_service_account" "transcripts_api" {
  account_id   = "transcripts-api-sa"
  display_name = "EchoNote Transcripts API Service Account"
}

# IAM bindings for the service account
resource "google_project_iam_member" "transcripts_api_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.transcripts_api.email}"
}

resource "google_project_iam_member" "transcripts_api_storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.transcripts_api.email}"
}

resource "google_project_iam_member" "transcripts_api_speech_admin" {
  project = var.project_id
  role    = "roles/speech.admin"
  member  = "serviceAccount:${google_service_account.transcripts_api.email}"
}

resource "google_project_iam_member" "transcripts_api_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.transcripts_api.email}"
}

# Secret Manager access
resource "google_secret_manager_secret_iam_member" "jwt_secret_access" {
  secret_id = google_secret_manager_secret.jwt.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.transcripts_api.email}"
}

resource "google_secret_manager_secret_iam_member" "db_password_access" {
  secret_id = google_secret_manager_secret.db_password.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.transcripts_api.email}"
} 