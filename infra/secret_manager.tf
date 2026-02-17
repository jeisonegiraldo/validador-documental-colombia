# ── Gemini API key in Secret Manager ────────────────────────────────
# Only the container is managed by Terraform.
# Load the actual secret value manually:
#   echo -n "YOUR_KEY" | gcloud secrets versions add gemini-api-key --data-file=- --project=validador-documental-col
resource "google_secret_manager_secret" "gemini_api_key" {
  project   = google_project.this.project_id
  secret_id = "gemini-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}
