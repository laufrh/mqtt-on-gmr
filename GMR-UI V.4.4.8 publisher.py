# ============================================================
# GMR UIN R1A
# Update: 2026-05-13
# ============================================================

import serial
import json
import threading
import time
from datetime import datetime
import pandas as pd
import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash.exceptions import PreventUpdate
import paho.mqtt.client as mqtt
import sys
import os

# ============================================================
# CONFIG
# ============================================================
if sys.platform.startswith("win"):
    DEFAULT_PORT = "COM4"
elif sys.platform.startswith("linux"):
    DEFAULT_PORT = "/dev/ttyUSB0"
else:
    DEFAULT_PORT = "/dev/tty.usbserial-0001"

BAUD_RATE = 9600

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883

MQTT_TOPIC_BASE = "gmr/data"
MQTT_TOPIC_DATA = MQTT_TOPIC_BASE
MQTT_TOPIC_STATUS = MQTT_TOPIC_BASE + "/status"

MQTT_CLIENT_ID = f"GMR-Publisher-{int(time.time())}"

# ============================================================
# FUNCTION
# ============================================================
def tegangan_ke_b(v):
    return 5.3381 * v - 4.2983

# ============================================================
# GLOBAL STATE
# ============================================================
data_waktu = []
data_b = []
data_v = []

collecting = False

start_time = None
paused_time = 0.0

ser = None

mqtt_client = None
mqtt_connected = False

log_messages = []
last_sensor_log_time = 0

# ============================================================
# LOG FUNCTION
# ============================================================
def add_log(message):

    timestamp = datetime.now().strftime("%H:%M:%S")

    formatted = f"[{timestamp}] {message}"

    if not log_messages or formatted != log_messages[-1]:
        log_messages.append(formatted)

    if len(log_messages) > 100:
        log_messages.pop(0)

# ============================================================
# DASH APP
# ============================================================
app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        dbc.icons.FONT_AWESOME
    ],
    title="GMR UIN R1A",
    update_title=None,
    suppress_callback_exceptions=True
)

# ============================================================
# MQTT FUNCTIONS
# ============================================================
def on_mqtt_connect(client, userdata, flags, rc):

    global mqtt_connected

    mqtt_connected = (rc == 0)

    if mqtt_connected:
        add_log("MQTT Connected")
    else:
        add_log(f"MQTT Failed rc={rc}")

def on_mqtt_disconnect(client, userdata, rc):

    global mqtt_connected

    mqtt_connected = False

    add_log("MQTT Disconnected")

def connect_mqtt(broker, port):

    global mqtt_client

    try:

        if mqtt_client:
            mqtt_client.disconnect()

        mqtt_client = mqtt.Client(
            client_id=MQTT_CLIENT_ID,
            protocol=mqtt.MQTTv311
        )

        mqtt_client.on_connect = on_mqtt_connect
        mqtt_client.on_disconnect = on_mqtt_disconnect

        mqtt_client.will_set(
            MQTT_TOPIC_STATUS,
            json.dumps({"status": "publisher_offline"}),
            retain=True
        )

        mqtt_client.connect_async(
            broker,
            int(port),
            keepalive=60
        )

        mqtt_client.loop_start()

        return True

    except Exception as e:

        add_log(f"MQTT Error : {e}")

        return False

# ============================================================
# PUBLISH DATA
# ============================================================
def publish_data(t, v, b):

    if mqtt_client and mqtt_connected:

        payload = json.dumps({
            "timestamp": datetime.now().isoformat(),
            "t_s": round(t, 4),
            "v_V": round(v, 4),
            "b_mT": round(b, 4)
        })

        mqtt_client.publish(
            MQTT_TOPIC_DATA,
            payload,
            qos=1
        )

# ============================================================
# SERIAL THREAD
# ============================================================
def serial_reader():

    global collecting
    global start_time
    global paused_time
    global ser

    while True:

        if collecting and ser and ser.is_open:

            try:

                if ser.in_waiting:

                    baris = ser.readline().decode(
                        "utf-8"
                    ).strip()

                    if baris:

                        tegangan = float(baris)

                        b_mT = tegangan_ke_b(tegangan)

                        if start_time is None:
                            start_time = datetime.now()

                        elapsed = (
                            datetime.now() - start_time
                        ).total_seconds()

                        waktu = paused_time + elapsed

                        data_waktu.append(waktu)
                        data_v.append(tegangan)
                        data_b.append(b_mT)

                        publish_data(
                            waktu,
                            tegangan,
                            b_mT
                        )

                        if len(data_waktu) > 10000:

                            data_waktu.pop(0)
                            data_v.pop(0)
                            data_b.pop(0)

            except Exception as e:

                add_log(f"Serial Error : {e}")

        time.sleep(0.05)

# ============================================================
# LAYOUT
# ============================================================
app.layout = dbc.Container([

    dbc.Row([
        dbc.Col(
            html.H3(
                "GMR UIN R1A - Live Magnetic Field",
                className="text-primary mb-0"
            ),
            width="auto"
        ),

        dbc.Col(
            html.Span(
                "Publisher",
                className="text-muted small"
            ),
            width="auto"
        ),
    ], className="mb-2 mt-2 align-items-center"),

    dbc.Row([

        # ====================================================
        # SIDEBAR
        # ====================================================
        dbc.Col([

            # SERIAL CARD
            dbc.Card([

                dbc.CardHeader(
                    html.H6(
                        "Serial Port",
                        className="mb-0 py-1"
                    ),
                    className="py-1"
                ),

                dbc.CardBody([

                    dbc.Row([
                        dbc.Col(
                            dbc.Label(
                                "Port",
                                className="small"
                            ),
                            width=4
                        ),

                        dbc.Col(
                            dbc.Input(
                                id="port-input",
                                value=DEFAULT_PORT,
                                size="sm"
                            ),
                            width=8
                        ),
                    ], className="mb-1"),

                    dbc.Row([
                        dbc.Col(
                            dbc.Label(
                                "Baud",
                                className="small"
                            ),
                            width=4
                        ),

                        dbc.Col(
                            dbc.Select(
                                id="baud-input",
                                options=[
                                    {
                                        "label": b,
                                        "value": b
                                    }
                                    for b in [
                                        "9600",
                                        "19200",
                                        "38400",
                                        "57600",
                                        "115200"
                                    ]
                                ],
                                value=str(BAUD_RATE),
                                size="sm"
                            ),
                            width=8
                        ),
                    ], className="mb-2"),

                    dbc.Button(
                        "Connect Serial",
                        id="btn-serial",
                        color="primary",
                        size="sm",
                        className="w-100 mb-1"
                    ),

                    dbc.Button(
                        "Disconnect Serial",
                        id="btn-serial-disconnect",
                        color="danger",
                        size="sm",
                        className="w-100"
                    ),

                    html.Div(
                        id="serial-status",
                        className="small text-center mt-1 fw-bold"
                    ),

                ], className="py-2")

            ], className="mb-2"),

            # MQTT CARD
            dbc.Card([

                dbc.CardHeader(
                    html.H6(
                        "HiveMQ Broker",
                        className="mb-0 py-1"
                    ),
                    className="py-1"
                ),

                dbc.CardBody([

                    html.Div(
                        f"Broker : {MQTT_BROKER}",
                        className="small text-muted mb-1"
                    ),

                    html.Div(
                        f"Port : {MQTT_PORT}",
                        className="small text-muted mb-2"
                    ),

                    dbc.Row([
                        dbc.Col(
                            dbc.Label(
                                "Topic",
                                className="small"
                            ),
                            width=4
                        ),

                        dbc.Col(
                            dbc.Input(
                                id="topic-input",
                                value=MQTT_TOPIC_BASE,
                                size="sm"
                            ),
                            width=8
                        ),

                    ], className="mb-2"),

                    dbc.Button(
                        "Connect HiveMQ",
                        id="btn-mqtt",
                        color="success",
                        size="sm",
                        className="w-100 mb-1"
                    ),

                    dbc.Button(
                        "Disconnect MQTT",
                        id="btn-mqtt-disconnect",
                        color="danger",
                        size="sm",
                        className="w-100"
                    ),

                    html.Div(
                        id="mqtt-status",
                        className="small text-center mt-1 fw-bold"
                    ),

                ], className="py-2")

            ], className="mb-2"),

            # CONTROL CARD
            dbc.Card([

                dbc.CardHeader(
                    html.H6(
                        "Control",
                        className="mb-0 py-1"
                    ),
                    className="py-1"
                ),

                dbc.CardBody([

                    dbc.Row([

                        dbc.Col(
                            dbc.Button(
                                "START",
                                id="btn-start",
                                color="success",
                                size="sm",
                                className="w-100"
                            ),
                            width=6
                        ),

                        dbc.Col(
                            dbc.Button(
                                "STOP",
                                id="btn-stop",
                                color="warning",
                                size="sm",
                                className="w-100"
                            ),
                            width=6
                        ),

                    ], className="mb-2"),

                    dbc.Row([

                        dbc.Col(
                            dbc.Button(
                                "Reset",
                                id="btn-reset",
                                color="secondary",
                                size="sm",
                                className="w-100"
                            ),
                            width=6
                        ),

                        dbc.Col(
                            dbc.Button(
                                "Download",
                                id="btn-excel",
                                color="info",
                                size="sm",
                                className="w-100"
                            ),
                            width=6
                        ),

                    ], className="mb-2"),

                    dbc.Button(
                        "EXIT PROGRAM",
                        id="btn-exit",
                        color="dark",
                        size="sm",
                        className="w-100"
                    ),

                ], className="py-2")

            ])

        ], width=3),

        # ====================================================
        # MAIN AREA
        # ====================================================
        dbc.Col([

            dcc.Graph(
                id="live-graph",
                style={"height": "68vh"},
                config={
                    "scrollZoom": True,
                    "displayModeBar": True
                }
            ),

            dbc.Row([

                dbc.Col(
                    html.H6(
                        id="live-b",
                        className="text-primary text-center mb-0"
                    ),
                    width=4
                ),

                dbc.Col(
                    html.H6(
                        id="live-v",
                        className="text-center mb-0"
                    ),
                    width=4
                ),

                dbc.Col(
                    html.H6(
                        id="sample-count",
                        className="text-muted text-center mb-0"
                    ),
                    width=4
                ),

            ], className="mt-4 mb-2"),

            html.Hr(className="my-2"),

            html.H6(
                "Log Output",
                className="mb-1"
            ),

            dcc.Textarea(
                id="log-area",
                style={
                    "width": "100%",
                    "height": "80px",
                    "fontFamily": "Courier New",
                    "fontSize": "12.5px"
                },
                readOnly=True
            )

        ], width=9)

    ]),

    dcc.Interval(
        id="interval-graph",
        interval=400,
        n_intervals=0
    ),

    dcc.Store(id="store-data"),

    dcc.Download(id="download-excel"),

], fluid=True, style={
    "maxHeight": "100vh",
    "overflow": "hidden"
})

# ============================================================
# SERIAL CALLBACK
# ============================================================
@app.callback(
    [
        Output("serial-status", "children"),
        Output("serial-status", "style")
    ],
    [
        Input("btn-serial", "n_clicks"),
        Input("btn-serial-disconnect", "n_clicks")
    ],
    [
        State("port-input", "value"),
        State("baud-input", "value")
    ],
    prevent_initial_call=True
)
def serial_callback(connect_click, disconnect_click, port, baud):

    global ser
    global collecting

    ctx = callback_context.triggered_id

    # CONNECT
    if ctx == "btn-serial":

        try:

            if ser and ser.is_open:
                ser.close()

            ser = serial.Serial(
                port.strip(),
                int(baud),
                timeout=1
            )

            ser.flush()

            add_log(
                f"Serial connected : {port} @ {baud}"
            )

            return (
                f"✓ {port} @ {baud}",
                {"color": "green"}
            )

        except Exception as e:

            add_log(f"Serial failed : {e}")

            return (
                "✗ Failed",
                {"color": "red"}
            )

    # DISCONNECT
    elif ctx == "btn-serial-disconnect":

        try:

            collecting = False

            if ser and ser.is_open:
                ser.close()

            add_log("Serial disconnected")

            return (
                "Disconnected",
                {"color": "orange"}
            )

        except Exception as e:

            add_log(f"Disconnect error : {e}")

            return (
                "Disconnect Failed",
                {"color": "red"}
            )

    raise PreventUpdate

# ============================================================
# MQTT CALLBACK
# ============================================================
@app.callback(
    [
        Output("mqtt-status", "children"),
        Output("mqtt-status", "style")
    ],
    [
        Input("btn-mqtt", "n_clicks"),
        Input("btn-mqtt-disconnect", "n_clicks")
    ],
    State("topic-input", "value"),
    prevent_initial_call=True
)
def mqtt_callback(connect_click, disconnect_click, topic):

    global MQTT_TOPIC_DATA
    global MQTT_TOPIC_STATUS
    global mqtt_client
    global mqtt_connected

    ctx = callback_context.triggered_id

    # CONNECT
    if ctx == "btn-mqtt":

        MQTT_TOPIC_DATA = topic.strip()

        MQTT_TOPIC_STATUS = (
            topic.strip() + "/status"
        )

        success = connect_mqtt(
            MQTT_BROKER,
            MQTT_PORT
        )

        if success:

            add_log(
                f"MQTT connected : {MQTT_TOPIC_DATA}"
            )

            return (
                f"✓ Topic : {MQTT_TOPIC_DATA}",
                {"color": "green"}
            )

        else:

            add_log("MQTT connection failed")

            return (
                "✗ Failed",
                {"color": "red"}
            )

    # DISCONNECT
    elif ctx == "btn-mqtt-disconnect":

        try:

            if mqtt_client:
                mqtt_client.loop_stop()
                mqtt_client.disconnect()

            mqtt_connected = False

            add_log("MQTT disconnected")

            return (
                "Disconnected",
                {"color": "orange"}
            )

        except Exception as e:

            add_log(f"MQTT disconnect error : {e}")

            return (
                "Disconnect Failed",
                {"color": "red"}
            )

    raise PreventUpdate

# ============================================================
# GRAPH CALLBACK
# ============================================================
@app.callback(
    Output("live-graph", "figure"),
    Input("interval-graph", "n_intervals")
)
def update_graph(n):

    fig = go.Figure()

    if data_waktu:

        fig.add_trace(go.Scatter(
            x=data_waktu,
            y=data_b,
            mode='lines+markers',
            line=dict(
                color='#0077b6',
                width=2.5
            ),
            marker=dict(size=3)
        ))

    fig.update_layout(
        title="Medan Magnet vs Waktu (Real-time)",
        xaxis_title="Waktu (s)",
        yaxis_title="B (mT)",
        template="plotly_white",
        height=520,
        margin=dict(
            l=40,
            r=20,
            t=50,
            b=40
        ),
        showlegend=False,
        uirevision="constant"
    )

    return fig

# ============================================================
# LIVE INFO CALLBACK
# ============================================================
@app.callback(
    [
        Output("live-b", "children"),
        Output("live-v", "children"),
        Output("sample-count", "children")
    ],
    Input("interval-graph", "n_intervals")
)
def update_live_info(n):

    if not data_b:

        return (
            "B = - mT",
            "V = - V",
            "0 sampel"
        )

    return (
        f"B = {data_b[-1]:.4f} mT",
        f"V = {data_v[-1]:.4f} V",
        f"{len(data_b)} sampel"
    )

# ============================================================
# LOG CALLBACK
# ============================================================
@app.callback(
    Output("log-area", "value"),
    Input("interval-graph", "n_intervals")
)
def update_log(n):

    global last_sensor_log_time

    current_time = time.time()

    if data_b and (
        current_time - last_sensor_log_time > 2
    ):

        add_log(
            f"B={data_b[-1]:.4f} mT | "
            f"V={data_v[-1]:.4f} V | "
            f"{len(data_b)} sampel"
        )

        last_sensor_log_time = current_time

    return "\n".join(log_messages[-20:])

# ============================================================
# CONTROL CALLBACK
# ============================================================
@app.callback(
    Output("store-data", "data"),
    Input("btn-start", "n_clicks"),
    Input("btn-stop", "n_clicks"),
    Input("btn-reset", "n_clicks"),
    prevent_initial_call=True
)
def control_collection(start, stop, reset):

    global collecting
    global start_time
    global paused_time

    ctx = callback_context.triggered_id

    # START
    if ctx == "btn-start":

        if ser and ser.is_open:

            collecting = True

            if start_time is None:
                start_time = datetime.now()

            add_log(
                "Data collection STARTED"
            )

            return "started"

    # STOP
    elif ctx == "btn-stop":

        if start_time is not None:

            elapsed = (
                datetime.now() - start_time
            ).total_seconds()

            paused_time += elapsed

            start_time = None

        collecting = False

        add_log(
            "Data collection STOPPED"
        )

        return "stopped"

    # RESET
    elif ctx == "btn-reset":

        collecting = False

        data_waktu.clear()
        data_b.clear()
        data_v.clear()

        start_time = None
        paused_time = 0.0

        add_log("Data RESET")

        return "reset"

    return dash.no_update

# ============================================================
# DOWNLOAD CALLBACK
# ============================================================
@app.callback(
    Output("download-excel", "data"),
    Input("btn-excel", "n_clicks"),
    prevent_initial_call=True
)
def download_excel(n):

    if not data_waktu:
        raise PreventUpdate

    df = pd.DataFrame({
        "t (s)": data_waktu,
        "B (mT)": data_b,
        "V (V)": data_v
    })

    filename = (
        f"GMR_Data_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        f".xlsx"
    )

    add_log(
        f"Excel downloaded : {filename}"
    )

    return dcc.send_data_frame(
        df.to_excel,
        filename,
        index=False
    )

# ============================================================
# EXIT CALLBACK
# ============================================================
@app.callback(
    Output("btn-exit", "children"),
    Input("btn-exit", "n_clicks"),
    prevent_initial_call=True
)
def exit_program(n):

    add_log("Application closed")

    os._exit(0)

# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":

    threading.Thread(
        target=serial_reader,
        daemon=True
    ).start()

    print("=" * 70)
    print("🚀 GMR UIN R1A - Compact Version Started")
    print("🌐 http://127.0.0.1:8050")
    print("=" * 70)

    app.run(
        debug=False,
        port=8050,
        host="0.0.0.0"
    )
