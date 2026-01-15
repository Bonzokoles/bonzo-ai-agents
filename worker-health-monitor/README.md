# Worker Health Monitor Agent

Real-time monitoring for 35 Cloudflare Workers - automatic health checks, performance tracking, and auto-restart capabilities.

## Features

- 💓 **Health Checks** - Pings all workers every 5 minutes
- ⚡ **Performance Tracking** - Response time monitoring (P50/P95)
- 🔄 **Auto-Restart** - Restarts failed workers via Cloudflare API
- 📊 **Metrics Storage** - Redis for fast metric access
- 🚨 **Instant Alerts** - Slack notifications for downtime
- 📈 **Uptime Tracking** - Exponential moving average uptime %

## Architecture

```
Background Loop (5min) → HTTP GET /health → Workers (35)
         ↓
   Redis Metrics (db 1)
         ↓
  Slack Alerts + Auto-Restart
```

## API Endpoints

### Worker Status

- `GET /workers` - List all workers with status
- `GET /workers/{name}` - Detailed status + history

### Metrics

- `GET /metrics` - Aggregated health metrics

### Manual Checks

- `POST /check/all` - Trigger immediate health check

### Health

- `GET /` - Service info
- `GET /health` - Health check

## Monitored Workers (35)

### Web Apps (5)

- hub (jimbo77.com)
- zen-browser (zen-bro-wser.org)
- blog (my-bonzo-ai-blog)
- luc-de-zen-on
- pumo-api

### Orchestration (1)

- agents-orchestrator

### (Add remaining 29 workers...)

## Health Status Definitions

- **healthy**: HTTP 200 + response time <1000ms
- **degraded**: HTTP 200 + response time 1000-3000ms
- **down**: Non-200 status or timeout

## Uptime Calculation

Exponential moving average:

```
new_uptime = prev_uptime * 0.95 + current_status * 5.0
```

This gives more weight to recent checks while maintaining history.

## Auto-Restart

When a worker is detected as `down`:

1. Send Slack alert
2. Call Cloudflare API to redeploy worker
3. Wait 2 seconds
4. Re-check status

## Metrics Example

```json
{
  "total_workers": 35,
  "healthy": 33,
  "degraded": 1,
  "down": 1,
  "avg_response_time_ms": 287.5,
  "uptime_percent": 98.7
}
```

## Docker Deployment

```bash
docker build -t worker-health-monitor .
docker run -p 6003:6003 --env-file .env worker-health-monitor
```

## Usage

### Check All Workers

```bash
curl -X POST http://localhost:6003/check/all
```

### Get Metrics

```bash
curl http://localhost:6003/metrics
```

### Worker Status

```bash
curl http://localhost:6003/workers/hub
```

## Integration

Port **6003** with continuous background monitoring loop.
