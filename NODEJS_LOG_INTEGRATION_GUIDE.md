# Node.js Log Integration Guide for AppVital

## 🚀 Quick Start: Add Log Shipping to Your Node.js Service

Your Node.js services can now send logs directly to AppVital's centralized monitoring system! This replaces the old file-based logging with real-time, user-isolated log ingestion.

---

## 📦 Step 1: Install the Log Shipper

### Option A: Copy the Log Shipper File

Copy `services/log_shipper.js` to your Node.js project:

```bash
# Copy the log shipper to your project
cp services/log_shipper.js ./log_shipper.js
```

### Option B: Install as NPM Package (if available)

```bash
npm install appvital-log-shipper
```

---

## 🔧 Step 2: Initialize the Log Shipper

Add this to your main application file (e.g., `app.js`, `server.js`, or `index.js`):

```javascript
const AppVitalLogShipper = require("./log_shipper");

// Initialize the log shipper
const logger = new AppVitalLogShipper({
  apiUrl: "http://localhost:8001", // AppVital backend URL (demo mode)
  serviceName: "your-service-name", // Your service name
  batchSize: 10, // Send logs in batches of 10
  flushInterval: 5000, // Flush every 5 seconds
});

// Handle graceful shutdown
process.on("SIGINT", () => {
  console.log("Shutting down gracefully...");
  logger.stop();
  process.exit(0);
});

process.on("SIGTERM", () => {
  console.log("Shutting down gracefully...");
  logger.stop();
  process.exit(0);
});
```

---

## 📝 Step 3: Replace Console Logs with AppVital Logger

### Before (Console Logging):

```javascript
console.log("User logged in");
console.error("Database connection failed");
console.warn("High memory usage detected");
```

### After (AppVital Logging):

```javascript
// Basic logging
logger.info("User logged in");
logger.error("Database connection failed");
logger.warn("High memory usage detected");
logger.debug("Processing request data");

// Structured logging with metadata
logger.info("User authentication successful", {
  userId: "user_123",
  ip: "192.168.1.100",
  method: "jwt",
  duration: 150,
});

logger.error("Payment processing failed", {
  error: "Insufficient funds",
  amount: 100.5,
  userId: "user_456",
  gateway: "stripe",
});

logger.warn("Database connection pool at 80% capacity", {
  poolSize: 80,
  maxPool: 100,
  database: "postgres",
});
```

---

## 🔄 Step 4: Integration Examples

### Express.js Middleware Integration:

```javascript
const express = require("express");
const AppVitalLogShipper = require("./log_shipper");

const app = express();
const logger = new AppVitalLogShipper({
  apiUrl: "http://localhost:8001",
  serviceName: "express-api",
});

// Request logging middleware
app.use((req, res, next) => {
  const start = Date.now();

  // Log request start
  logger.info("Request started", {
    method: req.method,
    path: req.path,
    ip: req.ip,
    userAgent: req.get("User-Agent"),
  });

  // Override res.end to log response
  const originalEnd = res.end;
  res.end = function (chunk, encoding) {
    const duration = Date.now() - start;

    logger.info("Request completed", {
      method: req.method,
      path: req.path,
      statusCode: res.statusCode,
      duration: duration,
      contentLength: res.get("Content-Length"),
    });

    originalEnd.call(this, chunk, encoding);
  };

  next();
});

// Error handling middleware
app.use((err, req, res, next) => {
  logger.error("Request error", {
    method: req.method,
    path: req.path,
    error: err.message,
    stack: err.stack,
  });

  res.status(500).json({ error: "Internal server error" });
});
```

### Database Operations:

```javascript
const logger = new AppVitalLogShipper({
  apiUrl: "http://localhost:8001",
  serviceName: "database-service",
});

async function createUser(userData) {
  try {
    logger.info("Creating new user", { email: userData.email });

    const user = await db.users.create(userData);

    logger.info("User created successfully", {
      userId: user.id,
      email: user.email,
    });

    return user;
  } catch (error) {
    logger.error("Failed to create user", {
      error: error.message,
      email: userData.email,
      stack: error.stack,
    });
    throw error;
  }
}
```

### API Endpoints:

```javascript
app.post("/api/orders", async (req, res) => {
  try {
    logger.info("Processing order request", {
      userId: req.body.userId,
      items: req.body.items.length,
      total: req.body.total,
    });

    const order = await processOrder(req.body);

    logger.info("Order processed successfully", {
      orderId: order.id,
      userId: order.userId,
      status: order.status,
    });

    res.json(order);
  } catch (error) {
    logger.error("Order processing failed", {
      error: error.message,
      userId: req.body.userId,
      orderData: req.body,
    });

    res.status(500).json({ error: "Order processing failed" });
  }
});
```

---

## 🎯 Step 5: Configuration Options

### Log Shipper Configuration:

```javascript
const logger = new AppVitalLogShipper({
  apiUrl: "http://localhost:8001", // AppVital backend URL
  serviceName: "my-service", // Service name (appears in dashboard)
  batchSize: 10, // Number of logs to batch before sending
  flushInterval: 5000, // Flush interval in milliseconds
  retryAttempts: 3, // Number of retry attempts on failure
  retryDelay: 1000, // Delay between retries in milliseconds
});
```

### Environment Variables:

```javascript
const logger = new AppVitalLogShipper({
  apiUrl: process.env.APPVITAL_API_URL || "http://localhost:8001",
  serviceName: process.env.SERVICE_NAME || "my-service",
  batchSize: parseInt(process.env.LOG_BATCH_SIZE) || 10,
  flushInterval: parseInt(process.env.LOG_FLUSH_INTERVAL) || 5000,
});
```

---

## 🔍 Step 6: Testing Your Integration

### Test Script:

```javascript
// test_logging.js
const AppVitalLogShipper = require("./log_shipper");

const logger = new AppVitalLogShipper({
  apiUrl: "http://localhost:8001",
  serviceName: "test-service",
});

// Send test logs
logger.info("Test service started", { version: "1.0.0" });
logger.warn("Test warning message", { threshold: 80 });
logger.error("Test error message", { error: "Test error" });

// Wait for logs to be sent
setTimeout(() => {
  logger.stop();
  console.log("Test completed! Check the AppVital dashboard.");
}, 3000);
```

Run the test:

```bash
node test_logging.js
```

---

## 📊 Step 7: Verify in AppVital Dashboard

1. **Open the Dashboard**: http://localhost:3000
2. **Check Logs Page**: Look for logs from your service
3. **Filter by Service**: Use the service name filter
4. **Check Analytics**: See AI-powered insights
5. **Monitor Metrics**: View real-time performance data

---

## 🚨 Troubleshooting

### Common Issues:

**1. Connection Refused**

```javascript
// Check if AppVital backend is running
// Default URL: http://localhost:8001 (demo mode)
// Production URL: http://localhost:8000
```

**2. Logs Not Appearing**

- Check service name matches in dashboard
- Verify API URL is correct
- Check network connectivity
- Look for error messages in console

**3. High Memory Usage**

```javascript
// Reduce batch size and increase flush interval
const logger = new AppVitalLogShipper({
  batchSize: 5, // Smaller batches
  flushInterval: 2000, // More frequent flushing
});
```

**4. Performance Issues**

```javascript
// Increase batch size and flush interval
const logger = new AppVitalLogShipper({
  batchSize: 50, // Larger batches
  flushInterval: 10000, // Less frequent flushing
});
```

---

## 🔄 Migration from File Logging

### If you're currently using file logging:

**Before:**

```javascript
const fs = require("fs");
const path = require("path");

function logToFile(level, message, data) {
  const logEntry = {
    timestamp: new Date().toISOString(),
    level: level,
    message: message,
    data: data,
  };

  fs.appendFileSync(
    path.join(__dirname, "logs", "app.log"),
    JSON.stringify(logEntry) + "\n"
  );
}

logToFile("INFO", "User logged in", { userId: "123" });
```

**After:**

```javascript
const AppVitalLogShipper = require("./log_shipper");

const logger = new AppVitalLogShipper({
  apiUrl: "http://localhost:8001",
  serviceName: "my-service",
});

logger.info("User logged in", { userId: "123" });
```

---

## 📈 Benefits of the New System

✅ **Real-time**: Logs appear immediately in dashboard  
✅ **User Isolation**: Each user sees only their logs  
✅ **Structured**: Rich metadata and context  
✅ **Scalable**: Handles millions of logs  
✅ **Searchable**: Advanced filtering and search  
✅ **Analytics**: AI-powered insights  
✅ **No File Management**: No log rotation or cleanup needed

---

## 🎉 You're All Set!

Your Node.js service is now integrated with AppVital's centralized log ingestion system. Your logs will appear in real-time in the dashboard with full user isolation and AI-powered analytics.

**Next Steps:**

1. Test the integration
2. Monitor the dashboard
3. Configure alerts if needed
4. Share with your team!

---

**Need Help?**

- Check the AppVital dashboard for log status
- Review the troubleshooting section above
- Contact the AppVital team for support
