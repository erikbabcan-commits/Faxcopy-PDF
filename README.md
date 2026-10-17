# Faxcopy-PDF / PressPilot MVP

DTP preflight automation pilot: PDF inspection, workflow, audit reports, Python FastAPI backend and TypeScript dashboard.

## Deployment architecture

- Vercel: static frontend only.
- Separate container host: Python API, persistent database and PDF scanner worker.
- Never expose the backend or PDF files without authentication and tenant isolation.

**Status:** Repository initialization. Full source import and production deployment are pending. Do not treat this repository as a functioning deployment.
