variable "project_id" {
  description = "GCP project id"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-east1"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}

variable "api_image" {
  description = "Container image for the FastAPI Cloud Run service"
  type        = string
  default     = ""
}

variable "web_image" {
  description = "Container image for the Next.js Cloud Run service"
  type        = string
  default     = ""
}

variable "worker_image" {
  description = "Container image for the scheduled data refresh Cloud Run job"
  type        = string
  default     = ""
}

variable "soda_app_token" {
  description = "Optional Socrata app token for scheduled ingestion"
  type        = string
  default     = ""
  sensitive   = true
}

variable "census_api_key" {
  description = "Optional Census API key for scheduled ingestion"
  type        = string
  default     = ""
  sensitive   = true
}

variable "cors_allow_origins" {
  description = "Comma-joined list for FastAPI CORS (exact origins). Add https://your-domain after custom domain mapping."
  type        = list(string)
  default = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
  ]
}

variable "cors_allow_origin_regex" {
  description = "Optional regex so Cloud Run default https://*.a.run.app web origins can call the API without a second apply. Set to empty string to disable."
  type        = string
  default     = "https://.*\\.a\\.run\\.app$"
}

variable "api_allow_unauthenticated" {
  description = "Grant roles/run.invoker to allUsers on the API service (browser + health checks). Disable if org policy forbids public Cloud Run."
  type        = bool
  default     = true
}

variable "web_allow_unauthenticated" {
  description = "Grant roles/run.invoker to allUsers on the web service."
  type        = bool
  default     = true
}
