# Secrets Handling

## Local development

- Store local credentials in `.env`.
- Never commit `.env`, `.env.*`, service account JSON files, private keys, or downloaded credential artifacts.
- Keep `.env.example` committed with placeholder values only.

## Required local variables

- `GCP_PROJECT_ID`
- `SODA_APP_TOKEN`
- `GOOGLE_APPLICATION_CREDENTIALS` or Application Default Credentials from `gcloud auth application-default login`
- `NEXT_PUBLIC_API_URL`

## Production

- Store runtime secrets in Google Secret Manager.
- Grant Cloud Run services `roles/secretmanager.secretAccessor` only for the secrets they need.
- Prefer Workload Identity / service account permissions over long-lived JSON keys.

## Before pushing

Run:

```powershell
python scripts/check_secrets.py
git status --short
```

If a real token was accidentally committed, rotate it immediately and remove it from git history before pushing.
