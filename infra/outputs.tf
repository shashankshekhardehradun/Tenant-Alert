output "raw_bucket_name" {
  value = google_storage_bucket.raw_data.name
}

output "artifacts_bucket_name" {
  value = google_storage_bucket.artifacts.name
}

output "workload_service_account_email" {
  value = google_service_account.workload_sa.email
}

output "artifact_registry_repository" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.containers.repository_id}"
}

output "api_url" {
  description = "Primary HTTPS URL (status.uri) for the FastAPI Cloud Run service."
  value       = length(google_cloud_run_v2_service.api) > 0 ? trimspace(google_cloud_run_v2_service.api[0].uri) : ""
}

output "api_urls" {
  description = "All HTTPS URLs Cloud Run publishes for the API service. If /healthz returns a Google HTML 404 on api_url, try the other entry (often *.<project-number>.<region>.run.app)."
  value       = length(google_cloud_run_v2_service.api) > 0 ? google_cloud_run_v2_service.api[0].urls : []
}

output "web_url" {
  description = "Primary HTTPS URL (status.uri) for the Next.js Cloud Run service."
  value       = length(google_cloud_run_v2_service.web) > 0 ? trimspace(google_cloud_run_v2_service.web[0].uri) : ""
}

output "web_urls" {
  description = "All HTTPS URLs Cloud Run publishes for the web service."
  value       = length(google_cloud_run_v2_service.web) > 0 ? google_cloud_run_v2_service.web[0].urls : []
}

output "daily_refresh_job" {
  value = try(google_cloud_run_v2_job.daily_refresh[0].name, "")
}
