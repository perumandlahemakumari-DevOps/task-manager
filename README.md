# Task Manager: Local Kubernetes GitOps Portfolio

A three-tier task manager built with Python, PostgreSQL, Docker, and Kubernetes.
The project is being developed locally first, then extended with GitHub Actions,
Argo CD, Prometheus, and Grafana.

## Architecture

- Web and API tier: Flask
- Data tier: PostgreSQL
- Container runtime: Docker
- Local cluster: kind
- Deployment configuration: Kubernetes manifests in `deploy/`

## Current status

- [x] Flask API with health, readiness, and task endpoints
- [x] PostgreSQL-backed task storage
- [x] Docker image build
- [x] Local kind cluster deployment
- [ ] GitHub Actions CI and image publishing
- [ ] Argo CD GitOps deployment
- [ ] Prometheus and Grafana monitoring

## Run locally

The API expects PostgreSQL and a `DATABASE_URL` environment variable.
For local development, set this variable to your local PostgreSQL connection
string before starting Flask.

## Kubernetes

The current local manifests are in `deploy/`. PostgreSQL credentials are created
directly in the local cluster and are not stored in this repository.

## Limitations

This is a learning and portfolio project running on a local kind cluster. It is
not a production deployment. PostgreSQL currently runs as a single replica.
