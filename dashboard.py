#!/usr/bin/env python
# coding: utf-8

# In[3]:


import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objs as go
import pandas as pd
import serial
import time
import os

# Serial Port Configuration
SERIAL_PORT = "/dev/cu.usbmodem34B7DA5D7D182"  # Update for your system
BAUD_RATE = 115200

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)  # Allow time for serial connection to initialize
except serial.SerialException:
    print(f"Error: Could not open serial port {SERIAL_PORT}. Check connection!")
    exit(1)

# File for CSV Storage
CSV_FILE = "sensor_data.csv"

# Ensure CSV file exists
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w") as file:
        file.write("Timestamp,Temperature,Humidity\n")

# Dash App Setup
app = dash.Dash(__name__)
app.layout = html.Div([
    html.H1("Hybrid System Dashboard", style={'textAlign': 'center'}),

    # Alert Message
    html.Div(id="alert-message", style={'textAlign': 'center', 'color': 'red', 'fontSize': '20px'}),

    # Live Mode Toggle
    html.Div([
        html.Label("Live Mode:"),
        dcc.RadioItems(
            id='live-mode',
            options=[
                {'label': 'ON (Real-Time Updates)', 'value': 'on'},
                {'label': 'OFF (Pause Graph)', 'value': 'off'}
            ],
            value='on',
            inline=True
        )
    ], style={'textAlign': 'center', 'margin': '10px'}),

    # Time Range Filter
    html.Label("Select Time Range:"),
    dcc.Dropdown(
        id='time-filter',
        options=[
            {'label': 'Last 5 minutes', 'value': '5'},
            {'label': 'Last 10 minutes', 'value': '10'},
            {'label': 'Last 30 minutes', 'value': '30'},
            {'label': 'Show All', 'value': 'all'}
        ],
        value='all',
        clearable=False,
        style={'width': '50%'}
    ),

    # Real-Time Statistics
    html.Div([
        html.H3("Current Sensor Data"),
        html.P(id="current-temp"),
        html.P(id="current-hum"),
        html.H3("Statistics"),
        html.P(id="avg-temp"),
        html.P(id="avg-hum"),
        html.P(id="max-temp"),
        html.P(id="min-temp")
    ], style={'textAlign': 'center', 'border': '2px solid #ccc', 'padding': '10px', 'margin': '10px'}),

    dcc.Graph(id='live-graph', config={'scrollZoom': True}),

    html.Div([
        html.Button("Download CSV", id="download-btn"),
        dcc.Download(id="download-dataframe-csv"),  # CSV Download Component
    ], style={'textAlign': 'center', 'margin': '20px'}),

    dcc.Interval(
        id='interval-component',
        interval=2000,  # Update every 2 seconds
        n_intervals=0
    )
])

# Function to Read Data from Arduino and Save to CSV
def read_serial_data():
    """ Reads serial data safely, ignoring invalid or incomplete lines. """
    while ser.in_waiting:  # Check if new data is available
        try:
            line = ser.readline().decode().strip()
            print(f"Raw Serial Data: {line}")

            # Extract numerical values using regex
            import re
            matches = re.findall(r"[-+]?\d*\.\d+|\d+", line)  # Extract all numbers
            
            if len(matches) < 2:  # Ensure we got at least 2 values
                print("Warning: Could not find both Temperature and Humidity, skipping...")
                continue

            temp = float(matches[0])  # First number = Temperature
            hum = float(matches[1])  # Second number = Humidity
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

            # Save to CSV
            with open(CSV_FILE, "a") as file:
                file.write(f"{timestamp},{temp},{hum}\n")

            print(f"[{timestamp}] Temp: {temp}°C, Hum: {hum}% (Saved to CSV)")
            return temp, hum  # Return as soon as valid data is found

        except ValueError:
            print("Error: Invalid number format, skipping...")
        except IndexError:
            print("Error: Data format issue, skipping...")

    return None, None  # Return None if no valid data found

# Callback to Update Graph, Statistics, and Alerts
@app.callback(
    [Output('live-graph', 'figure'),
     Output('current-temp', 'children'),
     Output('current-hum', 'children'),
     Output('avg-temp', 'children'),
     Output('avg-hum', 'children'),
     Output('max-temp', 'children'),
     Output('min-temp', 'children'),
     Output('alert-message', 'children')],
    [Input('interval-component', 'n_intervals'),
     Input('time-filter', 'value'),
     Input('live-mode', 'value')]
)
def update_dashboard(n, selected_range, live_mode):
    if live_mode == "off":
        return dash.no_update

    temp, hum = read_serial_data()

    # Ensure CSV exists and is not empty
    if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0:
        df = pd.read_csv(CSV_FILE)
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors='coerce')

        if selected_range != "all":
            time_limit = pd.Timestamp.now() - pd.to_timedelta(int(selected_range), unit='m')
            df = df[df["Timestamp"] >= time_limit]
    else:
        df = pd.DataFrame(columns=["Timestamp", "Temperature", "Humidity"])

    if df.empty or "Temperature" not in df.columns:
        return go.Figure(), "Temperature: --", "Humidity: --", "Avg Temp: --", "Avg Hum: --", "Max Temp: --", "Min Temp: --", ""

    # Compute statistics safely
    latest_temp = df["Temperature"].iloc[-1]
    latest_hum = df["Humidity"].iloc[-1]
    avg_temp = df["Temperature"].mean()
    avg_hum = df["Humidity"].mean()
    max_temp = df["Temperature"].max()
    min_temp = df["Temperature"].min()

    alert = ""
    if latest_temp > 35:
        alert = "⚠️ WARNING: High Temperature! (> 35°C)"
    elif latest_hum > 80:
        alert = "⚠️ WARNING: High Humidity! (> 80%)"

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Timestamp"], y=df["Temperature"], mode='lines+markers', name='Temperature (°C)', line=dict(color='red')))
    fig.add_trace(go.Scatter(x=df["Timestamp"], y=df["Humidity"], mode='lines+markers', name='Humidity (%)', line=dict(color='blue')))
    fig.update_layout(title="Real-Time Sensor Data (Updated Every 2s)", xaxis_title="Time", yaxis_title="Values", template="plotly_dark", xaxis=dict(rangeslider=dict(visible=True)))

    return fig, f"Temperature: {latest_temp}°C", f"Humidity: {latest_hum}%", f"Avg Temp: {avg_temp:.2f}°C", f"Avg Hum: {avg_hum:.2f}%", f"Max Temp: {max_temp}°C", f"Min Temp: {min_temp}°C", alert

# CSV Download Callback
@app.callback(
    Output("download-dataframe-csv", "data"),
    Input("download-btn", "n_clicks"),
    prevent_initial_call=True
)
def download_csv(n_clicks):
    return dcc.send_file(CSV_FILE)

# Run Dash App
if __name__ == '__main__':
    app.run_server(debug=True, port=8050)


# In[ ]:





# In[ ]:




