# BONZO Research Agent

Python-based AI agent for research tasks and data gathering.

## Features

- 🔍 Research query processing
- 🔴 Redis-backed task queue
- 📊 Status monitoring
- 🌐 HTTP API interface
- ⚡ Async processing support

## Quick Start

### Local Development

```bash
cd agents/python/research-agent

# Install dependencies
pip install -r requirements.txt

# Set environment
export REDIS_URL=redis://localhost:6379/1
export RESEARCH_AGENT_PORT=6062

# Run agent
python main.py
```

### Docker

```bash
# Build
docker build -t bonzo-research-agent .

# Run
docker run -p 6062:6062 -e REDIS_URL=redis://redis:6379/1 bonzo-research-agent
```

## API Endpoints

### GET /
Get agent status and statistics

```bash
curl http://localhost:6062/
```

Response:
```json
{
  "agent": "research-agent-001",
  "status": "active",
  "redis_connected": true,
  "total_queries": 42,
  "timestamp": "2026-01-14T21:30:00Z"
}
```

### POST /
Submit research query

```bash
curl -X POST http://localhost:6062/ \
  -H "Content-Type: application/json" \
  -d '{"query": "AI trends 2026"}'
```

Response:
```json
{
  "query_id": "query:1705267800.123",
  "status": "processed",
  "result": "Research for: AI trends 2026",
  "agent": "research-agent-001",
  "timestamp": "2026-01-14T21:30:00Z"
}
```

## Environment Variables

```env
REDIS_URL=redis://redis:6379/1
RESEARCH_AGENT_PORT=6062
LOG_LEVEL=info
```

## Architecture

```
research-agent/
├── main.py              # Agent server & logic
├── requirements.txt     # Python dependencies
├── Dockerfile          # Container configuration
└── README.md           # This file
```

## Development Roadmap

- [x] Basic HTTP server
- [x] Redis integration
- [x] Query processing
- [ ] Integrate with research APIs (Perplexity, Tavily)
- [ ] Add result caching
- [ ] Implement rate limiting
- [ ] Add comprehensive logging
- [ ] WebSocket support for real-time updates

## Testing

```bash
# Start agent
python main.py

# In another terminal:

# Check status
curl http://localhost:6062/

# Submit query
curl -X POST http://localhost:6062/ \
  -H "Content-Type: application/json" \
  -d '{"query": "test research"}'
```

## Integration with Main System

The Research Agent communicates via Redis with the main API Gateway:

1. API Gateway receives research request
2. Request queued in Redis
3. Research Agent picks up from queue
4. Agent processes and stores results
5. API Gateway retrieves results
