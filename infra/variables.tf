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
