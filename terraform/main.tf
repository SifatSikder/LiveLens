# LiveLens — Terraform Infrastructure Configuration
# Deploys all GCP resources needed for the application

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# --- Enable Required APIs ---
resource "google_project_service" "apis" {
  for_each = toset([
    "aiplatform.googleapis.com",       # Vertex AI (Gemini)
    "run.googleapis.com",              # Cloud Run
    "firestore.googleapis.com",        # Firestore
    "storage.googleapis.com",          # Cloud Storage
    "artifactregistry.googleapis.com", # Container Registry
    "cloudbuild.googleapis.com",       # Cloud Build
    "secretmanager.googleapis.com",    # Secret Manager
  ])

  service            = each.value
  disable_on_destroy = false
}

# --- Cloud Storage Bucket ---
resource "google_storage_bucket" "livelens" {
  name          = "${var.project_id}-livelens"
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 30 # Auto-delete after 30 days (hackathon only)
    }
    action {
      type = "Delete"
    }
  }
}

# --- Firestore Database ---
resource "google_firestore_database" "livelens" {
  name        = "(default)"
  location_id = var.firestore_location
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.apis["firestore.googleapis.com"]]
}

# --- Artifact Registry ---
resource "google_artifact_registry_repository" "livelens" {
  location      = var.region
  repository_id = "livelens"
  format        = "DOCKER"

  depends_on = [google_project_service.apis["artifactregistry.googleapis.com"]]
}

# --- Cloud Run Backend ---
# NOTE: Initial deployment requires a container image to exist first.
# Run `gcloud builds submit` before `terraform apply` for Cloud Run resources.
# Full Cloud Run config will be added in Phase 4.

# --- Outputs ---
output "storage_bucket" {
  value = google_storage_bucket.livelens.name
}

output "artifact_registry" {
  value = google_artifact_registry_repository.livelens.name
}
