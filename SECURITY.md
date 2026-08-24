# Security Policy

## Reporting a vulnerability

Call recordings and transcripts are sensitive data, and this project processes both. If you find a security vulnerability, **do not open a public issue**. Report it privately by emailing the maintainers (see the repository metadata) or opening a GitHub Security Advisory.

Please include:

- Affected component and version
- Steps to reproduce
- Impact assessment (data exposure? RCE? tenant isolation bypass?)

## Security posture

### Secrets

- API keys are read from the environment only (`ELEVENLABS_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, …).
- Secrets are never committed, logged, embedded in source, exposed via API responses, shipped in Docker images, or accessible from browser code.
- `.env` and `.env.*` are git-ignored; only `.env.example` (names, no values) is tracked.

### Data handling

- Call recordings are private: tenant-isolated, private/signed storage in production, never public.
- Complete transcripts are not logged by default.
- `DELETE /api/v1/calls/{id}` deletes the call and associated data per the retention policy.
- Multi-tenancy is designed in from day one (`organization_id` scoping); Supabase RLS is the production enforcement layer.

### Operations

- Upload limits and content-type validation are applied at the API boundary.
- Rate limiting should be enabled behind a reverse proxy in production.
- Audit trail: every analysis records model/provider/prompt/rubric/pipeline versions and AI usage.

## Supported versions

Security fixes land on the latest release. We do not maintain long-term support branches.

## Responsible disclosure

We will acknowledge reports within 3 business days and work toward a coordinated fix and advisory.
