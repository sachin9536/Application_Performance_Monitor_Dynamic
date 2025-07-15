# 🚀 Node.js Quick Start for AppVital Log Integration

## Copy-Paste This Code Right Now!

### 1. Copy the Log Shipper

```bash
# Copy this file to your Node.js project
cp services/log_shipper.js ./log_shipper.js
```

### 2. Add This to Your Main File (app.js/server.js/index.js)

```javascript
const AppVitalLogShipper = require("./log_shipper");

// Initialize logger
const logger = new AppVitalLogShipper({
  apiUrl: "http://localhost:8001", // AppVital backend
  serviceName: "your-service-name", // Change this!
  batchSize: 10,
  flushInterval: 5000,
});

// Graceful shutdown
process.on("SIGINT", () => {
  logger.stop();
  process.exit(0);
});
```

### 3. Replace Your Console Logs

```javascript
// Instead of:
console.log("User logged in");
console.error("Database failed");

// Use:
logger.info("User logged in", { userId: "123" });
logger.error("Database failed", { error: "Connection timeout" });
```

### 4. Test It

```javascript
// Add this to test
logger.info("Service started", { version: "1.0.0" });
logger.warn("Test warning", { threshold: 80 });
logger.error("Test error", { error: "Test" });
```

### 5. Check Dashboard

- Open: http://localhost:3000
- Go to Logs page
- Filter by your service name
- See your logs in real-time!

---

## 🎯 That's It! Your logs are now in AppVital!

**Benefits:**

- ✅ Real-time dashboard
- ✅ User isolation
- ✅ AI analytics
- ✅ No file management
- ✅ Structured logging

**Need the full guide?** See `NODEJS_LOG_INTEGRATION_GUIDE.md`
