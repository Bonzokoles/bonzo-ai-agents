"""
Scraper Agent - Data scraping i monitoring cen
Port: 8201
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
import httpx
from bs4 import BeautifulSoup
import json
from pathlib import Path

app = FastAPI(title="Scraper Agent")

# Data storage
DATA_DIR = Path("U:/The_yellow_hub/data/scraper")
DATA_DIR.mkdir(parents=True, exist_ok=True)

PRICE_HISTORY_FILE = DATA_DIR / "price_history.json"
MONITORED_URLS_FILE = DATA_DIR / "monitored_urls.json"


# Models
class PriceMonitor(BaseModel):
    url: str
    product_name: str
    selector: Optional[str] = None  # CSS selector dla ceny
    check_interval: int = 3600  # seconds


# Helper functions
def load_json(file_path: Path) -> List[dict]:
    if not file_path.exists():
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(file_path: Path, data: List[dict]):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# Routes
@app.get("/health")
async def health():
    return {"status": "ok", "agent": "scraper", "port": 8201}


@app.post("/execute")
async def execute(request: dict):
    """Main execution endpoint"""
    command = request.get("command")
    args = request.get("args", {})

    if command == "monitor_price":
        return await monitor_price(**args)
    elif command == "scrape_page":
        return await scrape_page(**args)
    elif command == "get_price_history":
        return await get_price_history(**args)
    elif command == "analyze_competitors":
        return await analyze_competitors(**args)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown command: {command}")


async def scrape_page(url: str, extract: Optional[List[str]] = None):
    """Scrape page content"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            data = {
                "url": url,
                "title": soup.title.string if soup.title else None,
                "scraped_at": datetime.utcnow().isoformat(),
            }

            # Extract specific elements if requested
            if extract:
                data["extracted"] = {}
                for selector in extract:
                    elements = soup.select(selector)
                    data["extracted"][selector] = [el.text.strip() for el in elements]

            return {"success": True, "data": data}

    except Exception as e:
        return {"success": False, "error": str(e)}


async def monitor_price(url: str, product_name: str, selector: Optional[str] = None):
    """Monitor product price"""
    # Scrape current price
    scrape_result = await scrape_page(url, extract=[selector] if selector else None)

    if not scrape_result.get("success"):
        return scrape_result

    # Try to extract price
    price = None
    if selector and "extracted" in scrape_result["data"]:
        price_texts = scrape_result["data"]["extracted"].get(selector, [])
        if price_texts:
            # Try to parse price from text
            import re

            price_match = re.search(r"[\d,]+\.?\d*", price_texts[0])
            if price_match:
                price = float(price_match.group().replace(",", ""))

    # Save to history
    price_history = load_json(PRICE_HISTORY_FILE)

    entry = {
        "product_name": product_name,
        "url": url,
        "price": price,
        "scraped_at": datetime.utcnow().isoformat(),
        "raw_data": scrape_result["data"],
    }

    price_history.append(entry)
    save_json(PRICE_HISTORY_FILE, price_history)

    # Check for price change
    previous_entries = [
        e
        for e in price_history[:-1]
        if e["product_name"] == product_name and e["price"] is not None
    ]

    price_change = None
    if previous_entries and price:
        last_price = previous_entries[-1]["price"]
        price_change = {
            "previous": last_price,
            "current": price,
            "diff": round(price - last_price, 2),
            "diff_percent": (
                round((price - last_price) / last_price * 100, 2)
                if last_price > 0
                else 0
            ),
        }

    return {
        "success": True,
        "data": {
            "product": product_name,
            "url": url,
            "current_price": price,
            "price_change": price_change,
            "scraped_at": entry["scraped_at"],
        },
    }


async def get_price_history(product_name: str, days: int = 30):
    """Get price history for product"""
    price_history = load_json(PRICE_HISTORY_FILE)

    # Filter by product
    product_history = [
        e
        for e in price_history
        if e["product_name"] == product_name and e["price"] is not None
    ]

    # Sort by date
    product_history.sort(key=lambda x: x["scraped_at"], reverse=True)

    # Limit to days
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(days=days)
    recent_history = [
        e for e in product_history if datetime.fromisoformat(e["scraped_at"]) >= cutoff
    ]

    # Calculate stats
    prices = [e["price"] for e in recent_history]

    stats = {
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
        "avg_price": round(sum(prices) / len(prices), 2) if prices else None,
        "current_price": recent_history[0]["price"] if recent_history else None,
        "data_points": len(recent_history),
    }

    return {
        "success": True,
        "data": {
            "product": product_name,
            "stats": stats,
            "history": recent_history[:50],  # Last 50 entries
        },
    }


async def analyze_competitors(category: str, competitors: List[str]):
    """Analyze competitor prices"""
    results = []

    for url in competitors:
        # Extract domain for product name
        from urllib.parse import urlparse

        domain = urlparse(url).netloc

        result = await monitor_price(url, f"{category}_{domain}")
        results.append(result)

    # Aggregate
    prices = [
        r["data"]["current_price"]
        for r in results
        if r.get("success") and r["data"].get("current_price")
    ]

    analysis = {
        "category": category,
        "competitors_checked": len(competitors),
        "prices_found": len(prices),
        "price_range": {
            "min": min(prices) if prices else None,
            "max": max(prices) if prices else None,
            "avg": round(sum(prices) / len(prices), 2) if prices else None,
        },
        "results": results,
    }

    return {"success": True, "data": analysis}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8201)
