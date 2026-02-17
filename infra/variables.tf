variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "validador-documental-col"
}

variable "region" {
  description = "GCP region for all resources"
  type        = string
  default     = "us-central1"
}

variable "billing_account" {
  description = "GCP billing account ID"
  type        = string
}

variable "org_id" {
  description = "GCP organization ID (optional, leave empty for standalone project)"
  type        = string
  default     = ""
}

variable "cloud_run_image" {
  description = "Full Docker image path for the Cloud Run service"
  type        = string
  default     = "us-central1-docker.pkg.dev/validador-documental-col/backend/validador:latest"
}
