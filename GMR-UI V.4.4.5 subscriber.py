# ============================================================
# GMR UIN R1A
# MQTT SUBSCRIBER with HiveMQ + Plotly Dash
# FIXED VERSION
# ============================================================

import json
import time
from datetime import datetime
import pandas as pd
import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash.exceptions import PreventUpdate
import paho.mqtt.client as mqtt
import os

# ============================================================
# MQTT CONFIG
# ============================================================
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883

MQTT_TOPIC_DEFAULT = "gmr/data"

MQTT_CLIENT_ID = f"GMR-Subscriber-{int(time.time())}"

# ============================================================
# GLOBAL DATA
# ============================================================
data_waktu = []
data_b = []
data_v = []

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

    print(formatted)

    if not log_messages or formatted != log_messages[-1]:
        log_messages.append(formatted)

    if len(log_messages) > 100:
        log_messages.pop(0)

# ============================================================
# MQTT CALLBACK
# ============================================================
def on_connect(client, userdata, flags, rc):

    global mqtt_connected

    if rc == 0:

        mqtt_connected = True

        client.subscribe(MQTT_TOPIC_DEFAULT)

        add_log(
            f"MQTT Connected -> {MQTT_TOPIC_DEFAULT}"
        )

    else:

        mqtt_connected = False

        add_log(f"MQTT Failed rc={rc}")

# ============================================================
# MQTT DISCONNECT
# ============================================================
def on_disconnect(client, userdata, rc):

    global mqtt_connected

    mqtt_connected = False

    add_log("MQTT Disconnected")

# ============================================================
# MQTT MESSAGE
# ============================================================
def on_message(client, userdata, msg):

    global data_waktu
    global data_v
    global data_b

    try:

        print("RAW DATA :", msg.payload)

        payload = json.loads(
            msg.payload.decode()
        )

        t = payload.get("t_s", 0)
        v = payload.get("v_V", 0)
        b = payload.get("b_mT", 0)

        data_waktu.append(t)
        data_v.append(v)
        data_b.append(b)

        if len(data_waktu) > 10000:

            data_waktu.pop(0)
            data_v.pop(0)
            data_b.pop(0)

        add_log(
            f"Received -> B={b:.4f} mT"
        )

    except Exception as e:

        add_log(f"Data Error : {e}")

# ============================================================
# CONNECT MQTT
# ============================================================
def connect_mqtt(topic):

    global mqtt_client
    global MQTT_TOPIC_DEFAULT

    try:

        MQTT_TOPIC_DEFAULT = topic.strip()

        # disconnect lama
        if mqtt_client:

            mqtt_client.loop_stop()
            mqtt_client.disconnect()

        mqtt_client = mqtt.Client(
            client_id=MQTT_CLIENT_ID,
            protocol=mqtt.MQTTv311
        )

        mqtt_client.on_connect = on_connect
        mqtt_client.on_disconnect = on_disconnect
        mqtt_client.on_message = on_message

        # CONNECT LANGSUNG
        mqtt_client.connect(
            MQTT_BROKER,
            MQTT_PORT,
            keepalive=60
        )

        mqtt_client.loop_start()

        add_log(
            f"Connecting MQTT -> {MQTT_TOPIC_DEFAULT}"
        )

        return True

    except Exception as e:

        add_log(f"MQTT Error : {e}")

        return False

# ============================================================
# DASH APP
# ============================================================
app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        dbc.icons.FONT_AWESOME
    ],
    title="GMR Subscriber",
    update_title=None
)

# ============================================================
# LAYOUT
# ============================================================
app.layout = dbc.Container([

    dbc.Row([

        dbc.Col(
            html.H3(
                "GMR UIN R1A - MQTT Subscriber",
                className="text-primary mb-0"
            ),
            width="auto"
        ),

        dbc.Col(
            html.Span(
                "Subscriber",
                className="text-muted small"
            ),
            width="auto"
        )

    ], className="mt-2 mb-2 align-items-center"),

    dbc.Row([

        # ====================================================
        # SIDEBAR
        # ====================================================
        dbc.Col([

            dbc.Card([

                dbc.CardHeader(
                    html.H6(
                        "HiveMQ Subscriber",
                        className="mb-0"
                    )
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
                            width=3
                        ),

                        dbc.Col(
                            dbc.Input(
                                id="topic-input",
                                value=MQTT_TOPIC_DEFAULT,
                                size="sm"
                            ),
                            width=9
                        )

                    ], className="mb-2"),

                    dbc.Button(
                        "Connect MQTT",
                        id="btn-connect",
                        color="success",
                        size="sm",
                        className="w-100 mb-1"
                    ),

                    dbc.Button(
                        "Disconnect MQTT",
                        id="btn-disconnect",
                        color="danger",
                        size="sm",
                        className="w-100 mb-2"
                    ),

                    html.Div(
                        id="mqtt-status",
                        className="small fw-bold text-center"
                    )

                ])

            ], className="mb-2"),

            dbc.Card([

                dbc.CardHeader(
                    html.H6(
                        "Control",
                        className="mb-0"
                    )
                ),

                dbc.CardBody([

                    dbc.Button(
                        "Reset Data",
                        id="btn-reset",
                        color="secondary",
                        size="sm",
                        className="w-100 mb-2"
                    ),

                    dbc.Button(
                        "Download Excel",
                        id="btn-download",
                        color="info",
                        size="sm",
                        className="w-100 mb-2"
                    ),

                    dbc.Button(
                        "EXIT PROGRAM",
                        id="btn-exit",
                        color="dark",
                        size="sm",
                        className="w-100"
                    )

                ])

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
                        className="text-primary text-center"
                    ),
                    width=4
                ),

                dbc.Col(
                    html.H6(
                        id="live-v",
                        className="text-center"
                    ),
                    width=4
                ),

                dbc.Col(
                    html.H6(
                        id="sample-count",
                        className="text-muted text-center"
                    ),
                    width=4
                )

            ], className="mt-4"),

            html.Hr(),

            html.H6("Log Output"),

            dcc.Textarea(
                id="log-area",
                style={
                    "width": "100%",
                    "height": "100px",
                    "fontFamily": "Courier New",
                    "fontSize": "12px"
                },
                readOnly=True
            )

        ], width=9)

    ]),

    dcc.Interval(
        id="interval-update",
        interval=400,
        n_intervals=0
    ),

    dcc.Download(id="download-excel")

], fluid=True)

# ============================================================
# MQTT CONNECT CALLBACK
# ============================================================
@app.callback(
    [
        Output("mqtt-status", "children"),
        Output("mqtt-status", "style")
    ],
    [
        Input("btn-connect", "n_clicks"),
        Input("btn-disconnect", "n_clicks")
    ],
    State("topic-input", "value"),
    prevent_initial_call=True
)
def mqtt_callback(connect_click,
                  disconnect_click,
                  topic):

    global mqtt_client
    global mqtt_connected

    ctx = callback_context.triggered_id

    # CONNECT
    if ctx == "btn-connect":

        success = connect_mqtt(topic)

        if success:

            return (
                f"✓ {topic}",
                {"color": "green"}
            )

        else:

            return (
                "✗ Failed",
                {"color": "red"}
            )

    # DISCONNECT
    elif ctx == "btn-disconnect":

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

            add_log(f"Disconnect Error : {e}")

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
    Input("interval-update", "n_intervals")
)
def update_graph(n):

    fig = go.Figure()

    if data_waktu:

        fig.add_trace(go.Scatter(
            x=data_waktu,
            y=data_b,
            mode="lines+markers",
            line=dict(width=2),
            marker=dict(size=3)
        ))

    fig.update_layout(
        title="Medan Magnet vs Waktu",
        xaxis_title="Waktu (s)",
        yaxis_title="B (mT)",
        template="plotly_white",
        height=520,
        showlegend=False,
        uirevision="constant"
    )

    return fig

# ============================================================
# LIVE INFO
# ============================================================
@app.callback(
    [
        Output("live-b", "children"),
        Output("live-v", "children"),
        Output("sample-count", "children")
    ],
    Input("interval-update", "n_intervals")
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
    Input("interval-update", "n_intervals")
)
def update_log(n):

    return "\n".join(log_messages[-20:])

# ============================================================
# RESET CALLBACK
# ============================================================
@app.callback(
    Output("btn-reset", "children"),
    Input("btn-reset", "n_clicks"),
    prevent_initial_call=True
)
def reset_data(n):

    data_waktu.clear()
    data_b.clear()
    data_v.clear()

    add_log("Data RESET")

    return "Reset Done"

# ============================================================
# DOWNLOAD CALLBACK
# ============================================================
@app.callback(
    Output("download-excel", "data"),
    Input("btn-download", "n_clicks"),
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
        f"GMR_Subscriber_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        f".xlsx"
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

    os._exit(0)

# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":

    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    s.connect(("8.8.8.8", 80))

    local_ip = s.getsockname()[0]

    s.close()

    print("=" * 70)
    print("🚀 GMR MQTT Subscriber Started")
    print("🌐 http://127.0.0.1:8051")
    print(f"🌐 http://{local_ip}:8051")
    print("=" * 70)

    app.run(
        debug=False,
        port=8051,
        host="0.0.0.0"
    )
