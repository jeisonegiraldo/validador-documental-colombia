# ── Service account for Cloud Run ────────────────────────────────────
resource "google_service_account" "cloud_run" {
  project      = google_project.this.project_id
  account_id   = "validador-backend"
  display_name = "Validador Backend (Cloud Run)"

  depends_on = [google_project_service.apis["iam.googleapis.com"]]
}

# ── IAM bindings ────────────────────────────────────────────────────
resource "google_project_iam_member" "firestore" {
  project = google_project.this.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_project_iam_member" "storage" {
  project = google_project.this.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_project_iam_member" "secrets" {
  project = google_project.this.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_service_account_iam_member" "sign_blobs" {
  service_account_id = google_service_account.cloud_run.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.cloud_run.email}"
}
