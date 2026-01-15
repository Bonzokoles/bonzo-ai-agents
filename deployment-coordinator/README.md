# Deployment Coordinator Agent

Automated deployment orchestration for Cloudflare Workers - monitors GitHub Actions workflows, auto-deploys green builds, and performs automatic rollback on errors.

## Features

- 🔍 **GitHub Actions Monitoring** - Tracks workflow runs across 4 repositories
- 🚀 **Auto-Deployment** - Deploys successful builds to Cloudflare Workers
- ⏮️ **Automatic Rollback** - Reverts to previous version on deployment failures
- 📢 **Slack Notifications** - Real-time alerts for all deployment events
- 📊 **Redis Queue** - Async task processing with deployment history
- 🏥 **Health Checks** - Built-in health endpoint for monitoring

## Architecture

```
GitHub Actions (success) → Deployment Coordinator → Cloudflare Workers API
                                 ↓
                            Redis Queue (db 1)
                                 ↓
                          Slack Notifications
```

## API Endpoints

### Core Endpoints

- `GET /` - Service info and status
- `GET /health` - Health check (Redis connectivity)

### Deployment Management

- `GET /deployments` - List recent deployments (limit parameter)
- `GET /deployments/{id}` - Get deployment details
- `POST /deployments/trigger` - Manually trigger deployment

### Monitoring

- `POST /monitor/workflows` - Check all repos for green builds

## Environment Variables

See `.env.example` for required configuration.

## Docker Deployment

```bash
# Build image
docker build -t deployment-coordinator .

# Run container
docker run -p 6001:6001 --env-file .env deployment-coordinator
```

## Usage

### Manual Deployment

```bash
curl -X POST http://localhost:6001/deployments/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "JIMBO_devz_inc_HUB",
    "workflow": "deploy-hub.yml",
    "commit_sha": "1829945abc",
    "branch": "main"
  }'
```

### Check Workflows

```bash
curl -X POST http://localhost:6001/monitor/workflows
```

### List Deployments

```bash
curl http://localhost:6001/deployments?limit=10
```

## Monitored Repositories

1. **JIMBO_devz_inc_HUB** - Hub deployment + PUMO worker
2. **zen-bro-wser.org** - Zen Browser website
3. **my-bonzo-ai-blog** - AI Blog deployment
4. **luc-de-zen-on** - Lucjan Moa website

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
uvicorn main:app --reload --port 6001
```

## Integration with Docker Compose

Service runs on port **6001** and depends on Redis (db 1).

```yaml
deployment-coordinator:
  build: ./agents/deployment-coordinator
  ports:
    - "6001:6001"
  depends_on:
    - redis
  environment:
    - REDIS_URL=redis://redis:6379/1
```
