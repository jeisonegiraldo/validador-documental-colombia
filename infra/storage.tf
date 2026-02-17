# ── GCS bucket for session document images ──────────────────────────
resource "google_storage_bucket" "docs" {
  project       = google_project.this.project_id
  name          = "${var.project_id}-docs"
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 7 # days — safety margin over 24h session TTL
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.apis["storage.googleapis.com"]]
}
