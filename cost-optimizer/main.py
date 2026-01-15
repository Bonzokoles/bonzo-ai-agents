"""
Cost Optimizer Agent
Tracks Cloudflare and OpenRouter costs, monitors budgets, sends alerts,
provides optimization suggestions.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import asyncio
from decimal import Decimal

app = FastAPI(
    title="Cost Optimizer",
    description="Budget tracking and cost optimization for Cloudflare + AI services",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
DAILY_BUDGET_USD = float(os.getenv("DAILY_BUDGET_USD", "5.0"))
MONTHLY_BUDGET_USD = float(os.getenv("MONTHLY_BUDGET_USD", "100.0"))


class CostReport(BaseModel):
    period: str  # daily, weekly, monthly
    cloudflare_workers_cost: float
    cloudflare_r2_cost: float
    cloudflare_kv_cost: float
    openrouter_cost: float
    total_cost: float
    budget_limit: float
    budget_used_percent: float
    status: str  # ok, warning, critical


class OptimizationSuggestion(BaseModel):
    category: str  # workers, r2, kv, ai
    severity: str  # info, warning, critical
    title: str
    description: str
    estimated_savings_usd: float


@app.get("/")
async def root():
    return {
        "service": "Cost Optimizer",
        "status": "healthy",
        "version": "1.0.0",
        "daily_budget": DAILY_BUDGET_USD,
        "monthly_budget": MONTHLY_BUDGET_USD,
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/costs/daily")
async def get_daily_costs():
    """Get today's costs"""
    try:
        cloudflare_costs = await fetch_cloudflare_costs("day")
        openrouter_costs = await fetch_openrouter_costs("day")

        total = sum(cloudflare_costs.values()) + openrouter_costs
        budget_percent = (total / DAILY_BUDGET_USD) * 100

        status = "ok"
        if budget_percent > 90:
            status = "critical"
            await send_budget_alert(total, DAILY_BUDGET_USD, "daily")
        elif budget_percent > 75:
            status = "warning"

        return CostReport(
            period="daily",
            cloudflare_workers_cost=cloudflare_costs["workers"],
            cloudflare_r2_cost=cloudflare_costs["r2"],
            cloudflare_kv_cost=cloudflare_costs["kv"],
            openrouter_cost=openrouter_costs,
            total_cost=total,
            budget_limit=DAILY_BUDGET_USD,
            budget_used_percent=budget_percent,
            status=status,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/costs/monthly")
async def get_monthly_costs():
    """Get month-to-date costs"""
    try:
        cloudflare_costs = await fetch_cloudflare_costs("month")
        openrouter_costs = await fetch_openrouter_costs("month")

        total = sum(cloudflare_costs.values()) + openrouter_costs
        budget_percent = (total / MONTHLY_BUDGET_USD) * 100

        status = "ok"
        if budget_percent > 90:
            status = "critical"
            await send_budget_alert(total, MONTHLY_BUDGET_USD, "monthly")
        elif budget_percent > 75:
            status = "warning"

        return CostReport(
            period="monthly",
            cloudflare_workers_cost=cloudflare_costs["workers"],
            cloudflare_r2_cost=cloudflare_costs["r2"],
            cloudflare_kv_cost=cloudflare_costs["kv"],
            openrouter_cost=openrouter_costs,
            total_cost=total,
            budget_limit=MONTHLY_BUDGET_USD,
            budget_used_percent=budget_percent,
            status=status,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/optimize/suggestions")
async def get_optimization_suggestions() -> List[OptimizationSuggestion]:
    """Get cost optimization suggestions"""
    suggestions = []

    # Fetch current usage stats
    cloudflare_costs = await fetch_cloudflare_costs("day")

    # Workers invocation optimization
    if cloudflare_costs["workers"] > 1.0:  # $1/day threshold
        suggestions.append(
            OptimizationSuggestion(
                category="workers",
                severity="warning",
                title="High Workers invocation rate",
                description="Consider implementing request caching to reduce invocations. Enable Cache API in workers to cache frequent requests.",
                estimated_savings_usd=0.50,
            )
        )

    # R2 storage optimization
    if cloudflare_costs["r2"] > 0.50:
        suggestions.append(
            OptimizationSuggestion(
                category="r2",
                severity="info",
                title="R2 storage costs rising",
                description="Review stored objects and implement lifecycle policies to delete old/unused files automatically.",
                estimated_savings_usd=0.25,
            )
        )

    # KV optimization
    if cloudflare_costs["kv"] > 0.30:
        suggestions.append(
            OptimizationSuggestion(
                category="kv",
                severity="info",
                title="KV read operations can be optimized",
                description="Batch KV reads where possible and implement worker-local caching for frequently accessed keys.",
                estimated_savings_usd=0.15,
            )
        )

    # AI costs optimization
    openrouter_costs = await fetch_openrouter_costs("day")
    if openrouter_costs > 2.0:
        suggestions.append(
            OptimizationSuggestion(
                category="ai",
                severity="warning",
                title="High AI API usage",
                description="Consider using cheaper models for simple tasks. Use DeepSeek R1 ($0.55/M tokens) instead of GPT-4 ($60/M tokens) where applicable.",
                estimated_savings_usd=1.50,
            )
        )

    return suggestions


async def fetch_cloudflare_costs(period: str) -> Dict[str, float]:
    """Fetch Cloudflare costs from Analytics API"""
    # In production, this would call Cloudflare GraphQL Analytics API
    # For now, return simulated costs based on Workers Monitoring data

    if period == "day":
        return {
            "workers": 0.62,  # From Workers Monitoring dashboard
            "r2": 0.08,
            "kv": 0.12,
        }
    else:  # month
        # Estimate: daily * 30
        return {"workers": 18.60, "r2": 2.40, "kv": 3.60}


async def fetch_openrouter_costs(period: str) -> float:
    """Fetch OpenRouter API usage costs"""
    if not OPENROUTER_API_KEY:
        return 0.0

    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            }

            # OpenRouter credits API endpoint
            response = await client.get(
                "https://openrouter.ai/api/v1/auth/key", headers=headers
            )

            if response.status_code == 200:
                data = response.json()
                # Calculate usage from credits
                # This is simplified - real implementation would track usage over time
                if period == "day":
                    return 1.25  # Example daily cost
                else:
                    return 37.50  # Example monthly cost
    except Exception as e:
        print(f"Error fetching OpenRouter costs: {str(e)}")

    return 0.0


async def send_budget_alert(current: float, limit: float, period: str):
    """Send Slack alert when budget threshold exceeded"""
    percent = (current / limit) * 100

    message = f"🚨 *Budget Alert - {period.upper()}*\n\n"
    message += f"Current spending: ${current:.2f}\n"
    message += f"Budget limit: ${limit:.2f}\n"
    message += f"Usage: {percent:.1f}%\n\n"
    message += "Consider reviewing optimization suggestions at `/optimize/suggestions`"

    await send_slack_notification(message, "error")


async def send_slack_notification(message: str, level: str = "info"):
    """Send notification to Slack"""
    if not SLACK_WEBHOOK_URL:
        print(f"[SLACK] {level.upper()}: {message}")
        return

    emoji_map = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}

    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "text": f"{emoji_map.get(level, '📢')} {message}",
                "username": "Cost Optimizer",
                "icon_emoji": ":moneybag:",
            }
            await client.post(SLACK_WEBHOOK_URL, json=payload)
    except Exception as e:
        print(f"Failed to send Slack notification: {str(e)}")


@app.on_event("startup")
async def startup_event():
    print("💰 Cost Optimizer starting...")
    print(f"📊 Daily budget: ${DAILY_BUDGET_USD}")
    print(f"📊 Monthly budget: ${MONTHLY_BUDGET_USD}")
    await send_slack_notification("💰 Cost Optimizer started", "info")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "6002")))
