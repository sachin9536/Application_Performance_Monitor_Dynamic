import { useEffect } from "react";

const LoadForecast = () => {
  useEffect(() => {
    window.open("http://localhost:8501", "_blank");
  }, []);
  return null;
};

export default LoadForecast;
