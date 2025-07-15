import streamlit as st
import pandas as pd
from prophet import Prophet
from pathlib import Path
import json
import plotly.express as px
from datetime import datetime
import io
import smtplib
from email.message import EmailMessage

# --- Page Setup ---
st.set_page_config(page_title="Service Load Forecast", layout="wide")
st.title("📊 Service Load Forecast Dashboard")

# --- Manual Refresh Button ---
if st.button("🔄 Refresh Forecast"):
    st.rerun()

# --- Read Log File ---
log_path = Path("/forecast/exportedMetrics.log")
if not log_path.exists():
    st.error("❌ Log file not found.")
    st.stop()

# --- Parse Log Data ---
records = []
with open(log_path, "r") as file:
    for line in file:
        try:
            data = json.loads(line)
            timestamp = pd.to_datetime(data["timestamp"])
            service = data["service"]
            for key, value in data.items():
                if key not in ["timestamp", "service"]:
                    records.append({
                        "timestamp": timestamp,
                        "service": service,
                        "metric_type": key,
                        "value": pd.to_numeric(value, errors="coerce")
                    })
        except Exception:
            continue

df = pd.DataFrame(records)
df.dropna(subset=["value"], inplace=True)

if df.empty:
    st.warning("No valid metric data available.")
    st.stop()

# --- Dropdowns for Service and Metrics ---
services = sorted(df["service"].unique())
selected_service = st.selectbox("Select a Service", services)

metrics = sorted(df[df["service"] == selected_service]["metric_type"].unique())
selected_metrics = st.multiselect("Select Metrics", metrics)

if not selected_metrics:
    st.warning("Please select at least one metric.")
    st.stop()

latest_forecast = None

for selected_metric in selected_metrics:
    filtered_df = df[(df["service"] == selected_service) & (df["metric_type"] == selected_metric)].sort_values("timestamp")

    # Short-term Forecast
    st.subheader(f"Short-term Forecast for {selected_metric}")
    agg_df_short = filtered_df.set_index("timestamp").resample("5min")["value"].max().dropna().reset_index()

    if len(agg_df_short) >= 2:
        agg_df_short.rename(columns={"timestamp": "ds", "value": "y"}, inplace=True)
        model_short = Prophet()
        model_short.fit(agg_df_short)
        future_short = model_short.make_future_dataframe(periods=96, freq="5min")
        forecast_short = model_short.predict(future_short)
        forecast_short["Forecasted"] = forecast_short["yhat"].clip(lower=0)

        merged_short = pd.merge(forecast_short[["ds", "Forecasted"]], agg_df_short.rename(columns={"y": "Real"}), on="ds", how="outer").sort_values("ds")
        merged_short["Real"] = merged_short["Real"].ffill()

        fig_short = px.line(merged_short, x="ds", y=["Real", "Forecasted"], title=f"Short-term Forecast for {selected_metric}", labels={"ds": "Time"})
        fig_short.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_short, use_container_width=True)
    else:
        st.warning(f"Not enough data for short-term forecast of {selected_metric}")

    # Monthly Forecast
    st.subheader(f"Monthly Forecast for {selected_metric}")
    agg_df_monthly = filtered_df.set_index("timestamp").resample("D")["value"].max().dropna().reset_index()

    if len(agg_df_monthly) >= 2:
        agg_df_monthly.rename(columns={"timestamp": "ds", "value": "y"}, inplace=True)
        model_monthly = Prophet()
        model_monthly.fit(agg_df_monthly)
        future_monthly = model_monthly.make_future_dataframe(periods=30)
        forecast_monthly = model_monthly.predict(future_monthly)
        forecast_monthly["Forecasted"] = forecast_monthly["yhat"].clip(lower=0)

        merged_monthly = pd.merge(forecast_monthly[["ds", "Forecasted"]], agg_df_monthly.rename(columns={"y": "Real"}), on="ds", how="outer").sort_values("ds")
        merged_monthly["Real"] = merged_monthly["Real"].ffill()

        fig_monthly = px.line(merged_monthly, x="ds", y=["Real", "Forecasted"], title=f"Monthly Forecast for {selected_metric}", labels={"ds": "Date"})
        fig_monthly.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_monthly, use_container_width=True)

        latest_forecast = forecast_monthly  # capture for export/email
    else:
        st.warning(f"Not enough data for monthly forecast of {selected_metric}")

# Export & Email
st.subheader('📤 Export Forecast Data')
if latest_forecast is not None:
    buffer = io.BytesIO()
    latest_forecast[['ds','yhat','yhat_lower','yhat_upper']].to_excel(buffer, index=False, engine='openpyxl')
    st.download_button('📥 Download Forecast as Excel', data=buffer.getvalue(), file_name='forecast.xlsx')

    st.subheader('📧 Email Forecast Summary')
    recipient = st.text_input('Enter admin email')
    if st.button('Send Email') and recipient:
        try:
            msg = EmailMessage()
            msg['Subject'] = f"Load Forecast: {selected_service}"
            msg['From'] = 'your_email@gmail.com'
            msg['To'] = recipient
            msg.set_content('Attached is the forecast.')
            buffer.seek(0)
            msg.add_attachment(buffer.read(), maintype='application', subtype='octet-stream', filename='forecast.xlsx')
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login('your_email@gmail.com', 'your_app_password')
                smtp.send_message(msg)
            st.success('📩 Email sent successfully!')
        except Exception as e:
            st.error(f"Failed to send email: {e}")

if st.button('🔁 Refresh Forecast'):
    st.experimental_rerun()

st.markdown('---')
st.markdown(f"Generated on: {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}")