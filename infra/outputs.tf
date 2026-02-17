output "project_id" {
  value = google_project.this.project_id
}

output "cloud_run_url" {
  description = "Public URL of the Cloud Run service"
  value       = google_cloud_run_v2_service.backend.uri
}

output "gcs_bucket_name" {
  value = google_storage_bucket.docs.name
}

output "artifact_registry_repo" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.backend.repository_id}"
}

output "service_account_email" {
  value = google_service_account.cloud_run.email
}
