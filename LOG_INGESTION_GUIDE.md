# AppVital Log Ingestion Guide

This guide explains how to integrate your services with AppVital's centralized log ingestion system.

## Overview

AppVital now supports **centralized log ingestion** where any service (regardless of language) can send logs to a central endpoint. Logs are stored in MongoDB with proper user isolation and can be queried through the dashboard.

## How It Works

1. **Your service** sends logs to `/api/ingest_log` endpoint
2. **AppVital backend** stores logs in MongoDB with user isolation
3. **Dashboard** queries logs from MongoDB and displays them
4. **All logs** are automatically filtered by user ownership

## API Endpoints

### POST `/api/ingest_log`

Send multiple logs in a batch.

**Request Body:**

```json
{
  "logs": [
    {
      "service": "my_service",
      "level": "INFO",
      "message": "User logged in successfully",
      "timestamp": "2024-01-01T12:00:00Z",
      "metadata": {
        "user_id": "123",
        "ip": "192.168.1.1"
      }
    }
  ]
}
```

### POST `/api/ingest_single_log`

Send a single log entry.

**Request Body:**

```json
{
  "service": "my_service",
  "level": "ERROR",
  "message": "Database connection failed",
  "timestamp": "2024-01-01T12:00:00Z",
  "metadata": {
    "error": "Connection timeout"
  }
}
```

## Integration Examples

### Node.js Service

1. **Install the log shipper:**

```bash
npm install axios
```

2. **Use the provided log shipper:**

```javascript
const AppVitalLogShipper = require("./services/log_shipper");

const logger = new AppVitalLogShipper({
  apiUrl: "http://localhost:8000",
  serviceName: "my_nodejs_service",
  batchSize: 5,
  flushInterval: 3000,
});

// Use the logger
logger.info("User logged in", { userId: "123", ip: "192.168.1.1" });
logger.error("Database connection failed", { error: "Connection timeout" });
logger.warn("High memory usage", { memoryUsage: "85%" });

// Clean shutdown
process.on("SIGINT", () => {
  logger.stop();
  process.exit(0);
});
```

### Python Service

1. **Install dependencies:**

```bash
pip install requests
```

2. **Use the provided log shipper:**

```python
from services.log_shipper import AppVitalLogShipper

logger = AppVitalLogShipper({
    'api_url': 'http://localhost:8000',
    'service_name': 'my_python_service',
    'batch_size': 5,
    'flush_interval': 3
})

# Use the logger
logger.info('User logged in', {'user_id': '123', 'ip': '192.168.1.1'})
logger.error('Database connection failed', {'error': 'Connection timeout'})
logger.warn('High memory usage', {'memory_usage': '85%'})

# Clean shutdown
import signal
def signal_handler(sig, frame):
    logger.stop()
    exit(0)

signal.signal(signal.SIGINT, signal_handler)
```

### Direct HTTP Integration

For any language, you can make direct HTTP calls:

```bash
curl -X POST http://localhost:8000/api/ingest_single_log \
  -H "Content-Type: application/json" \
  -d '{
    "service": "my_service",
    "level": "INFO",
    "message": "Service started",
    "metadata": {"version": "1.0.0"}
  }'
```

## Log Format

Each log entry should have:

- **service** (required): Name of your service
- **level** (optional): Log level (INFO, WARN, ERROR, DEBUG)
- **message** (required): Log message
- **timestamp** (optional): ISO 8601 timestamp (auto-generated if not provided)
- **metadata** (optional): Additional structured data

## User Isolation

- Logs are automatically associated with the user who owns the service
- Users can only see logs from their own services
- No manual user management required

## Benefits

1. **Scalable**: Works for any number of services
2. **Language-agnostic**: Works with any programming language
3. **Centralized**: All logs in one place
4. **Secure**: User isolation built-in
5. **Real-time**: Logs appear in dashboard immediately
6. **Structured**: Support for metadata and structured logging

## Migration from File-based Logging

If you're currently using file-based logging:

1. **Keep existing log files** for debugging
2. **Add log ingestion** to your services
3. **Gradually migrate** to centralized logging
4. **Remove file-based logging** once migration is complete

## Troubleshooting

### Logs not appearing in dashboard

- Check that your service is registered in AppVital
- Verify the API endpoint is reachable
- Check network connectivity between your service and AppVital

### High latency

- Increase batch size to reduce API calls
- Increase flush interval
- Consider using async logging

### Memory usage

- Monitor log buffer size
- Adjust batch size and flush interval
- Implement log rotation if needed

## Best Practices

1. **Use structured logging** with metadata
2. **Batch logs** to reduce API calls
3. **Handle failures gracefully** (retry, fallback to local files)
4. **Use appropriate log levels**
5. **Include relevant context** in metadata
6. **Monitor log ingestion performance**

## Example: Complete Node.js Integration

```javascript
const express = require("express");
const AppVitalLogShipper = require("./services/log_shipper");

const app = express();
const logger = new AppVitalLogShipper({
  apiUrl: "http://localhost:8000",
  serviceName: "my_api_service",
  batchSize: 10,
  flushInterval: 5000,
});

app.use((req, res, next) => {
  const start = Date.now();

  res.on("finish", () => {
    const duration = Date.now() - start;
    logger.info("HTTP Request", {
      method: req.method,
      path: req.path,
      status: res.statusCode,
      duration: duration,
      ip: req.ip,
    });
  });

  next();
});

app.get("/health", (req, res) => {
  logger.info("Health check requested");
  res.json({ status: "ok" });
});

app.post("/users", (req, res) => {
  try {
    // Create user logic
    logger.info("User created", { userId: "123", email: req.body.email });
    res.json({ success: true });
  } catch (error) {
    logger.error("Failed to create user", { error: error.message });
    res.status(500).json({ error: "Internal server error" });
  }
});

// Clean shutdown
process.on("SIGINT", () => {
  logger.stop();
  process.exit(0);
});

app.listen(3000, () => {
  logger.info("Server started", { port: 3000 });
});
```

This integration provides:

- Automatic request logging
- Structured error logging
- Performance metrics
- Clean shutdown handling
- Real-time log ingestion to AppVital
