const axios = require("axios");

class AppVitalLogShipper {
  constructor(options = {}) {
    this.apiUrl = options.apiUrl || "http://localhost:8000";
    this.serviceName = options.serviceName || "unknown_service";
    this.batchSize = options.batchSize || 10;
    this.flushInterval = options.flushInterval || 5000;
    this.logBuffer = [];
    this.flushTimer = null;
    this.isRunning = true;
    this.startFlushTimer();
  }

  log(level, message, metadata = {}) {
    const logEntry = {
      timestamp: new Date().toISOString(),
      level: level.toUpperCase(),
      service: this.serviceName,
      message: message,
      ...metadata,
    };

    this.logBuffer.push(logEntry);

    if (this.logBuffer.length >= this.batchSize) {
      this.flush();
    }
  }

  info(message, metadata = {}) {
    this.log("info", message, metadata);
  }

  warn(message, metadata = {}) {
    this.log("warn", message, metadata);
  }

  error(message, metadata = {}) {
    this.log("error", message, metadata);
  }

  debug(message, metadata = {}) {
    this.log("debug", message, metadata);
  }

  // New method to log service identification
  logServiceRequest(
    requestingService,
    targetService,
    requestId,
    additionalData = {}
  ) {
    this.info("Service request received", {
      requesting_service: requestingService,
      target_service: targetService,
      request_id: requestId,
      ...additionalData,
    });
  }

  async flush() {
    if (this.logBuffer.length === 0) return;

    const logsToSend = [...this.logBuffer];
    this.logBuffer = [];

    try {
      await axios.post(`${this.apiUrl}/api/ingest_log`, {
        logs: logsToSend,
      });
    } catch (error) {
      console.error("Failed to send logs to AppVital:", error.message);
      // Optionally, you could add the logs back to the buffer here
    }
  }

  startFlushTimer() {
    this.flushTimer = setInterval(() => {
      this.flush();
    }, this.flushInterval);
  }

  stop() {
    this.isRunning = false;
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
    }
    this.flush(); // Final flush
  }
}

module.exports = AppVitalLogShipper;

// Example usage:
/*
const AppVitalLogShipper = require('./log_shipper');

const logger = new AppVitalLogShipper({
    apiUrl: 'http://localhost:8000',
    serviceName: 'my_nodejs_service',
    batchSize: 5,
    flushInterval: 3000
});

// Use the logger
logger.info('User logged in', { userId: '123', ip: '192.168.1.1' });
logger.error('Database connection failed', { error: 'Connection timeout' });
logger.warn('High memory usage', { memoryUsage: '85%' });

// Don't forget to stop when shutting down
process.on('SIGINT', () => {
    logger.stop();
    process.exit(0);
});
*/
