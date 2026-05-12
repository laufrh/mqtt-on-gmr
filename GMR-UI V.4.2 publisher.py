from nicegui import ui
import paho.mqtt.client as mqtt
import serial
import json
from datetime import datetime
from collections import deque
import pandas as pd
import plotly.graph_objects as go
import threading
import time

# ====================== KONFIGURASI ======================
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_DATA = "gmr/data"
MQTT_TOPIC_STATUS = "gmr/status"

def tegangan_ke_b(v):
    return 5.3381 * v - 4.2983

# ====================== GLOBAL ======================
ser = None
mqtt_client = None
running = True

# Channel Class
class PublisherChannel:
    def __init__(self, name, color):
        self.name = name
        self.color = color
        self.data_waktu = deque(maxlen=1000)
        self.data_b = deque(maxlen=1000)
        self.data_v = deque(maxlen=1000)
        self.collecting = False
        self.start_time = None
        self.current_b = 0.0
        self.fig = None
        self.plot = None
        self.value_label = None

ch1 = PublisherChannel("Sample 1", "#0066ff")
ch2 = PublisherChannel("Sample 2", "#ff8800")

lock = threading.Lock()

# ====================== MQTT ======================
def publish_data(t, v, b):
    if mqtt_client and mqtt_client.is_connected():
        payload = json.dumps({
            "timestamp": datetime.now().isoformat(),
            "t_s": round(t, 4),
            "v_V": round(v, 4),
            "b_mT": round(b, 4)
        })
        mqtt_client.publish(MQTT_TOPIC_DATA, payload, qos=1)

def connect_mqtt():
    global mqtt_client
    try:
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        mqtt_client.on_connect = lambda c,u,f,rc: ui.notify("✅ MQTT Terhubung", type='positive')
        mqtt_client.will_set(MQTT_TOPIC_STATUS, json.dumps({"status": "publisher_offline"}), retain=True)
        mqtt_client.connect(broker_input.value, int(port_input.value), 60)
        mqtt_client.loop_start()
    except Exception as e:
        ui.notify(f"MQTT Error: {e}", type='negative')

# ====================== SERIAL ======================
def connect_serial():
    global ser
    try:
        if ser and ser.is_open: ser.close()
        ser = serial.Serial(port=serial_port.value, baudrate=int(baudrate.value), timeout=1)
        ser.flush()
        ui.notify(f"✅ Serial Terhubung: {serial_port.value}", type='positive')
    except Exception as e:
        ui.notify(f"Serial Gagal: {e}", type='negative')

# ====================== ACQUISITION THREAD ======================
def acquisition_thread():
    global ser
    while running:
        if ser and ser.is_open:
            try:
                if ser.in_waiting:
                    line = ser.readline().decode('utf-8').strip()
                    if line:
                        voltage = float(line)
                        b_mT = tegangan_ke_b(voltage)
                        t = 0

                        for ch in [ch1, ch2]:
                            if ch.collecting:
                                if ch.start_time is None:
                                    ch.start_time = datetime.now()
                                t = (datetime.now() - ch.start_time).total_seconds()
                                with lock:
                                    ch.data_waktu.append(t)
                                    ch.data_b.append(b_mT)
                                    ch.data_v.append(voltage)
                                ch.current_b = b_mT

                        publish_data(t, voltage, b_mT)
            except:
                pass
        time.sleep(0.05)

# ====================== KONTROL ======================
def start_channel(ch):
    ch.collecting = True
    ui.notify(f"▶ {ch.name} dimulai", type='positive')

def stop_channel(ch):
    ch.collecting = False
    ui.notify(f"⏸ {ch.name} dihentikan", type='warning')

def reset_channel(ch):
    ch.collecting = False
    ch.start_time = None
    with lock:
        ch.data_waktu.clear()
        ch.data_b.clear()
        ch.data_v.clear()
    ui.notify(f"🔄 {ch.name} direset", type='info')

def save_excel(ch):
    if not ch.data_waktu:
        ui.notify("Belum ada data!", type='negative')
        return
    try:
        df = pd.DataFrame({
            't (s)': list(ch.data_waktu),
            'V (V)': list(ch.data_v),
            'B (mT)': list(ch.data_b)
        })
        filename = f"GMR_{ch.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df.to_excel(filename, index=False)
        ui.notify(f"✅ Tersimpan: {filename}", type='positive')
    except Exception as e:
        ui.notify(f"Gagal: {e}", type='negative')

# ====================== UI ======================
with ui.header().classes('justify-between items-center bg-[#0f172a] text-white p-4'):
    ui.label('GMR UIN R1A - MQTT Publisher').classes('text-h5 font-bold')

# Settings
with ui.card().classes('w-full m-4'):
    with ui.row().classes('gap-6 items-center'):
        # Serial
        with ui.column():
            ui.label('Serial Port').classes('font-bold')
            serial_port = ui.input(value='COM3').classes('w-48')
            baudrate = ui.select([9600, 19200, 38400, 57600, 115200], value=9600)
            ui.button('Connect Serial', on_click=connect_serial, color='blue')

        # MQTT
        with ui.column():
            ui.label('MQTT Broker').classes('font-bold')
            broker_input = ui.input(value=MQTT_BROKER).classes('w-48')
            port_input = ui.input(value=str(MQTT_PORT)).classes('w-32')
            ui.button('Connect MQTT', on_click=connect_mqtt, color='green')

# Main Content - Dual Channel
with ui.row().classes('w-full gap-6 p-4'):
    for ch in [ch1, ch2]:
        with ui.column().classes('flex-1'):
            with ui.card().classes('w-full'):
                ui.label(ch.name).classes(f'text-h6 font-bold').style(f'color: {ch.color}')
                
                with ui.row().classes('gap-3 my-3 flex-wrap'):
                    ui.button('▶ START', on_click=lambda c=ch: start_channel(c), color='green')
                    ui.button('⏸ STOP', on_click=lambda c=ch: stop_channel(c), color='orange')
                    ui.button('🔄 RESET', on_click=lambda c=ch: reset_channel(c), color='grey')
                    ui.button('💾 Excel', on_click=lambda c=ch: save_excel(c), color='blue')

                ch.value_label = ui.label('0.000 mT').classes('text-h3 font-bold mt-2').style(f'color: {ch.color}')

                # Plot
                ch.fig = go.Figure()
                ch.fig.update_layout(
                    title=f"Real-time {ch.name}",
                    xaxis_title="Waktu (detik)",
                    yaxis_title="Medan Magnet B (mT)",
                    template="plotly_dark",
                    height=420
                )
                ch.plot = ui.plotly(ch.fig).classes('w-full')

# Update Plot Function
def update_plots():
    for ch in [ch1, ch2]:
        ch.value_label.text = f"{ch.current_b:.3f} mT"
        if len(ch.data_waktu) > 1:
            ch.plot.figure.update_traces(
                x=list(ch.data_waktu),
                y=list(ch.data_b),
                selector=dict(type='scatter')
            )
            if not ch.plot.figure.data:
                ch.plot.figure.add_trace(go.Scatter(
                    x=list(ch.data_waktu),
                    y=list(ch.data_b),
                    mode='lines+markers',
                    line=dict(color=ch.color, width=2.5)
                ))
            ch.plot.update()

ui.timer(0.25, update_plots)

# Start Thread
threading.Thread(target=acquisition_thread, daemon=True).start()

# Run
ui.run(
    title="GMR UIN R1A - MQTT Publisher",
    host='0.0.0.0',
    port=8040,
    dark=True,
    reload=False
)
