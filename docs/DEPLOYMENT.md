# ChronoReel - GCP Deployment Guide

This guide covers deploying ChronoReel to Google Cloud Run Jobs with GitHub Actions CI/CD.

## Prerequisites

- GCP Project with billing enabled
- GitHub repository
- Service Account with required permissions

---

## Step 1: GCP Setup

### 1.1 Create Artifact Registry Repository

```bash
gcloud artifacts repositories create chronoreel \
  --repository-format=docker \
  --location=asia-southeast1 \
  --description="ChronoReel Docker images"
```

### 1.2 Create Service Account for Deployment

```bash
# Create service account
gcloud iam service-accounts create chronoreel-deploy \
  --display-name="ChronoReel Deploy"

# Grant permissions
PROJECT_ID=$(gcloud config get-value project)

# Cloud Run Admin
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:chronoreel-deploy@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.admin"

# Artifact Registry Writer
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:chronoreel-deploy@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

# Service Account User (to act as runtime SA)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:chronoreel-deploy@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

### 1.3 Set Up Workload Identity Federation (Recommended)

This allows GitHub Actions to authenticate without storing keys.

```bash
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

# Create Workload Identity Pool
gcloud iam workload-identity-pools create github-pool \
  --location="global" \
  --display-name="GitHub Actions Pool"

# Create Provider for GitHub
gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com"

# Allow GitHub repo to impersonate SA
# Replace YOUR_GITHUB_USERNAME/YOUR_REPO with your actual repo
gcloud iam service-accounts add-iam-policy-binding \
  chronoreel-deploy@$PROJECT_ID.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/YOUR_GITHUB_USERNAME/YOUR_REPO"
```

### 1.4 Store Service Account Key as Secret (for runtime)

```bash
# Create a key for the runtime SA (used by the app, not deployment)
gcloud secrets create chronoreel-sa-key --replication-policy="automatic"

# Upload your service_account.json
gcloud secrets versions add chronoreel-sa-key --data-file=service_account.json

# Grant Cloud Run access to the secret
gcloud secrets add-iam-policy-binding chronoreel-sa-key \
  --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## Step 2: GitHub Secrets

Add these secrets in your GitHub repo (Settings → Secrets and variables → Actions):

| Secret | Value |
|--------|-------|
| `GCP_PROJECT_ID` | Your GCP Project ID (e.g., `chronoreel-12345`) |
| `WIF_PROVIDER` | `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider` |
| `WIF_SERVICE_ACCOUNT` | `chronoreel-deploy@PROJECT_ID.iam.gserviceaccount.com` |
| `GOOGLE_API_KEY` | Your Gemini API key |
| `FAL_KEY` | Your Fal.ai API key |

---

## Step 3: Deploy

Push to `main` branch:

```bash
git add .
git commit -m "Add deployment configuration"
git push origin main
```

GitHub Actions will automatically:
1. Build Docker image
2. Push to Artifact Registry
3. Deploy to Cloud Run Jobs

---

## Step 4: Set Up Cloud Scheduler

Create a daily trigger:

```bash
gcloud scheduler jobs create http chronoreel-daily \
  --location=asia-southeast1 \
  --schedule="0 9 * * *" \
  --time-zone="Asia/Bangkok" \
  --uri="https://asia-southeast1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/PROJECT_ID/jobs/chronoreel:run" \
  --http-method=POST \
  --oauth-service-account-email=chronoreel-deploy@PROJECT_ID.iam.gserviceaccount.com
```

This runs the job every day at 9:00 AM Bangkok time.

---

## Manual Execution

To run the job manually:

```bash
gcloud run jobs execute chronoreel --region asia-southeast1
```

To view logs:

```bash
gcloud run jobs executions list --job=chronoreel --region=asia-southeast1
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=chronoreel" --limit=50
```

---

## Troubleshooting

### Build fails with "permission denied"
- Check that `chronoreel-deploy` SA has Artifact Registry Writer role

### Job fails with "secret not found"
- Verify secret exists: `gcloud secrets list`
- Check runtime SA has Secret Accessor role

### Job timeout
- Increase timeout: `--task-timeout 60m` (up to 24h for Cloud Run Jobs)
