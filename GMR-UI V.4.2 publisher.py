from nicegui import ui
import paho.mqtt.client as mqtt
import json
from datetime import datetime
from collections import deque
import pandas as pd
import plotly.graph_objects as go

# ====================== KONFIGURASI ======================
BROKER = "localhost"
PORT = 1883
TOPIC_DATA = "gmr/data"
TOPIC_STATUS = "gmr/status"

# Kalibrasi (sama dengan Publisher)
def tegangan_ke_b(v):
    return 5.3381 * v - 4.2983

# ====================== CLASS CHANNEL ======================
class SensorChannel:
    def __init__(self, name, color):
        self.name = name
        self.color = color
        self.data_waktu = deque(maxlen=1000)
        self.data_b = deque(maxlen=1000)
        self.collecting = False
        self.start_time = None
        self.current_b = 0.0
        self.current_v = 0.0
        
        self.value_label = None
        self.plot = None
        self.fig = None

# Buat 2 Channel
ch1 = SensorChannel("Sample 1", "#0066ff")
ch2 = SensorChannel("Sample 2", "#ff8800")

mqtt_client = None
mqtt_connected = False
publisher_status = "unknown"

# ====================== MQTT ======================
def on_connect(client, userdata, flags, rc):
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        client.subscribe(TOPIC_DATA, qos=1)
        client.subscribe(TOPIC_STATUS, qos=0)
        ui.notify("✅ MQTT Terhubung", type='positive')
    else:
        ui.notify(f"❌ MQTT Gagal (rc={rc})", type='negative')

def on_disconnect(client, userdata, rc):
    global mqtt_connected
    mqtt_connected = False
    ui.notify("MQTT Terputus", type='warning')

def on_message(client, userdata, msg):
    global publisher_status
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        
        if msg.topic == TOPIC_STATUS:
            publisher_status = payload.get("status", "unknown")
            status_text = {
                "publisher_online": "Online",
                "collecting": "Collecting",
                "stopped": "Stopped",
                "publisher_offline": "Offline"
            }.get(publisher_status, publisher_status)
            status_color = {
                "publisher_online": "green",
                "collecting": "orange",
                "stopped": "blue",
                "publisher_offline": "red"
            }.get(publisher_status, "grey")
            pub_status_label.text = status_text
            pub_status_label.classes(f'text-{status_color}-500')
            
        elif msg.topic == TOPIC_DATA:
            v = payload.get("v_V", 0.0)
            b = payload.get("b_mT", tegangan_ke_b(v))
            t = payload.get("t_s", None)
            
            for ch in [ch1, ch2]:
                if ch.collecting:
                    ch.current_b = b
                    ch.current_v = v
                    if ch.start_time is None:
                        ch.start_time = datetime.now()
                    waktu = (datetime.now() - ch.start_time).total_seconds()
                    ch.data_waktu.append(waktu)
                    ch.data_b.append(b)
    except Exception as e:
        print(f"Error parsing message: {e}")

# ====================== MQTT CONTROL ======================
def connect_mqtt():
    global mqtt_client
    broker = broker_input.value
    port = int(port_input.value)
    
    try:
        if mqtt_client:
            mqtt_client.disconnect()
        
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        mqtt_client.on_connect = on_connect
        mqtt_client.on_disconnect = on_disconnect
        mqtt_client.on_message = on_message
        
        mqtt_client.connect(broker, port, 60)
        mqtt_client.loop_start()
    except Exception as e:
        ui.notify(f"Error koneksi: {e}", type='negative')

def disconnect_mqtt():
    global mqtt_client
    if mqtt_client:
        mqtt_client.disconnect()
    ui.notify("MQTT Diputus", type='info')

# ====================== KONTROL CHANNEL ======================
def start_channel(ch):
    ch.collecting = True
    if ch.start_time is None:
        ch.start_time = datetime.now()
    ui.notify(f"▶ {ch.name} dimulai", type='positive')

def stop_channel(ch):
    ch.collecting = False
    ui.notify(f"⏸ {ch.name} dihentikan", type='warning')

def reset_channel(ch):
    ch.collecting = False
    ch.start_time = None
    ch.data_waktu.clear()
    ch.data_b.clear()
    ui.notify(f"🔄 {ch.name} direset", type='info')

def save_excel(ch):
    if not ch.data_waktu:
        ui.notify("Belum ada data!", type='negative')
        return
    try:
        df = pd.DataFrame({
            'Waktu (s)': list(ch.data_waktu),
            'B (mT)': list(ch.data_b),
            'V (V)': [tegangan_ke_b(b) for b in ch.data_b]  # inverse jika perlu
        })
        filename = f"GMR_{ch.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df.to_excel(filename, index=False)
        ui.notify(f"✅ Tersimpan: {filename}", type='positive')
    except Exception as e:
        ui.notify(f"Gagal menyimpan: {e}", type='negative')

# ====================== LAYOUT GUI ======================
with ui.header().classes('justify-between items-center bg-[#0f172a] text-white p-4'):
    ui.label('GMR UIN R1A - Dual Sample Comparison').classes('text-h5 font-bold')

# MQTT Settings
with ui.card().classes('w-full m-4'):
    with ui.row().classes('items-center gap-4'):
        ui.label('MQTT Broker:').classes('font-bold')
        broker_input = ui.input(value=BROKER).classes('w-48')
        port_input = ui.input(value=str(PORT), label='Port').classes('w-24')
        ui.button('Connect', on_click=connect_mqtt, color='green')
        ui.button('Disconnect', on_click=disconnect_mqtt, color='red')
        
        global pub_status_label
        pub_status_label = ui.label('Disconnected').classes('font-bold ml-6')

# Main Content
with ui.row().classes('w-full gap-6 p-4'):
    for ch in [ch1, ch2]:
        with ui.column().classes('flex-1'):
            with ui.card().classes('w-full'):
                ui.label(ch.name).classes(f'text-h6 font-bold').style(f'color: {ch.color}')
                
                with ui.row().classes('gap-3 my-3'):
                    ui.button('▶ START', on_click=lambda c=ch: start_channel(c), color='green')
                    ui.button('⏸ STOP', on_click=lambda c=ch: stop_channel(c), color='orange')
                    ui.button('🔄 RESET', on_click=lambda c=ch: reset_channel(c), color='grey')
                    ui.button('💾 Excel', on_click=lambda c=ch: save_excel(c), color='blue')
                
                ch.value_label = ui.label('0.000 mT').classes('text-h3 font-bold mt-2').style(f'color: {ch.color}')
                
                # Plotly Figure
                ch.fig = go.Figure()
                ch.fig.update_layout(
                    title=f"Real-time {ch.name}",
                    xaxis_title="Waktu (detik)",
                    yaxis_title="Medan Magnet B (mT)",
                    template="plotly_dark",
                    height=420,
                    margin=dict(l=50, r=30, t=50, b=50)
                )
                ch.plot = ui.plotly(ch.fig).classes('w-full')

# ====================== UPDATE PLOT ======================
def update_ui():
    for ch in [ch1, ch2]:
        # Update nilai
        ch.value_label.text = f"{ch.current_b:.3f} mT"
        
        # Update plot
        if len(ch.data_waktu) > 1:
            ch.plot.figure.update_traces(
                x=list(ch.data_waktu),
                y=list(ch.data_b),
                selector=dict(type='scatter')
            )
            if len(ch.plot.figure.data) == 0:  # Tambah trace pertama
                ch.plot.figure.add_trace(go.Scatter(
                    x=list(ch.data_waktu),
                    y=list(ch.data_b),
                    mode='lines+markers',
                    line=dict(color=ch.color, width=2.5),
                    marker=dict(size=3)
                ))
            ch.plot.update()

ui.timer(0.25, update_ui)   # Update setiap 250ms

# ====================== RUN ======================
ui.run(
    title="GMR UIN R1A - Dual Sample Comparison",
    host='0.0.0.0',
    port=8050,
    dark=True,
    reload=False
)
