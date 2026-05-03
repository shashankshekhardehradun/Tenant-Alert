locals {
  datasets = ["bronze", "silver", "gold", "ml"]
  cors_origins_for_api = concat(
    var.cors_allow_origins,
    [for x in split(",", var.cors_allow_origins_extra) : trimspace(x) if trimspace(x) != ""],
  )
  service_env = {
    GCP_PROJECT_ID       = var.project_id
    ENVIRONMENT          = var.environment
    GCS_RAW_BUCKET       = google_storage_bucket.raw_data.name
    ETL_UPLOAD_TO_GCS    = "true"
    ETL_LOAD_TO_BIGQUERY = "true"
    ANALYTICS_USE_GOLD   = "true"
    BQ_DATASET_BRONZE    = "bronze"
    BQ_DATASET_SILVER    = "silver"
    BQ_DATASET_GOLD      = "gold"
    BQ_DATASET_ML        = "ml"
    LOCAL_DATA_DIR       = "/tmp/tenant-alert-data"
    SODA_APP_TOKEN       = var.soda_app_token
    CENSUS_API_KEY       = var.census_api_key
  }
  api_container_env = merge(local.service_env, {
    CORS_ALLOW_ORIGINS      = join(",", local.cors_origins_for_api)
    CORS_ALLOW_ORIGIN_REGEX = var.cors_allow_origin_regex
  })
}

resource "google_project_service" "services" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "bigquery.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudscheduler.googleapis.com",
    "run.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "raw_data" {
  name                        = "${var.project_id}-${var.environment}-raw"
  location                    = "US"
  force_destroy               = false
  uniform_bucket_level_access = true
}

resource "google_storage_bucket" "artifacts" {
  name                        = "${var.project_id}-${var.environment}-artifacts"
  location                    = "US"
  force_destroy               = false
  uniform_bucket_level_access = true
}

resource "google_bigquery_dataset" "datasets" {
  for_each   = toset(local.datasets)
  dataset_id = each.value
  location   = "US"
}

resource "google_artifact_registry_repository" "containers" {
  repository_id = "tenant-alert"
  location      = var.region
  format        = "DOCKER"
  description   = "Tenant Alert / NYC Roulette containers"

  depends_on = [google_project_service.services]
}

resource "google_service_account" "workload_sa" {
  account_id   = "tenant-alert-${var.environment}"
  display_name = "Tenant Alert workload service account"
}

resource "google_project_iam_member" "bq_user" {
  project = var.project_id
  role    = "roles/bigquery.user"
  member  = "serviceAccount:${google_service_account.workload_sa.email}"
}

resource "google_project_iam_member" "bq_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.workload_sa.email}"
}

resource "google_project_iam_member" "run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.workload_sa.email}"
}

resource "google_project_iam_member" "run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.workload_sa.email}"
}

resource "google_service_account_iam_member" "workload_sa_user" {
  service_account_id = google_service_account.workload_sa.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.workload_sa.email}"
}

resource "google_project_iam_member" "storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.workload_sa.email}"
}

resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.workload_sa.email}"
}

resource "google_cloud_run_v2_service" "api" {
  count               = var.api_image == "" ? 0 : 1
  name                = "tenant-alert-api-${var.environment}"
  location            = var.region
  deletion_protection = true

  template {
    service_account = google_service_account.workload_sa.email

    containers {
      image = var.api_image

      ports {
        container_port = 8080
      }

      dynamic "env" {
        for_each = local.api_container_env
        content {
          name  = env.key
          value = env.value
        }
      }
    }
  }

  depends_on = [google_project_service.services]
}

resource "google_cloud_run_v2_service_iam_member" "api_public_invoker" {
  count    = var.api_image != "" && var.api_allow_unauthenticated ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service" "web" {
  count               = var.web_image == "" ? 0 : 1
  name                = "tenant-alert-web-${var.environment}"
  location            = var.region
  deletion_protection = true

  template {
    service_account = google_service_account.workload_sa.email

    containers {
      image = var.web_image

      ports {
        container_port = 8080
      }
    }
  }

  lifecycle {
    # Omitting -var="web_image=..." used to plan count=0 and destroy this service (breaking
    # custom domain mappings). Fail the plan instead of destroying the web service.
    prevent_destroy = true
  }

  depends_on = [google_project_service.services]
}

resource "google_cloud_run_v2_service_iam_member" "web_public_invoker" {
  count    = var.web_image != "" && var.web_allow_unauthenticated ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.web[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_job" "daily_refresh" {
  count    = var.worker_image == "" ? 0 : 1
  name     = "tenant-alert-daily-refresh-${var.environment}"
  location = var.region

  template {
    template {
      service_account = google_service_account.workload_sa.email
      timeout         = "3600s"

      containers {
        image = var.worker_image

        resources {
          limits = {
            cpu    = "2"
            memory = "2Gi"
          }
        }

        dynamic "env" {
          for_each = local.service_env
          content {
            name  = env.key
            value = env.value
          }
        }
      }
    }
  }

  depends_on = [google_project_service.services]
}

resource "google_cloud_scheduler_job" "daily_refresh" {
  count       = var.worker_image == "" ? 0 : 1
  name        = "tenant-alert-daily-refresh-${var.environment}"
  description = "Run daily NYPD ingestion, dbt marts, and BQML refresh"
  schedule    = "0 7 * * *"
  time_zone   = "America/New_York"
  region      = var.region

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.daily_refresh[0].name}:run"

    oauth_token {
      service_account_email = google_service_account.workload_sa.email
    }
  }

  depends_on = [google_cloud_run_v2_job.daily_refresh]
}
