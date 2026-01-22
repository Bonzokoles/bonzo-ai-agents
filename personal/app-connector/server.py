"""
App Connector Agent - Komunikacja między aplikacjami
Port: 8202
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import httpx
import json
from pathlib import Path

app = FastAPI(title="App Connector Agent")

# Data storage
DATA_DIR = Path("U:/The_yellow_hub/data/app-connector")
DATA_DIR.mkdir(parents=True, exist_ok=True)

SYNC_LOG_FILE = DATA_DIR / "sync_log.json"

# App endpoints configuration
APP_ENDPOINTS = {
    "jimbo77_com": {
        "base_url": "https://jimbo77.com",
        "api_url": "https://api.jimbo77.org",
    },
    "jimbo77_org": {
        "base_url": "https://jimbo77.org",
        "api_url": "https://api.jimbo77.org",
    },
    "pumo": {
        "base_url": "https://meblepumo.iai-shop.com",
        "worker_url": "https://pumo-rag.stolarnia-ams.workers.dev",
    },
    "mybonzo_blog": {"base_url": "https://www.mybonzoaiblog.com"},
    "zen_browser": {"base_url": "https://zen-bro-wser.org"},
    "dashboard": {
        "base_url": "https://dashboard.jimbo77.org",
        "local_url": "http://localhost:3880",
    },
}


# Models
class SyncRequest(BaseModel):
    source: str
    target: str
    data_type: str
    data: Optional[Dict[str, Any]] = None


# Helper functions
def load_json(file_path: Path) -> List[dict]:
    if not file_path.exists():
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(file_path: Path, data: List[dict]):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def log_sync(source: str, target: str, data_type: str, success: bool, details: dict):
    """Log sync operation"""
    logs = load_json(SYNC_LOG_FILE)

    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "source": source,
        "target": target,
        "data_type": data_type,
        "success": success,
        "details": details,
    }

    logs.append(log_entry)

    # Keep last 1000 entries
    if len(logs) > 1000:
        logs = logs[-1000:]

    save_json(SYNC_LOG_FILE, logs)


# Routes
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "agent": "app-connector",
        "port": 8202,
        "connected_apps": list(APP_ENDPOINTS.keys()),
    }


@app.post("/execute")
async def execute(request: dict):
    """Main execution endpoint"""
    command = request.get("command")
    args = request.get("args", {})

    if command == "sync_data":
        return await sync_data(**args)
    elif command == "forward_event":
        return await forward_event(**args)
    elif command == "aggregate_stats":
        return await aggregate_stats(**args)
    elif command == "get_sync_log":
        return await get_sync_log(**args)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown command: {command}")


async def sync_data(
    source: str, target: str, data_type: str, data: Optional[Dict] = None
):
    """Sync data between apps"""

    if source not in APP_ENDPOINTS:
        return {"success": False, "error": f"Unknown source: {source}"}
    if target not in APP_ENDPOINTS:
        return {"success": False, "error": f"Unknown target: {target}"}

    try:
        # Fetch data from source if not provided
        if not data:
            data = await fetch_from_source(source, data_type)

        # Transform data if needed
        transformed_data = transform_data(data, source, target, data_type)

        # Push to target
        result = await push_to_target(target, data_type, transformed_data)

        log_sync(
            source,
            target,
            data_type,
            True,
            {
                "records": (
                    len(transformed_data) if isinstance(transformed_data, list) else 1
                ),
                "result": result,
            },
        )

        return {
            "success": True,
            "data": {
                "source": source,
                "target": target,
                "data_type": data_type,
                "synced": True,
                "details": result,
            },
        }

    except Exception as e:
        log_sync(source, target, data_type, False, {"error": str(e)})

        return {"success": False, "error": str(e)}


async def fetch_from_source(source: str, data_type: str):
    """Fetch data from source app"""
    endpoint_config = APP_ENDPOINTS[source]

    # Determine endpoint based on data_type
    if data_type == "blog_posts" and source == "mybonzo_blog":
        url = f"{endpoint_config['base_url']}/api/posts"
    elif data_type == "pumo_products" and source == "pumo":
        url = f"{endpoint_config['worker_url']}/api/products"
    elif data_type == "agent_status" and source == "dashboard":
        url = f"{endpoint_config['local_url']}/api/agents/status"
    else:
        raise ValueError(f"Unknown data_type for source: {data_type} / {source}")

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


async def push_to_target(target: str, data_type: str, data: Any):
    """Push data to target app"""
    endpoint_config = APP_ENDPOINTS[target]

    # Determine endpoint based on data_type
    if data_type == "blog_posts" and target == "jimbo77_org":
        url = f"{endpoint_config['api_url']}/api/content/import"
    elif data_type == "pumo_stats" and target == "dashboard":
        url = f"{endpoint_config['local_url']}/api/stats/pumo"
    elif data_type == "agent_metrics" and target == "jimbo77_com":
        url = f"{endpoint_config['api_url']}/api/metrics/agents"
    else:
        # Generic webhook
        url = (
            f"{endpoint_config.get('api_url', endpoint_config['base_url'])}/api/webhook"
        )

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=data)
        response.raise_for_status()
        return response.json()


def transform_data(data: Any, source: str, target: str, data_type: str):
    """Transform data between different app formats"""

    # Example transformations
    if data_type == "blog_posts":
        # Transform blog post format
        if isinstance(data, list):
            return [
                {
                    "title": post.get("title"),
                    "content": post.get("content"),
                    "published_at": post.get("date"),
                    "author": "MyBonzo",
                    "source": source,
                }
                for post in data
            ]

    elif data_type == "pumo_stats":
        # Aggregate PUMO stats
        return {
            "total_products": data.get("product_count", 0),
            "total_searches": data.get("search_count", 0),
            "avg_response_time": data.get("avg_time", 0),
            "source": source,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # Default: pass through
    return data


async def forward_event(source: str, target: str, event_type: str, payload: Dict):
    """Forward event from one app to another"""
    try:
        endpoint_config = APP_ENDPOINTS[target]
        url = (
            f"{endpoint_config.get('api_url', endpoint_config['base_url'])}/api/events"
        )

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                url,
                json={
                    "event_type": event_type,
                    "source": source,
                    "payload": payload,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
            response.raise_for_status()

            return {
                "success": True,
                "data": {
                    "forwarded": True,
                    "target": target,
                    "response": response.json(),
                },
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


async def aggregate_stats(apps: Optional[List[str]] = None):
    """Aggregate stats from multiple apps"""
    if not apps:
        apps = list(APP_ENDPOINTS.keys())

    stats = {}

    for app in apps:
        try:
            # Try to fetch health/stats endpoint
            endpoint_config = APP_ENDPOINTS[app]
            url = f"{endpoint_config.get('api_url', endpoint_config['base_url'])}/api/health"

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)
                response.raise_for_status()
                stats[app] = response.json()

        except Exception as e:
            stats[app] = {"error": str(e), "status": "unreachable"}

    return {
        "success": True,
        "data": {
            "apps_checked": len(apps),
            "stats": stats,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }


async def get_sync_log(
    limit: int = 100, source: Optional[str] = None, target: Optional[str] = None
):
    """Get sync operation log"""
    logs = load_json(SYNC_LOG_FILE)

    # Filter
    if source:
        logs = [l for l in logs if l["source"] == source]
    if target:
        logs = [l for l in logs if l["target"] == target]

    # Sort by timestamp desc
    logs.sort(key=lambda x: x["timestamp"], reverse=True)

    # Limit
    logs = logs[:limit]

    return {"success": True, "data": {"total": len(logs), "logs": logs}}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8202)
