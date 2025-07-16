import os
import streamlit as st
import pandas as pd
from prophet import Prophet
from datetime import datetime
import plotly.express as px
from pymongo import MongoClient
import io
import smtplib
from email.message import EmailMessage

def get_mongo_config():
    return {
        'host': os.getenv("MONGO_HOST", "localhost"),
        'port': int(os.getenv("MONGO_PORT", "27017")),
        'user': os.getenv("MONGO_USER", "admin"),
        'password': os.getenv("MONGO_PASS", "secret"),
        'auth_db': os.getenv("MONGO_AUTH_DB", "admin"),
        'db_name': os.getenv("DB_NAME", "appvital"),
        'collection': os.getenv("COLLECTION_NAME", "metrics_history"),
    }

def get_mongo_collection():
    cfg = get_mongo_config()
    mongo_uri = f"mongodb://{cfg['user']}:{cfg['password']}@{cfg['host']}:{cfg['port']}/?authSource={cfg['auth_db']}"
    client = MongoClient(mongo_uri)
    return client[cfg['db_name']][cfg['collection']]

def parse_mongo_data(data_cursor):
    records = []
    for doc in data_cursor:
        try:
            timestamp = pd.to_datetime(doc["timestamp"])
            service = doc["service"]
            for key, value in doc.items():
                if key not in ["_id", "timestamp", "service"]:
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
    return df

def run_prophet_forecast(df, period, freq):
    df = df.rename(columns={"timestamp": "ds", "value": "y"})
    model = Prophet()
    model.fit(df)
    future = model.make_future_dataframe(periods=period, freq=freq)
    forecast = model.predict(future)
    forecast["Forecasted"] = forecast["yhat"].clip(lower=0)
    forecast["yhat"] = forecast["yhat"].clip(lower=0)
    forecast["yhat_lower"] = forecast["yhat_lower"].clip(lower=0)
    forecast["yhat_upper"] = forecast["yhat_upper"].clip(lower=0)
    return forecast

def plot_forecast(real_df, forecast_df, title, x_label):
    real_df = real_df.rename(columns={"timestamp": "ds", "value": "y"}).copy()
    merged = pd.merge(
        forecast_df[["ds", "Forecasted"]],
        real_df.rename(columns={"y": "Real"}),
        on="ds", how="outer"
    ).sort_values("ds")
    merged["Real"] = merged["Real"].ffill()
    fig = px.line(
        merged, x="ds", y=["Real", "Forecasted"],
        title=title,
        labels={"ds": x_label}
    )
    fig.update_layout(
        xaxis_tickangle=-45,
        plot_bgcolor="#000000",
        paper_bgcolor="#000000",
        font=dict(color="#FFFFFF"),
        xaxis=dict(gridcolor="#444"),
        yaxis=dict(gridcolor="#444"),
        legend_title="Metric"
    )
    return fig

def export_forecast_to_excel(forecast, selected_service, selected_metric):
    buffer = io.BytesIO()
    export_df = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].rename(columns={
        'ds': 'Date',
        'yhat': 'Forecast',
        'yhat_lower': 'Lower Bound',
        'yhat_upper': 'Upper Bound'
    })
    export_df['Date'] = export_df['Date'].dt.strftime('%Y-%m-%d %H:%M')
    export_df.insert(0, 'Service', selected_service)
    export_df.insert(1, 'Metric', selected_metric)
    export_df.to_excel(buffer, index=False, engine='openpyxl')
    return buffer


def send_email_with_attachment(recipient, buffer, subject):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = 'elegancia24by7@gmail.com'
    msg['To'] = recipient
    msg.set_content('Attached is the forecast.')

    buffer.seek(0)
    msg.add_attachment(buffer.read(), maintype='application', subtype='octet-stream', filename='forecast.xlsx')
    with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
        smtp.starttls()
        smtp.login('elegancia24by7@gmail.com', 'ibffqoteknrwhvux')
        smtp.send_message(msg)


# --- Streamlit Setup ---
st.set_page_config(page_title="Service Load Forecast", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
/* Fonts */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, .stApp {
    font-family: 'Inter', sans-serif;
    background-color: #f9fafb !important; /* Tailwind's gray-50 */
    color: #111827 !important;           /* Tailwind's gray-900 */
}

/* Headings and text */
h1, h2, h3, h4, h5, h6, label {
    color: #111827 !important;
}

/* Card styles */
.stContainer, .main, .block-container {
    background-color: #ffffff !important; /* white */
    border: 1px solid #e5e7eb;            /* gray-200 */
    border-radius: 0.5rem;                /* rounded-lg */
    padding: 1.5rem;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05); /* shadow-sm */
}

/* Selectbox and Multiselect input */
div[data-baseweb="select"] > div {
    background-color: #ffffff !important;
    color: #111827 !important;
    border: 1px solid #d1d5db !important; /* gray-300 */
    border-radius: 0.375rem;
}

/* Dropdown menu */
div[data-baseweb="menu"] {
    background-color: #ffffff !important;
    color: #111827 !important;
}

/* Dropdown options */
div[data-baseweb="menu"] div[role="option"] {
    color: #111827 !important;
}

/* Text input */
.stTextInput input {
    background-color: #ffffff !important;
    color: #111827 !important;
    border: 1px solid #d1d5db !important;
    border-radius: 0.375rem;
}

/* Buttons */
.stButton button, .stDownloadButton button {
    background-color: #2563eb !important; /* primary-600 */
    color: #ffffff !important;
    border-radius: 0.375rem;
    font-weight: 500;
    border: none;
    padding: 0.5rem 1rem;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.stButton button:hover, .stDownloadButton button:hover {
    background-color: #1d4ed8 !important; /* primary-700 */
}

/* Plotly chart override */
.plot-container {
    background-color: #111827 !important; /* dark mode for plot */
    border-radius: 0.5rem;
}

.plotly-graph-div .xtick text,
.plotly-graph-div .ytick text,
.plotly-graph-div .legend text {
    fill: #ffffff !important;
}
</style>
""", unsafe_allow_html=True)


st.title("📊 Service Load Forecast Dashboard")

try:
    collection = get_mongo_collection()
    data_cursor = list(collection.find({}))
except Exception as e:
    st.error(f"❌ Failed to connect to MongoDB: {e}")
    st.stop()

df = parse_mongo_data(data_cursor)
if df.empty:
    st.warning("No valid metric data available.")
    st.stop()

services = sorted(df["service"].unique())
selected_service = st.selectbox("Select a Service", services)
metrics = sorted(df[df["service"] == selected_service]["metric_type"].unique())
selected_metrics = st.multiselect("Select Metrics", metrics)
if not selected_metrics:
    st.warning("Please select at least one metric.")
    st.stop()

latest_forecast = None

for selected_metric in selected_metrics:
    filtered_df = df[
        (df["service"] == selected_service) &
        (df["metric_type"] == selected_metric)
    ].sort_values("timestamp")

    st.subheader(f"Short-term Forecast for {selected_metric}")
    agg_df_short = (
        filtered_df
        .set_index("timestamp")
        .resample("5min")["value"]
        .max()
        .dropna()
        .reset_index()
    )
    if len(agg_df_short) >= 2:
        forecast_short = run_prophet_forecast(agg_df_short, period=96, freq="5min")
        fig_short = plot_forecast(agg_df_short, forecast_short, f"Short-term Forecast for {selected_metric}", "Time")
        st.plotly_chart(fig_short, use_container_width=True)
    else:
        st.warning(f"Not enough data for short-term forecast of {selected_metric}")

    st.subheader(f"Monthly Forecast for {selected_metric}")
    agg_df_monthly = (
        filtered_df
        .set_index("timestamp")
        .resample("D")["value"]
        .max()
        .dropna()
        .reset_index()
    )
    if len(agg_df_monthly) >= 2:
        forecast_monthly = run_prophet_forecast(agg_df_monthly, period=30, freq="D")
        fig_monthly = plot_forecast(agg_df_monthly, forecast_monthly, f"Monthly Forecast for {selected_metric}", "Date")
        st.plotly_chart(fig_monthly, use_container_width=True)
        latest_forecast = forecast_monthly
    else:
        st.warning(f"Not enough data for monthly forecast of {selected_metric}")

# Export & Email
st.subheader('📤 Export Forecast Data')
if latest_forecast is not None:
    buffer = export_forecast_to_excel(latest_forecast, selected_service, selected_metric)
    st.download_button('📥 Download Forecast as Excel', data=buffer.getvalue(), file_name='forecast.xlsx')

    st.subheader('📧 Email Forecast Summary')
    recipient = st.text_input('Enter admin email')
    if st.button('Send Email') and recipient:
        try:
            send_email_with_attachment(recipient, buffer, f"Load Forecast: {selected_service}")
            st.success('📩 Email sent successfully!')
        except Exception as e:
            st.error(f"Failed to send email: {e}")

if st.button('🔁 Refresh Forecast'):
    st.experimental_rerun()

st.markdown('---')
st.markdown(f"Generated on: {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}")