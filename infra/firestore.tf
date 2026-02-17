# ── Firestore database (Native mode) ────────────────────────────────
resource "google_firestore_database" "default" {
  project     = google_project.this.project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.apis["firestore.googleapis.com"]]
}
