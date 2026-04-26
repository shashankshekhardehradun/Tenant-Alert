output "raw_bucket_name" {
  value = google_storage_bucket.raw_data.name
}

output "artifacts_bucket_name" {
  value = google_storage_bucket.artifacts.name
}

output "workload_service_account_email" {
  value = google_service_account.workload_sa.email
}
