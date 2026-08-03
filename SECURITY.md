# Security and privacy

## Credentials

- Store personal credentials only in `backend/.env`.
- Never commit `.env`, access tokens, passwords, SDK login files, databases, runtime logs, or retrieved market data.
- Use `backend/.env.example` as the public template.
- If a key is ever committed, revoke it at the provider immediately and remove it from Git history before publishing.

## Local-only configuration

The backend reads credentials from environment variables or `backend/.env`. Keys are not entered in the browser and are never placed in frontend code or browser storage.

## Data and DFA caches

The repository may include derived, provider-neutral DFA artifacts needed for an offline demonstration. Personal queries, user-authored DFAs, raw corpora, retrieved evidence, reports, database files, and source-machine paths are excluded.

## Reporting a vulnerability

Please use GitHub Security Advisories after the repository is published. Do not include real credentials or private datasets in an issue.
