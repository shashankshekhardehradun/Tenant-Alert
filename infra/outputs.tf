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
  description = "Public HTTPS URL for the FastAPI Cloud Run service (must look like https://....a.run.app — not Artifact Registry)."
  value       = try(trimspace(google_cloud_run_v2_service.api[0].uri), "")
}

output "web_url" {
  description = "Public HTTPS URL for the Next.js Cloud Run service."
  value       = try(trimspace(google_cloud_run_v2_service.web[0].uri), "")
}

output "daily_refresh_job" {
  value = try(google_cloud_run_v2_job.daily_refresh[0].name, "")
}
