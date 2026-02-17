# ── Artifact Registry for Docker images ─────────────────────────────
resource "google_artifact_registry_repository" "backend" {
  project       = google_project.this.project_id
  location      = var.region
  repository_id = "backend"
  format        = "DOCKER"
  description   = "Docker images for the validador backend"

  depends_on = [google_project_service.apis["artifactregistry.googleapis.com"]]
}
