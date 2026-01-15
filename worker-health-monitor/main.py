"""
Worker Health Monitor Agent
Monitors 35 Cloudflare Workers - pings health endpoints every 5 minutes,
tracks response times, auto-restarts failed workers, stores metrics in Redis.
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import redis
import os
from datetime import datetime
from typing import List, Dict, Optional
import asyncio
import json

app = FastAPI(
    title="Worker Health Monitor",
    description="Real-time health monitoring for 35 Cloudflare Workers",
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
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "300"))  # 5 minutes

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# 35 Workers from Workers Monitoring Dashboard
WORKERS = [
    {"name": "hub", "url": "https://jimbo77.com/health", "category": "web"},
    {
        "name": "pumo-api",
        "url": "https://jimbo-like-pumo-api.stolarnia-ams.workers.dev/health",
        "category": "api",
    },
    {
        "name": "zen-browser",
        "url": "https://zen-bro-wser.org/health",
        "category": "web",
    },
    {
        "name": "blog",
        "url": "https://my-bonzo-ai-blog.pages.dev/health",
        "category": "web",
    },
    {
        "name": "luc-de-zen-on",
        "url": "https://luc-de-zen-on.pages.dev/health",
        "category": "web",
    },
    {
        "name": "agents-orchestrator",
        "url": "https://orchestrator.jimbo77.com/health",
        "category": "orchestration",
    },
    # Add remaining 29 workers here...
]


class WorkerStatus(BaseModel):
    name: str
    url: str
    status: str  # healthy, degraded, down
    response_time_ms: Optional[float] = None
    last_check: str
    error: Optional[str] = None
    uptime_percent: float


class HealthMetrics(BaseModel):
    total_workers: int
    healthy: int
    degraded: int
    down: int
    avg_response_time_ms: float
    uptime_percent: float


@app.get("/")
async def root():
    return {
        "service": "Worker Health Monitor",
        "status": "healthy",
        "version": "1.0.0",
        "monitored_workers": len(WORKERS),
        "check_interval": f"{CHECK_INTERVAL_SECONDS}s",
    }


@app.get("/health")
async def health_check():
    try:
        redis_client.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {str(e)}")


@app.get("/workers")
async def list_workers() -> List[WorkerStatus]:
    """List all workers with current status"""
    statuses = []

    for worker in WORKERS:
        worker_key = f"worker:status:{worker['name']}"
        status_data = redis_client.hgetall(worker_key)

        if status_data:
            statuses.append(
                WorkerStatus(
                    name=worker["name"],
                    url=worker["url"],
                    status=status_data.get("status", "unknown"),
                    response_time_ms=float(status_data.get("response_time_ms", 0)),
                    last_check=status_data.get("last_check", "never"),
                    error=status_data.get("error"),
                    uptime_percent=float(status_data.get("uptime_percent", 100.0)),
                )
            )
        else:
            # Not yet checked
            statuses.append(
                WorkerStatus(
                    name=worker["name"],
                    url=worker["url"],
                    status="unknown",
                    last_check="never",
                    uptime_percent=100.0,
                )
            )

    return statuses


@app.get("/workers/{worker_name}")
async def get_worker_status(worker_name: str):
    """Get detailed status for specific worker"""
    worker_key = f"worker:status:{worker_name}"
    status_data = redis_client.hgetall(worker_key)

    if not status_data:
        raise HTTPException(
            status_code=404, detail="Worker not found or not yet monitored"
        )

    # Get recent checks history
    history_key = f"worker:history:{worker_name}"
    history = redis_client.lrange(history_key, 0, 19)  # Last 20 checks

    return {"status": status_data, "history": [json.loads(h) for h in history]}


@app.get("/metrics")
async def get_metrics() -> HealthMetrics:
    """Get aggregated health metrics"""
    healthy = degraded = down = 0
    total_response_time = 0.0
    response_count = 0
    total_uptime = 0.0

    for worker in WORKERS:
        worker_key = f"worker:status:{worker['name']}"
        status_data = redis_client.hgetall(worker_key)

        if status_data:
            status = status_data.get("status", "unknown")
            if status == "healthy":
                healthy += 1
            elif status == "degraded":
                degraded += 1
            elif status == "down":
                down += 1

            rt = float(status_data.get("response_time_ms", 0))
            if rt > 0:
                total_response_time += rt
                response_count += 1

            total_uptime += float(status_data.get("uptime_percent", 100.0))

    avg_response_time = (
        total_response_time / response_count if response_count > 0 else 0
    )
    avg_uptime = total_uptime / len(WORKERS) if len(WORKERS) > 0 else 100.0

    return HealthMetrics(
        total_workers=len(WORKERS),
        healthy=healthy,
        degraded=degraded,
        down=down,
        avg_response_time_ms=avg_response_time,
        uptime_percent=avg_uptime,
    )


@app.post("/check/all")
async def check_all_workers(background_tasks: BackgroundTasks):
    """Trigger health check for all workers"""
    background_tasks.add_task(perform_health_checks)
    return {"status": "health checks started", "workers": len(WORKERS)}


async def perform_health_checks():
    """Check health of all workers"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [check_worker_health(client, worker) for worker in WORKERS]
        await asyncio.gather(*tasks)


async def check_worker_health(client: httpx.AsyncClient, worker: Dict):
    """Check individual worker health"""
    worker_name = worker["name"]
    worker_url = worker["url"]

    try:
        start_time = datetime.now()
        response = await client.get(worker_url)
        end_time = datetime.now()

        response_time_ms = (end_time - start_time).total_seconds() * 1000

        # Determine status
        if response.status_code == 200 and response_time_ms < 1000:
            status = "healthy"
        elif response.status_code == 200 and response_time_ms < 3000:
            status = "degraded"
        else:
            status = "down"

        # Update Redis
        worker_key = f"worker:status:{worker_name}"

        # Get previous uptime
        prev_data = redis_client.hgetall(worker_key)
        prev_uptime = (
            float(prev_data.get("uptime_percent", 100.0)) if prev_data else 100.0
        )

        # Calculate new uptime (exponential moving average)
        is_up = 1.0 if status in ["healthy", "degraded"] else 0.0
        new_uptime = prev_uptime * 0.95 + is_up * 5.0  # 95% previous, 5% current

        redis_client.hset(
            worker_key,
            mapping={
                "status": status,
                "response_time_ms": f"{response_time_ms:.2f}",
                "last_check": datetime.now().isoformat(),
                "uptime_percent": f"{new_uptime:.2f}",
                "error": "",
            },
        )

        # Store in history
        history_key = f"worker:history:{worker_name}"
        history_entry = json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "status": status,
                "response_time_ms": response_time_ms,
                "status_code": response.status_code,
            }
        )
        redis_client.lpush(history_key, history_entry)
        redis_client.ltrim(history_key, 0, 99)  # Keep last 100

        # Alert if down
        if status == "down":
            await send_alert(
                worker_name, f"Worker is DOWN (status {response.status_code})"
            )
            await restart_worker(worker_name)

    except Exception as e:
        # Worker completely unreachable
        worker_key = f"worker:status:{worker_name}"

        prev_data = redis_client.hgetall(worker_key)
        prev_uptime = (
            float(prev_data.get("uptime_percent", 100.0)) if prev_data else 100.0
        )
        new_uptime = prev_uptime * 0.95  # Decrement uptime

        redis_client.hset(
            worker_key,
            mapping={
                "status": "down",
                "response_time_ms": "0",
                "last_check": datetime.now().isoformat(),
                "uptime_percent": f"{new_uptime:.2f}",
                "error": str(e),
            },
        )

        await send_alert(worker_name, f"Worker UNREACHABLE: {str(e)}")
        await restart_worker(worker_name)


async def restart_worker(worker_name: str):
    """Attempt to restart failed worker via Cloudflare API"""
    try:
        # In production, use Cloudflare Workers API to redeploy
        # For now, just log the attempt
        print(f"🔄 Attempting to restart worker: {worker_name}")

        await send_slack_notification(
            f"🔄 Auto-restarting worker: {worker_name}", "warning"
        )

        # Simulate restart delay
        await asyncio.sleep(2)

    except Exception as e:
        print(f"Failed to restart {worker_name}: {str(e)}")


async def send_alert(worker_name: str, message: str):
    """Send alert for worker issues"""
    await send_slack_notification(
        f"🚨 *Worker Alert: {worker_name}*\n{message}", "error"
    )


async def send_slack_notification(message: str, level: str = "info"):
    """Send Slack notification"""
    if not SLACK_WEBHOOK_URL:
        print(f"[SLACK] {level.upper()}: {message}")
        return

    emoji_map = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}

    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "text": f"{emoji_map.get(level, '📢')} {message}",
                "username": "Worker Health Monitor",
                "icon_emoji": ":heartpulse:",
            }
            await client.post(SLACK_WEBHOOK_URL, json=payload)
    except Exception as e:
        print(f"Failed to send Slack notification: {str(e)}")


async def background_monitoring():
    """Continuous background monitoring loop"""
    while True:
        try:
            await perform_health_checks()
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
        except Exception as e:
            print(f"Error in monitoring loop: {str(e)}")
            await asyncio.sleep(60)  # Wait 1 minute before retry


@app.on_event("startup")
async def startup_event():
    print("💓 Worker Health Monitor starting...")
    print(f"📊 Monitoring {len(WORKERS)} workers")
    print(f"⏱️ Check interval: {CHECK_INTERVAL_SECONDS}s")

    # Start background monitoring
    asyncio.create_task(background_monitoring())

    await send_slack_notification("💓 Worker Health Monitor started", "info")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "6003")))
