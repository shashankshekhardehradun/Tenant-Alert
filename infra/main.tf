locals {
  datasets = ["bronze", "silver", "gold", "ml"]
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

resource "google_service_account" "workload_sa" {
  account_id   = "tenant-alert-${var.environment}"
  display_name = "Tenant Alert workload service account"
}

resource "google_project_iam_member" "bq_user" {
  project = var.project_id
  role    = "roles/bigquery.user"
  member  = "serviceAccount:${google_service_account.workload_sa.email}"
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
