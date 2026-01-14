"""
BONZO Research Agent
Python-based AI agent for research and data gathering
"""
import redis
import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ResearchAgent")

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")
PORT = int(os.getenv("RESEARCH_AGENT_PORT", "6062"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()

logger.setLevel(getattr(logging, LOG_LEVEL))

# Redis connection
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    logger.info(f"Connected to Redis at {REDIS_URL}")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    redis_client = None


class ResearchAgent:
    """Research Agent with Redis-backed task queue"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.agent_id = "research-agent-001"
        logger.info(f"Initialized {self.agent_id}")
    
    def process_query(self, query: str) -> Dict[str, Any]:
        """
        Process a research query
        TODO: Integrate with actual research APIs
        """
        logger.info(f"Processing query: {query}")
        
        # Store query in Redis
        query_id = f"query:{datetime.utcnow().timestamp()}"
        self.redis.setex(
            query_id,
            3600,  # 1 hour expiry
            json.dumps({
                "query": query,
                "status": "processed",
                "timestamp": datetime.utcnow().isoformat(),
                "agent_id": self.agent_id
            })
        )
        
        return {
            "query_id": query_id,
            "status": "processed",
            "result": f"Research for: {query}",
            "agent": self.agent_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status and statistics"""
        try:
            # Count queries in Redis
            query_keys = self.redis.keys("query:*")
            
            return {
                "agent": self.agent_id,
                "status": "active",
                "redis_connected": self.redis.ping(),
                "total_queries": len(query_keys),
                "uptime": "running",
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            return {
                "agent": self.agent_id,
                "status": "error",
                "error": str(e)
            }


# HTTP Request Handler
class AgentRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler for Research Agent"""
    
    agent = ResearchAgent(redis_client) if redis_client else None
    
    def _send_json_response(self, data: Dict, status: int = 200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
    
    def do_GET(self):
        """Handle GET requests - Status endpoint"""
        if not self.agent:
            self._send_json_response({
                "error": "Agent not initialized - Redis unavailable"
            }, 503)
            return
        
        status = self.agent.get_status()
        self._send_json_response(status)
        logger.info(f"Status check: {status['status']}")
    
    def do_POST(self):
        """Handle POST requests - Research queries"""
        if not self.agent:
            self._send_json_response({
                "error": "Agent not initialized - Redis unavailable"
            }, 503)
            return
        
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json_response({
                    "error": "Empty request body"
                }, 400)
                return
            
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            # Process query
            query = data.get('query', '')
            if not query:
                self._send_json_response({
                    "error": "Missing 'query' field"
                }, 400)
                return
            
            result = self.agent.process_query(query)
            self._send_json_response(result)
            
        except json.JSONDecodeError:
            self._send_json_response({
                "error": "Invalid JSON"
            }, 400)
        except Exception as e:
            logger.error(f"Request processing error: {e}")
            self._send_json_response({
                "error": str(e)
            }, 500)
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    
    def log_message(self, format, *args):
        """Override to use custom logger"""
        logger.debug(f"{self.address_string()} - {format % args}")


def main():
    """Start the Research Agent HTTP server"""
    if not redis_client:
        logger.error("Cannot start agent - Redis connection failed")
        logger.error("Exiting...")
        return
    
    server_address = ("0.0.0.0", PORT)
    httpd = HTTPServer(server_address, AgentRequestHandler)
    
    logger.info(f"🚀 Research Agent starting on port {PORT}")
    logger.info(f"📊 Status: GET http://localhost:{PORT}/")
    logger.info(f"🔍 Query: POST http://localhost:{PORT}/ with JSON body")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down agent...")
        httpd.shutdown()


if __name__ == "__main__":
    main()
