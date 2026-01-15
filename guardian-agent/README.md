# Guardian Agent

Agent supervision, policy enforcement, and security auditing - the watchdog for all AI agents.

## Features

- 🛡️ **Agent Monitoring** - Watches 3 agents for anomalous behavior
- 📋 **Policy Enforcement** - Enforces deployment/cost/health policies
- 🚨 **Violation Detection** - Detects policy breaches in real-time
- 🛑 **Emergency Stop** - Failsafe mechanism to stop rogue agents
- 📊 **Security Auditing** - Logs all violations for review
- ⚡ **Real-time Alerts** - Slack notifications for threats

## Architecture

```
Background Loop (1min) → Check Agents (3) → Policy Compliance
         ↓
  Redis Violations Log
         ↓
  Slack Alerts + Emergency Stop
```

## Monitored Agents

1. **deployment-coordinator** (orchestration)
2. **cost-optimizer** (analytics)
3. **worker-health-monitor** (monitoring)

## Policy Rules

### Deployment Policies

- `max_deployments_per_hour`: 10
- `require_approval_for_production`: true

### Cost Policies

- `max_cost_per_day`: $10.00

### Health Policies

- `max_failed_health_checks`: 5 workers

## API Endpoints

### Agent Status

- `GET /agents` - List all agents with threat levels
- `GET /violations` - List policy violations (24h default)
- `GET /metrics` - Guardian metrics

### Actions

- `POST /monitor/all` - Trigger immediate check
- `POST /stop/{agent_name}` - Emergency stop agent

### Health

- `GET /` - Service info
- `GET /health` - Health check

## Threat Levels

- **low**: Normal operation
- **medium**: Minor policy violations
- **high**: Suspicious behavior detected
- **critical**: Rogue agent, emergency stop executed

## Agent Status

- **healthy**: Passing all policy checks
- **suspicious**: Policy violations detected
- **rogue**: Critical violations, dangerous behavior
- **stopped**: Emergency stop executed

## Policy Violation Example

```json
{
  "agent": "deployment-coordinator",
  "policy": "max_deployments_per_hour",
  "severity": "critical",
  "timestamp": "2026-01-15T15:30:00",
  "details": "Exceeded deployment limit: 15 deployments in last hour",
  "action_taken": "Flagged as suspicious"
}
```

## Emergency Stop

Guardian can execute emergency stop on rogue agents:

```bash
curl -X POST http://localhost:6004/stop/deployment-coordinator
```

This will:

1. Stop the agent process (Docker container)
2. Mark as "stopped" in Redis
3. Log critical violation
4. Send Slack alert

## Docker Deployment

```bash
docker build -t guardian-agent .
docker run -p 6004:6004 --env-file .env guardian-agent
```

## Usage

### Check Agents

```bash
curl http://localhost:6004/agents
```

### Get Violations

```bash
curl http://localhost:6004/violations?hours=24
```

### Metrics

```bash
curl http://localhost:6004/metrics
```

## Integration

Port **6004** with continuous 1-minute supervision loop.
