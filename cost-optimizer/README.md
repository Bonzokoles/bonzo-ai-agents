# Cost Optimizer Agent

Budget tracking and cost optimization for Cloudflare Workers, R2, KV, and AI services (OpenRouter).

## Features

- 💰 **Cost Tracking** - Monitors Cloudflare (Workers/R2/KV) and OpenRouter costs
- 📊 **Budget Alerts** - Slack notifications when thresholds exceeded (75%, 90%)
- 💡 **Optimization Tips** - AI-powered suggestions to reduce costs
- 📈 **Usage Analytics** - Daily and monthly cost reports
- 🎯 **Budget Enforcement** - Configurable daily/monthly limits

## Architecture

```
Cloudflare Analytics API → Cost Optimizer → Budget Analysis
OpenRouter Usage API     ↗                ↓
                                    Slack Alerts
                                          ↓
                                 Optimization Suggestions
```

## API Endpoints

### Cost Reports

- `GET /costs/daily` - Today's spending breakdown
- `GET /costs/monthly` - Month-to-date costs

### Optimization

- `GET /optimize/suggestions` - Get cost-saving recommendations

### Health

- `GET /` - Service info
- `GET /health` - Health check

## Cost Breakdown

### Cloudflare Workers

- **Free tier**: 100,000 requests/day
- **Paid**: $0.50 per million requests
- **Current**: ~$0.62/day (from Workers Monitoring)

### Cloudflare R2 Storage

- **Storage**: $0.015/GB/month
- **Operations**: Class A $4.50/M, Class B $0.36/M

### Cloudflare KV

- **Storage**: $0.50/GB/month
- **Reads**: $0.50 per 10M reads

### OpenRouter AI

- **DeepSeek R1**: $0.55/M input, $2.19/M output
- **GPT-4**: $60/M input, $120/M output

## Budget Configuration

Default budgets (configurable via env vars):

- **Daily**: $5.00
- **Monthly**: $100.00

Alert thresholds:

- **Warning**: 75% budget used
- **Critical**: 90% budget used

## Optimization Suggestions

Agent provides actionable tips:

1. **Cache API** - Reduce worker invocations
2. **R2 Lifecycle** - Auto-delete old objects
3. **KV Batching** - Batch reads to reduce operations
4. **Model Selection** - Use cheaper AI models

## Docker Deployment

```bash
docker build -t cost-optimizer .
docker run -p 6002:6002 --env-file .env cost-optimizer
```

## Usage

### Get Daily Costs

```bash
curl http://localhost:6002/costs/daily
```

Response:

```json
{
  "period": "daily",
  "cloudflare_workers_cost": 0.62,
  "cloudflare_r2_cost": 0.08,
  "cloudflare_kv_cost": 0.12,
  "openrouter_cost": 1.25,
  "total_cost": 2.07,
  "budget_limit": 5.0,
  "budget_used_percent": 41.4,
  "status": "ok"
}
```

### Get Optimization Tips

```bash
curl http://localhost:6002/optimize/suggestions
```

## Integration

Port **6002** with Redis for historical cost data (future enhancement).
