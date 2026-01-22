"""
Financial Agent - Zarządzanie finansami osobistymi
Port: 8200
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import json
import os
from pathlib import Path

app = FastAPI(title="Financial Agent")

# Data storage
DATA_DIR = Path("U:/The_yellow_hub/data/financial")
DATA_DIR.mkdir(parents=True, exist_ok=True)

EXPENSES_FILE = DATA_DIR / "expenses.json"
REVENUE_FILE = DATA_DIR / "revenue.json"
BUDGET_FILE = DATA_DIR / "budget.json"


# Models
class Expense(BaseModel):
    id: Optional[str] = None
    date: str
    amount: float
    category: str
    description: str
    source: str = "manual"  # manual, stripe, cloudflare, openrouter


class Revenue(BaseModel):
    id: Optional[str] = None
    date: str
    amount: float
    source: str
    description: str
    client: Optional[str] = None


class Budget(BaseModel):
    category: str
    monthly_limit: float
    alert_threshold: float = 0.8  # Alert at 80%


# Helper functions
def load_json(file_path: Path) -> List[dict]:
    if not file_path.exists():
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(file_path: Path, data: List[dict]):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def generate_id() -> str:
    return datetime.utcnow().strftime("%Y%m%d%H%M%S%f")


# Routes
@app.get("/health")
async def health():
    return {"status": "ok", "agent": "financial", "port": 8200}


@app.post("/execute")
async def execute(request: dict):
    """Main execution endpoint"""
    command = request.get("command")
    args = request.get("args", {})

    if command == "track_expense":
        return await track_expense(**args)
    elif command == "track_revenue":
        return await track_revenue(**args)
    elif command == "get_summary":
        return await get_summary(**args)
    elif command == "get_budget_status":
        return await get_budget_status(**args)
    elif command == "set_budget":
        return await set_budget(**args)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown command: {command}")


async def track_expense(
    amount: float,
    category: str,
    description: str,
    date: Optional[str] = None,
    source: str = "manual",
):
    """Track expense"""
    expenses = load_json(EXPENSES_FILE)

    expense = {
        "id": generate_id(),
        "date": date or datetime.utcnow().isoformat(),
        "amount": amount,
        "category": category,
        "description": description,
        "source": source,
    }

    expenses.append(expense)
    save_json(EXPENSES_FILE, expenses)

    # Check budget
    budget_status = await check_budget_alert(category, amount)

    return {
        "success": True,
        "data": {
            "expense": expense,
            "budget_alert": budget_status.get("alert", False),
            "budget_remaining": budget_status.get("remaining", 0),
        },
    }


async def track_revenue(
    amount: float,
    source: str,
    description: str,
    date: Optional[str] = None,
    client: Optional[str] = None,
):
    """Track revenue"""
    revenues = load_json(REVENUE_FILE)

    revenue = {
        "id": generate_id(),
        "date": date or datetime.utcnow().isoformat(),
        "amount": amount,
        "source": source,
        "description": description,
        "client": client,
    }

    revenues.append(revenue)
    save_json(REVENUE_FILE, revenues)

    return {"success": True, "data": revenue}


async def get_summary(period: str = "month"):
    """Get financial summary"""
    expenses = load_json(EXPENSES_FILE)
    revenues = load_json(REVENUE_FILE)

    # Calculate date range
    now = datetime.utcnow()
    if period == "month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start_date = now - timedelta(days=7)
    elif period == "year":
        start_date = now.replace(
            month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
    else:
        start_date = now - timedelta(days=30)

    # Filter by date
    period_expenses = [
        e for e in expenses if datetime.fromisoformat(e["date"]) >= start_date
    ]
    period_revenues = [
        r for r in revenues if datetime.fromisoformat(r["date"]) >= start_date
    ]

    # Calculate totals
    total_expenses = sum(e["amount"] for e in period_expenses)
    total_revenue = sum(r["amount"] for r in period_revenues)

    # Group expenses by category
    expenses_by_category = {}
    for expense in period_expenses:
        cat = expense["category"]
        expenses_by_category[cat] = expenses_by_category.get(cat, 0) + expense["amount"]

    # Group revenue by source
    revenue_by_source = {}
    for revenue in period_revenues:
        src = revenue["source"]
        revenue_by_source[src] = revenue_by_source.get(src, 0) + revenue["amount"]

    return {
        "success": True,
        "data": {
            "period": period,
            "start_date": start_date.isoformat(),
            "end_date": now.isoformat(),
            "summary": {
                "total_revenue": round(total_revenue, 2),
                "total_expenses": round(total_expenses, 2),
                "net_profit": round(total_revenue - total_expenses, 2),
                "profit_margin": (
                    round((total_revenue - total_expenses) / total_revenue * 100, 2)
                    if total_revenue > 0
                    else 0
                ),
            },
            "expenses_by_category": {
                k: round(v, 2)
                for k, v in sorted(expenses_by_category.items(), key=lambda x: -x[1])
            },
            "revenue_by_source": {
                k: round(v, 2)
                for k, v in sorted(revenue_by_source.items(), key=lambda x: -x[1])
            },
            "transaction_count": {
                "expenses": len(period_expenses),
                "revenues": len(period_revenues),
            },
        },
    }


async def set_budget(category: str, monthly_limit: float, alert_threshold: float = 0.8):
    """Set budget for category"""
    budgets = load_json(BUDGET_FILE)

    # Update or add budget
    updated = False
    for budget in budgets:
        if budget["category"] == category:
            budget["monthly_limit"] = monthly_limit
            budget["alert_threshold"] = alert_threshold
            updated = True
            break

    if not updated:
        budgets.append(
            {
                "category": category,
                "monthly_limit": monthly_limit,
                "alert_threshold": alert_threshold,
            }
        )

    save_json(BUDGET_FILE, budgets)

    return {
        "success": True,
        "data": {
            "category": category,
            "monthly_limit": monthly_limit,
            "alert_threshold": alert_threshold,
        },
    }


async def get_budget_status(category: Optional[str] = None):
    """Get budget status"""
    budgets = load_json(BUDGET_FILE)
    expenses = load_json(EXPENSES_FILE)

    # Current month expenses
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    month_expenses = [
        e for e in expenses if datetime.fromisoformat(e["date"]) >= month_start
    ]

    # Calculate spent by category
    spent_by_category = {}
    for expense in month_expenses:
        cat = expense["category"]
        spent_by_category[cat] = spent_by_category.get(cat, 0) + expense["amount"]

    # Check each budget
    status = []
    for budget in budgets:
        if category and budget["category"] != category:
            continue

        cat = budget["category"]
        limit = budget["monthly_limit"]
        threshold = budget["alert_threshold"]
        spent = spent_by_category.get(cat, 0)
        remaining = limit - spent
        percentage = (spent / limit * 100) if limit > 0 else 0

        status.append(
            {
                "category": cat,
                "limit": limit,
                "spent": round(spent, 2),
                "remaining": round(remaining, 2),
                "percentage": round(percentage, 2),
                "alert": percentage >= (threshold * 100),
                "over_budget": spent > limit,
            }
        )

    return {
        "success": True,
        "data": status if not category else status[0] if status else None,
    }


async def check_budget_alert(category: str, new_expense: float):
    """Check if expense triggers budget alert"""
    budget_status = await get_budget_status(category)

    if not budget_status.get("data"):
        return {"alert": False}

    status = budget_status["data"]
    new_spent = status["spent"] + new_expense
    new_percentage = (new_spent / status["limit"] * 100) if status["limit"] > 0 else 0

    return {
        "alert": new_percentage >= 80,
        "remaining": status["limit"] - new_spent,
        "percentage": round(new_percentage, 2),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8200)
