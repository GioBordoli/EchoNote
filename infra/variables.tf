variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
  default     = "echonote-461723"
}

variable "region" {
  description = "Google Cloud region"
  type        = string
  default     = "europe-west4"
}

variable "db_password" {
  description = "Password for the PostgreSQL database"
  type        = string
  sensitive   = true
} 