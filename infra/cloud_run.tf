# ── Cloud Run service ────────────────────────────────────────────────
resource "google_cloud_run_v2_service" "backend" {
  project  = google_project.this.project_id
  name     = "validador-backend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.cloud_run.email

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    containers {
      image = var.cloud_run_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = google_project.this.project_id
      }

      env {
        name  = "GCS_BUCKET_NAME"
        value = google_storage_bucket.docs.name
      }

      env {
        name  = "GEMINI_API_KEY_SECRET_NAME"
        value = google_secret_manager_secret.gemini_api_key.secret_id
      }
    }
  }

  depends_on = [
    google_project_service.apis["run.googleapis.com"],
    google_project_iam_member.firestore,
    google_project_iam_member.storage,
    google_project_iam_member.secrets,
  ]
}

# ── Allow unauthenticated access (Woztell webhook) ─────────────────
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = google_cloud_run_v2_service.backend.project
  location = google_cloud_run_v2_service.backend.location
  name     = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
