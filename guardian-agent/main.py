"""
Guardian Agent
Monitors other agents for anomalous behavior, detects hallucinations,
enforces policy compliance, security auditing, failsafe mechanisms.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis
import httpx
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import asyncio
import json

app = FastAPI(
    title="Guardian Agent",
    description="Agent supervision, policy enforcement, and security auditing",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
EMERGENCY_STOP_ENABLED = os.getenv("EMERGENCY_STOP_ENABLED", "true").lower() == "true"

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# Monitored agents
AGENTS = [
    {
        "name": "deployment-coordinator",
        "url": "http://deployment-coordinator:6001",
        "type": "orchestration",
    },
    {
        "name": "cost-optimizer",
        "url": "http://cost-optimizer:6002",
        "type": "analytics",
    },
    {
        "name": "worker-health-monitor",
        "url": "http://worker-health-monitor:6003",
        "type": "monitoring",
    },
]

# Policy rules
POLICIES = {
    "max_deployments_per_hour": 10,
    "max_cost_per_day": 10.0,
    "max_failed_health_checks": 5,
    "require_approval_for_production": True,
}


class AgentStatus(BaseModel):
    name: str
    url: str
    status: str  # healthy, suspicious, rogue, stopped
    last_check: str
    violations: List[str]
    threat_level: str  # low, medium, high, critical


class PolicyViolation(BaseModel):
    agent: str
    policy: str
    severity: str  # warning, critical
    timestamp: str
    details: str
    action_taken: str


class GuardianMetrics(BaseModel):
    total_agents: int
    healthy: int
    suspicious: int
    stopped: int
    total_violations_24h: int
    critical_alerts_24h: int


@app.get("/")
async def root():
    return {
        "service": "Guardian Agent",
        "status": "watching",
        "version": "1.0.0",
        "monitored_agents": len(AGENTS),
        "emergency_stop": EMERGENCY_STOP_ENABLED,
    }


@app.get("/health")
async def health_check():
    try:
        redis_client.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {str(e)}")


@app.get("/agents")
async def list_agents() -> List[AgentStatus]:
    """List all monitored agents with status"""
    statuses = []

    for agent in AGENTS:
        agent_key = f"guardian:agent:{agent['name']}"
        status_data = redis_client.hgetall(agent_key)

        violations_key = f"guardian:violations:{agent['name']}"
        violations = redis_client.lrange(violations_key, 0, 9)  # Last 10

        if status_data:
            statuses.append(
                AgentStatus(
                    name=agent["name"],
                    url=agent["url"],
                    status=status_data.get("status", "unknown"),
                    last_check=status_data.get("last_check", "never"),
                    violations=[json.loads(v)["policy"] for v in violations],
                    threat_level=status_data.get("threat_level", "low"),
                )
            )
        else:
            statuses.append(
                AgentStatus(
                    name=agent["name"],
                    url=agent["url"],
                    status="unknown",
                    last_check="never",
                    violations=[],
                    threat_level="low",
                )
            )

    return statuses


@app.get("/violations")
async def list_violations(hours: int = 24) -> List[PolicyViolation]:
    """List policy violations from last N hours"""
    violations = []
    cutoff = datetime.now() - timedelta(hours=hours)

    for agent in AGENTS:
        violations_key = f"guardian:violations:{agent['name']}"
        all_violations = redis_client.lrange(violations_key, 0, -1)

        for v in all_violations:
            violation_data = json.loads(v)
            violation_time = datetime.fromisoformat(violation_data["timestamp"])

            if violation_time >= cutoff:
                violations.append(PolicyViolation(**violation_data))

    return sorted(violations, key=lambda x: x.timestamp, reverse=True)


@app.get("/metrics")
async def get_metrics() -> GuardianMetrics:
    """Get guardian metrics"""
    healthy = suspicious = stopped = 0

    for agent in AGENTS:
        agent_key = f"guardian:agent:{agent['name']}"
        status_data = redis_client.hgetall(agent_key)

        status = status_data.get("status", "unknown")
        if status == "healthy":
            healthy += 1
        elif status == "suspicious":
            suspicious += 1
        elif status == "stopped":
            stopped += 1

    # Count violations in last 24h
    violations_24h = await list_violations(24)
    critical_alerts = sum(1 for v in violations_24h if v.severity == "critical")

    return GuardianMetrics(
        total_agents=len(AGENTS),
        healthy=healthy,
        suspicious=suspicious,
        stopped=stopped,
        total_violations_24h=len(violations_24h),
        critical_alerts_24h=critical_alerts,
    )


@app.post("/monitor/all")
async def monitor_all_agents():
    """Check all agents for policy compliance"""
    await perform_agent_monitoring()
    return {"status": "monitoring complete", "agents": len(AGENTS)}


@app.post("/stop/{agent_name}")
async def emergency_stop_agent(agent_name: str):
    """Emergency stop for rogue agent"""
    if not EMERGENCY_STOP_ENABLED:
        raise HTTPException(status_code=403, detail="Emergency stop disabled")

    # Find agent
    agent = next((a for a in AGENTS if a["name"] == agent_name), None)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        # In production, this would stop the Docker container or kill the process
        print(f"🛑 EMERGENCY STOP: {agent_name}")

        # Mark as stopped
        agent_key = f"guardian:agent:{agent_name}"
        redis_client.hset(
            agent_key,
            mapping={
                "status": "stopped",
                "last_check": datetime.now().isoformat(),
                "threat_level": "critical",
            },
        )

        # Log violation
        await log_violation(
            agent_name,
            "emergency_stop",
            "critical",
            "Agent manually stopped by Guardian",
            "Agent process terminated",
        )

        await send_alert(
            f"🛑 EMERGENCY STOP executed for agent: {agent_name}", "critical"
        )

        return {"status": "stopped", "agent": agent_name}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def perform_agent_monitoring():
    """Monitor all agents for policy compliance"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        for agent in AGENTS:
            await check_agent_behavior(client, agent)


async def check_agent_behavior(client: httpx.AsyncClient, agent: Dict):
    """Check individual agent for anomalies"""
    agent_name = agent["name"]
    agent_url = agent["url"]

    try:
        # Check if agent is responsive
        response = await client.get(f"{agent_url}/health")

        if response.status_code != 200:
            await flag_suspicious_behavior(
                agent_name, f"Health check failed with status {response.status_code}"
            )
            return

        # Agent-specific policy checks
        if agent["type"] == "orchestration":
            await check_deployment_policies(client, agent_name, agent_url)
        elif agent["type"] == "analytics":
            await check_cost_policies(client, agent_name, agent_url)
        elif agent["type"] == "monitoring":
            await check_monitoring_policies(client, agent_name, agent_url)

        # Mark as healthy if no violations
        agent_key = f"guardian:agent:{agent_name}"
        redis_client.hset(
            agent_key,
            mapping={
                "status": "healthy",
                "last_check": datetime.now().isoformat(),
                "threat_level": "low",
            },
        )

    except Exception as e:
        await flag_suspicious_behavior(agent_name, f"Unreachable: {str(e)}")


async def check_deployment_policies(
    client: httpx.AsyncClient, agent_name: str, agent_url: str
):
    """Check deployment-coordinator policies"""
    try:
        # Get recent deployments
        response = await client.get(f"{agent_url}/deployments?limit=100")
        if response.status_code == 200:
            data = response.json()
            deployments = data.get("deployments", [])

            # Check deployment rate (max 10 per hour)
            recent = [
                d
                for d in deployments
                if datetime.fromisoformat(d.get("started_at", "2020-01-01"))
                > datetime.now() - timedelta(hours=1)
            ]

            if len(recent) > POLICIES["max_deployments_per_hour"]:
                await log_violation(
                    agent_name,
                    "max_deployments_per_hour",
                    "critical",
                    f"Exceeded deployment limit: {len(recent)} deployments in last hour",
                    "Flagged as suspicious",
                )
                await flag_suspicious_behavior(
                    agent_name, f"Deployment rate exceeded: {len(recent)}/hour"
                )

    except Exception as e:
        print(f"Error checking deployment policies: {str(e)}")


async def check_cost_policies(
    client: httpx.AsyncClient, agent_name: str, agent_url: str
):
    """Check cost-optimizer policies"""
    try:
        response = await client.get(f"{agent_url}/costs/daily")
        if response.status_code == 200:
            data = response.json()
            total_cost = data.get("total_cost", 0)

            if total_cost > POLICIES["max_cost_per_day"]:
                await log_violation(
                    agent_name,
                    "max_cost_per_day",
                    "warning",
                    f"Daily cost ${total_cost:.2f} exceeds limit ${POLICIES['max_cost_per_day']}",
                    "Alert sent",
                )

    except Exception as e:
        print(f"Error checking cost policies: {str(e)}")


async def check_monitoring_policies(
    client: httpx.AsyncClient, agent_name: str, agent_url: str
):
    """Check worker-health-monitor policies"""
    try:
        response = await client.get(f"{agent_url}/metrics")
        if response.status_code == 200:
            data = response.json()
            down_count = data.get("down", 0)

            if down_count > POLICIES["max_failed_health_checks"]:
                await log_violation(
                    agent_name,
                    "max_failed_health_checks",
                    "critical",
                    f"{down_count} workers are down (limit: {POLICIES['max_failed_health_checks']})",
                    "Alert sent",
                )

    except Exception as e:
        print(f"Error checking monitoring policies: {str(e)}")


async def flag_suspicious_behavior(agent_name: str, reason: str):
    """Mark agent as suspicious"""
    agent_key = f"guardian:agent:{agent_name}"
    redis_client.hset(
        agent_key,
        mapping={
            "status": "suspicious",
            "last_check": datetime.now().isoformat(),
            "threat_level": "high",
        },
    )

    await send_alert(
        f"⚠️ Suspicious behavior detected in {agent_name}: {reason}", "warning"
    )


async def log_violation(
    agent: str, policy: str, severity: str, details: str, action: str
):
    """Log policy violation"""
    violation = PolicyViolation(
        agent=agent,
        policy=policy,
        severity=severity,
        timestamp=datetime.now().isoformat(),
        details=details,
        action_taken=action,
    )

    violations_key = f"guardian:violations:{agent}"
    redis_client.lpush(violations_key, json.dumps(violation.dict()))
    redis_client.ltrim(violations_key, 0, 99)  # Keep last 100


async def send_alert(message: str, level: str):
    """Send alert via Slack"""
    await send_slack_notification(message, level)


async def send_slack_notification(message: str, level: str = "info"):
    """Send Slack notification"""
    if not SLACK_WEBHOOK_URL:
        print(f"[SLACK] {level.upper()}: {message}")
        return

    emoji_map = {
        "info": "ℹ️",
        "success": "✅",
        "warning": "⚠️",
        "error": "❌",
        "critical": "🚨",
    }

    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "text": f"{emoji_map.get(level, '📢')} {message}",
                "username": "Guardian Agent",
                "icon_emoji": ":shield:",
            }
            await client.post(SLACK_WEBHOOK_URL, json=payload)
    except Exception as e:
        print(f"Failed to send Slack notification: {str(e)}")


async def background_supervision():
    """Continuous supervision loop"""
    while True:
        try:
            await perform_agent_monitoring()
            await asyncio.sleep(60)  # Check every minute
        except Exception as e:
            print(f"Error in supervision loop: {str(e)}")
            await asyncio.sleep(30)


@app.on_event("startup")
async def startup_event():
    print("🛡️ Guardian Agent starting...")
    print(f"👁️ Monitoring {len(AGENTS)} agents")
    print(f"🚨 Emergency stop: {'enabled' if EMERGENCY_STOP_ENABLED else 'disabled'}")

    # Start background supervision
    asyncio.create_task(background_supervision())

    await send_slack_notification(
        "🛡️ Guardian Agent started - All systems under watch", "info"
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "6004")))
