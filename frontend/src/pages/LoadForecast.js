import React, { useState, useEffect, useRef } from "react";

const LoadForecast = () => {
  const [isLoaded, setIsLoaded] = useState(false);
  const [isError, setIsError] = useState(false);
  const iframeRef = useRef(null);

  // Optional: handle iframe load timeout
  useEffect(() => {
    const timeout = setTimeout(() => {
      if (!isLoaded) setIsError(true);
    }, 10000); // 10s timeout

    return () => clearTimeout(timeout);
  }, [isLoaded]);

  return (
    <div style={{ width: "100%", height: "100vh", position: "relative" }}>
      {!isLoaded && !isError && (
        <div style={{ textAlign: "center", paddingTop: "2rem" }}>
          <span>🔄 Loading Forecast Dashboard...</span>
        </div>
      )}

      {isError && (
        <div style={{ textAlign: "center", color: "red", paddingTop: "2rem" }}>
          ❌ Unable to load Streamlit dashboard at <code>localhost:8501</code>.<br />
          Make sure the `forecast_ui` service is running.
        </div>
      )}

      {!isError && (
        <iframe
          ref={iframeRef}
          title="Service Load Forecast"
          src="http://localhost:8501"
          onLoad={() => setIsLoaded(true)}
          style={{
            width: "100%",
            height: "100vh",
            border: "none",
            display: isLoaded ? "block" : "none"
          }}
        />
      )}
    </div>
  );
};

export default LoadForecast;