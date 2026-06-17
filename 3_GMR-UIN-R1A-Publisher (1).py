# ============================================================
# GMR UIN R1A - MQTT Publisher
# UI Redesign: Dashboard Style (Scrollable Right Panel)
# Update patch: 2026-05-16
# ============================================================

import serial
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime
import pandas as pd
import paho.mqtt.client as mqtt
import sys

# ============================================================
# DETEKSI PLATFORM
# ============================================================
if sys.platform.startswith("win"):
    DEFAULT_PORT = "COM3"
elif sys.platform.startswith("linux"):
    DEFAULT_PORT = "/dev/ttyUSB0"
else:
    DEFAULT_PORT = "/dev/tty.usbserial-0001"

BAUD_RATE         = 9600
MQTT_BROKER       = "100.76.227.11"
MQTT_PORT         = 1883
MQTT_TOPIC_DATA   = "gmr/data"
MQTT_TOPIC_STATUS = "gmr/status"
MQTT_CLIENT_ID    = "GMR-Publisher"

def tegangan_ke_b(v):
    return 5.3381 * v - 4.2983

# ============================================================
# STATE GLOBAL
# ============================================================
data_waktu     = []
data_b         = []
collecting     = False
start_time     = None
ser            = None
mqtt_client    = None
mqtt_connected = False

# ============================================================
# WARNA
# ============================================================
BG          = "#f0f4f0"
PANEL       = "#ffffff"
HEADER_BG   = "#1a4a3a"
ACCENT      = "#1a6b55"
ACCENT2     = "#0d9b6e"
GREEN       = "#16a34a"
GREEN_LIGHT = "#22c55e"
RED         = "#dc2626"
YELLOW      = "#d97706"
TEXT        = "#0f2d1f"
SUBTEXT     = "#4a7a5a"
DIVIDER     = "#c6ddd0"
CARD_BG     = "#f7fbf9"
TEAL_DARK   = "#134e3a"
TEAL_MID    = "#1a6b55"

# ============================================================
# MQTT
# ============================================================
def on_mqtt_connect(client, userdata, flags, rc):
    global mqtt_connected

    if rc == 0:
        mqtt_connected = True
        update_mqtt_status("Connected", GREEN_LIGHT)

        client.publish(
            MQTT_TOPIC_STATUS,
            json.dumps({"status": "publisher_online"}),
            retain=True
        )

    else:
        mqtt_connected = False
        update_mqtt_status(f"Failed rc={rc}", RED)

def on_mqtt_disconnect(client, userdata, rc):
    global mqtt_connected

    mqtt_connected = False
    update_mqtt_status("Disconnected", RED)

def connect_mqtt():
    global mqtt_client, MQTT_BROKER, MQTT_PORT

    MQTT_BROKER = broker_var.get().strip()

    try:
        MQTT_PORT = int(mqttport_var.get().strip())

    except ValueError:
        log("Invalid MQTT port.")
        return

    try:
        if mqtt_client:
            try:
                mqtt_client.loop_stop()
                mqtt_client.disconnect()
            except:
                pass

        mqtt_client = mqtt.Client(
            client_id=MQTT_CLIENT_ID,
            protocol=mqtt.MQTTv311
        )

        mqtt_client.on_connect    = on_mqtt_connect
        mqtt_client.on_disconnect = on_mqtt_disconnect

        mqtt_client.will_set(
            MQTT_TOPIC_STATUS,
            json.dumps({"status": "publisher_offline"}),
            retain=True
        )

        mqtt_client.connect_async(
            MQTT_BROKER,
            MQTT_PORT,
            keepalive=60
        )

        mqtt_client.loop_start()

        log(f"Connecting MQTT to {MQTT_BROKER}:{MQTT_PORT}...")

    except Exception as e:
        update_mqtt_status("Error", RED)
        log(f"MQTT Error: {e}")

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
# SERIAL
# ============================================================
def connect_serial():
    global ser

    port = port_var.get().strip()

    try:
        baud = int(baud_var.get())

    except ValueError:
        log("Invalid baud rate.")
        return

    try:
        if ser and ser.is_open:
            ser.close()

        ser = serial.Serial(port, baud, timeout=1)
        ser.flush()

        update_serial_status("Connected", GREEN_LIGHT)

        lbl_serial_port_val.config(text=port)
        lbl_serial_baud_val.config(text=str(baud))

        log(f"Serial connected: {port} @ {baud}")

    except Exception as e:
        ser = None
        update_serial_status("Disconnected", RED)
        log(f"Serial error: {e}")

# ============================================================
# GUI HELPERS
# ============================================================
def update_mqtt_status(text, color):
    try:
        dot = "●"

        lbl_mqtt_conn_val.config(
            text=f"{dot} {text}",
            fg=color
        )

        if color == GREEN_LIGHT:
            lbl_header_status.config(
                text="● Loaded",
                fg=GREEN_LIGHT
            )

        else:
            lbl_header_status.config(
                text="● Offline",
                fg=RED
            )

    except:
        pass

def update_serial_status(text, color):
    try:
        dot = "●"

        lbl_serial_conn_val.config(
            text=f"{dot} {text}",
            fg=color
        )

    except:
        pass

def log(msg):
    try:
        ts = datetime.now().strftime("%H:%M:%S")

        txt_log.config(state=tk.NORMAL)
        txt_log.insert(tk.END, f"[{ts}]  {msg}\n")
        txt_log.see(tk.END)
        txt_log.config(state=tk.DISABLED)

    except:
        pass

# ============================================================
# CONTROL
# ============================================================
def mulai():
    global collecting, start_time

    if ser is None or not ser.is_open:
        messagebox.showwarning(
            "Warning",
            "Please connect the serial port first."
        )
        return

    collecting = True

    if start_time is None:
        start_time = datetime.now()

    log("Acquisition started")

    if mqtt_connected:
        mqtt_client.publish(
            MQTT_TOPIC_STATUS,
            json.dumps({"status": "collecting"})
        )

def berhenti():
    global collecting

    collecting = False

    log("Acquisition stopped")

    if mqtt_connected and mqtt_client:
        mqtt_client.publish(
            MQTT_TOPIC_STATUS,
            json.dumps({"status": "stopped"})
        )

def reset_data():
    global data_waktu, data_b, start_time, collecting

    collecting = False

    data_waktu.clear()
    data_b.clear()

    start_time = None

    line.set_data([], [])

    ax.relim()
    ax.autoscale_view()

    canvas.draw()

    lbl_last_b.config(text="B = -- mT")
    lbl_last_v.config(text="V = -- V")

    log("Data reset.")

def simpan_excel():
    if not data_waktu:
        messagebox.showwarning(
            "Warning",
            "No data available."
        )
        return

    fp = filedialog.asksaveasfilename(
        defaultextension=".xlsx",
        filetypes=[("Excel", "*.xlsx")]
    )

    if fp:
        try:
            pd.DataFrame({
                "t (s)": data_waktu,
                "B (mT)": data_b
            }).to_excel(fp, index=False)

            log(f"Saved: {fp}")

        except Exception as e:
            messagebox.showerror("Failed", str(e))

def simpan_gambar():
    fp = filedialog.asksaveasfilename(
        defaultextension=".png",
        filetypes=[("PNG", "*.png")]
    )

    if fp:
        fig.savefig(fp, dpi=150)
        log(f"Image saved: {fp}")

def keluar():
    if messagebox.askokcancel(
        "Exit",
        "Are you sure you want to exit?"
    ):

        berhenti()

        if mqtt_client:
            try:
                mqtt_client.publish(
                    MQTT_TOPIC_STATUS,
                    json.dumps({"status": "publisher_offline"}),
                    retain=True
                )

                mqtt_client.loop_stop()
                mqtt_client.disconnect()

            except:
                pass

        try:
            if ser and ser.is_open:
                ser.close()

        except:
            pass

        root.destroy()

# ============================================================
# ANIMATION
# ============================================================
def update(frame):
    global start_time

    if collecting and ser and ser.is_open:

        try:
            if ser.in_waiting:

                baris = ser.readline().decode("utf-8").strip()

                tegangan = float(baris)
                b_mT     = tegangan_ke_b(tegangan)

                if start_time is None:
                    start_time = datetime.now()

                waktu = (
                    datetime.now() - start_time
                ).total_seconds()

                data_waktu.append(waktu)
                data_b.append(b_mT)

                publish_data(
                    waktu,
                    tegangan,
                    b_mT
                )

                ts = datetime.now().strftime("%H:%M:%S")

                log_entry = (
                    f"t={waktu:.2f}s   "
                    f"V={tegangan:.4f}   "
                    f"B={b_mT:.4f}mT"
                )

                txt_log.config(state=tk.NORMAL)
                txt_log.insert(
                    tk.END,
                    f"[{ts}]  {log_entry}\n"
                )
                txt_log.see(tk.END)
                txt_log.config(state=tk.DISABLED)

                lbl_last_b.config(
                    text=f"B = {b_mT:.4f} mT"
                )

                lbl_last_v.config(
                    text=f"V = {tegangan:.4f} V"
                )

                line.set_data(
                    data_waktu,
                    data_b
                )

                ax.relim()
                ax.autoscale_view()

                canvas.draw()

        except Exception as e:
            log(f"Error: {e}")

    return line,

# ============================================================
# ROOT
# ============================================================
root = tk.Tk()

root.title("GMR UIN R1A - MQTT Publisher")
root.configure(bg=BG)
root.resizable(True, True)

try:
    root.state("zoomed")

except tk.TclError:
    try:
        root.attributes("-zoomed", True)

    except tk.TclError:
        root.geometry(
            f"{root.winfo_screenwidth()}x"
            f"{root.winfo_screenheight()}+0+0"
        )

# ============================================================
# HEADER
# ============================================================
frm_hdr = tk.Frame(
    root,
    bg=HEADER_BG,
    pady=8
)

frm_hdr.pack(fill=tk.X)

frm_hdr_left = tk.Frame(
    frm_hdr,
    bg=HEADER_BG
)

frm_hdr_left.pack(
    side=tk.LEFT,
    padx=16
)

tk.Label(
    frm_hdr_left,
    text="⊙",
    font=("Courier New", 22, "bold"),
    bg=HEADER_BG,
    fg=GREEN_LIGHT
).pack(side=tk.LEFT, padx=(0, 8))

frm_hdr_title = tk.Frame(
    frm_hdr_left,
    bg=HEADER_BG
)

frm_hdr_title.pack(side=tk.LEFT)

tk.Label(
    frm_hdr_title,
    text="GMR Real-Time Monitoring",
    font=("Courier New", 14, "bold"),
    bg=HEADER_BG,
    fg="#ffffff"
).pack(anchor=tk.W)

tk.Label(
    frm_hdr_title,
    text="(MQTT Publisher — GMR UIN R1A)",
    font=("Courier New", 9, "italic"),
    bg=HEADER_BG,
    fg="#a0c4b0"
).pack(anchor=tk.W)

frm_hdr_right = tk.Frame(
    frm_hdr,
    bg=HEADER_BG
)

frm_hdr_right.pack(
    side=tk.RIGHT,
    padx=20
)

tk.Label(
    frm_hdr_right,
    text="System Status",
    font=("Courier New", 9, "bold"),
    bg=HEADER_BG,
    fg="#a0c4b0"
).pack(anchor=tk.E)

lbl_header_status = tk.Label(
    frm_hdr_right,
    text="● Offline",
    font=("Courier New", 11, "bold"),
    bg=HEADER_BG,
    fg=RED
)

lbl_header_status.pack(anchor=tk.E)

# ============================================================
# BODY
# ============================================================
frm_body = tk.Frame(root, bg=BG)

frm_body.pack(
    fill=tk.BOTH,
    expand=True,
    padx=10,
    pady=6
)

# ============================================================
# LEFT PANEL
# ============================================================
frm_left = tk.Frame(frm_body, bg=BG)

frm_left.pack(
    side=tk.LEFT,
    fill=tk.BOTH,
    expand=True,
    padx=(0, 6)
)

# ============================================================
# GRAPH CARD
# ============================================================
frm_graph_card = tk.Frame(
    frm_left,
    bg=PANEL,
    relief=tk.FLAT,
    highlightbackground=DIVIDER,
    highlightthickness=1
)

frm_graph_card.pack(
    fill=tk.BOTH,
    expand=True
)

fig, ax = plt.subplots(
    figsize=(8, 3.2),
    facecolor=PANEL
)

ax.set_facecolor("#f2f9f5")

ax.set_title(
    "Magnetic Field vs. Time",
    color=TEAL_DARK,
    fontsize=11,
    fontweight="bold",
    pad=8
)

ax.set_xlabel(
    "Time, t (s)",
    color=SUBTEXT,
    fontsize=9
)

ax.set_ylabel(
    "Magnetic Field, B (mT)",
    color=SUBTEXT,
    fontsize=9
)

ax.tick_params(
    colors=SUBTEXT,
    labelsize=8
)

for sp in ax.spines.values():
    sp.set_color(DIVIDER)

ax.grid(
    True,
    color="#c6ddd0",
    linewidth=0.7,
    linestyle="--"
)

line, = ax.plot(
    [],
    [],
    lw=1.8,
    color=TEAL_DARK,
    label="Magnetic Field (mT)"
)

ax.legend(
    loc="upper right",
    fontsize=8,
    framealpha=0.7
)

canvas = FigureCanvasTkAgg(
    fig,
    master=frm_graph_card
)

canvas.get_tk_widget().pack(
    fill=tk.BOTH,
    expand=True,
    padx=6,
    pady=6
)

# ============================================================
# LIVE DATA CARD
# ============================================================
frm_live_card = tk.Frame(
    frm_left,
    bg=PANEL,
    relief=tk.FLAT,
    highlightbackground=DIVIDER,
    highlightthickness=1
)

frm_live_card.pack(
    fill=tk.X,
    pady=(6, 0)
)

frm_live_hdr = tk.Frame(
    frm_live_card,
    bg=PANEL
)

frm_live_hdr.pack(
    fill=tk.X,
    padx=10,
    pady=(6, 2)
)

tk.Label(
    frm_live_hdr,
    text="↗  LIVE DATA",
    font=("Courier New", 9, "bold"),
    bg=PANEL,
    fg=TEAL_DARK
).pack(side=tk.LEFT)

tk.Frame(
    frm_live_card,
    bg=DIVIDER,
    height=1
).pack(
    fill=tk.X,
    padx=10
)

frm_live_cols = tk.Frame(
    frm_live_card,
    bg=PANEL
)

frm_live_cols.pack(
    fill=tk.X,
    padx=10,
    pady=8
)

value_font = ("Courier New", 18, "bold")

# ============================================================
# B FIELD
# ============================================================
frm_col1 = tk.Frame(
    frm_live_cols,
    bg=PANEL
)

frm_col1.pack(
    side=tk.LEFT,
    fill=tk.BOTH,
    expand=True
)

tk.Label(
    frm_col1,
    text="MAGNETIC FIELD (B)",
    font=("Courier New", 8, "bold"),
    bg=PANEL,
    fg=TEAL_DARK
).pack(anchor=tk.W)

lbl_last_b = tk.Label(
    frm_col1,
    text="B = -- mT",
    font=value_font,
    bg=PANEL,
    fg=TEAL_DARK
)

lbl_last_b.pack(anchor=tk.W)

# Divider
tk.Frame(
    frm_live_cols,
    bg=DIVIDER,
    width=1
).pack(
    side=tk.LEFT,
    fill=tk.Y,
    padx=10
)

# ============================================================
# VOLTAGE
# ============================================================
frm_col2 = tk.Frame(
    frm_live_cols,
    bg=PANEL
)

frm_col2.pack(
    side=tk.LEFT,
    fill=tk.BOTH,
    expand=True
)

tk.Label(
    frm_col2,
    text="VOLTAGE (V)",
    font=("Courier New", 8, "bold"),
    bg=PANEL,
    fg=TEAL_DARK
).pack(anchor=tk.W)

lbl_last_v = tk.Label(
    frm_col2,
    text="V = -- V",
    font=value_font,
    bg=PANEL,
    fg=TEAL_DARK
)

lbl_last_v.pack(anchor=tk.W)

# ============================================================
# LOG CARD
# ============================================================
frm_log_card = tk.Frame(
    frm_left,
    bg=PANEL,
    relief=tk.FLAT,
    highlightbackground=DIVIDER,
    highlightthickness=1
)

frm_log_card.pack(
    fill=tk.X,
    pady=(6, 0)
)

frm_log_hdr = tk.Frame(
    frm_log_card,
    bg=PANEL
)

frm_log_hdr.pack(
    fill=tk.X,
    padx=10,
    pady=(6, 2)
)

tk.Label(
    frm_log_hdr,
    text="≡  LOG OUTPUT (Latest)",
    font=("Courier New", 9, "bold"),
    bg=PANEL,
    fg=TEAL_DARK
).pack(side=tk.LEFT)

tk.Frame(
    frm_log_card,
    bg=DIVIDER,
    height=1
).pack(
    fill=tk.X,
    padx=10
)

txt_log = tk.Text(
    frm_log_card,
    height=5,
    bg="#f2f9f5",
    fg=TEAL_DARK,
    font=("Courier New", 8),
    state=tk.DISABLED,
    relief=tk.FLAT,
    bd=0,
    wrap=tk.WORD
)

txt_log.pack(
    fill=tk.X,
    padx=10,
    pady=(4, 8)
)

# ============================================================
# RIGHT PANEL (SCROLLABLE)
# ============================================================
frm_right = tk.Frame(
    frm_body,
    bg=BG,
    width=300
)

frm_right.pack(
    side=tk.RIGHT,
    fill=tk.Y
)

frm_right.pack_propagate(False)

right_canvas = tk.Canvas(
    frm_right,
    bg=BG,
    highlightthickness=0,
    bd=0
)

right_scrollbar = ttk.Scrollbar(
    frm_right,
    orient="vertical",
    command=right_canvas.yview
)

right_canvas.configure(
    yscrollcommand=right_scrollbar.set
)

right_scrollbar.pack(
    side=tk.RIGHT,
    fill=tk.Y
)

right_canvas.pack(
    side=tk.LEFT,
    fill=tk.BOTH,
    expand=True
)

frm_right_inner = tk.Frame(
    right_canvas,
    bg=BG
)

right_window = right_canvas.create_window(
    (0, 0),
    window=frm_right_inner,
    anchor="nw"
)

def _update_scrollregion(event=None):
    right_canvas.configure(
        scrollregion=right_canvas.bbox("all")
    )

def _sync_width(event):
    right_canvas.itemconfig(
        right_window,
        width=event.width
    )

frm_right_inner.bind(
    "<Configure>",
    _update_scrollregion
)

right_canvas.bind(
    "<Configure>",
    _sync_width
)

# Mouse wheel support.
# Because humans cannot resist scrolling things.
def _on_mousewheel(event):
    right_canvas.yview_scroll(
        int(-1 * (event.delta / 120)),
        "units"
    )

right_canvas.bind_all(
    "<MouseWheel>",
    _on_mousewheel
)

# ============================================================
# CONNECTION CARD
# ============================================================
frm_conn_card = tk.Frame(
    frm_right_inner,
    bg=PANEL,
    relief=tk.FLAT,
    highlightbackground=DIVIDER,
    highlightthickness=1
)

frm_conn_card.pack(
    fill=tk.X,
    pady=(0, 6)
)

frm_conn_hdr = tk.Frame(
    frm_conn_card,
    bg=PANEL
)

frm_conn_hdr.pack(
    fill=tk.X,
    padx=10,
    pady=(8, 2)
)

tk.Label(
    frm_conn_hdr,
    text="(ᵠ)  CONNECTION STATUS",
    font=("Courier New", 9, "bold"),
    bg=PANEL,
    fg=TEAL_DARK
).pack(anchor=tk.W)

tk.Frame(
    frm_conn_card,
    bg=DIVIDER,
    height=1
).pack(
    fill=tk.X,
    padx=10,
    pady=(2, 6)
)

# ============================================================
# SERIAL SECTION
# ============================================================
frm_serial_sec = tk.Frame(
    frm_conn_card,
    bg=PANEL
)

frm_serial_sec.pack(
    fill=tk.X,
    padx=10,
    pady=(0, 4)
)

tk.Label(
    frm_serial_sec,
    text="⊟  SERIAL PORT",
    font=("Courier New", 8, "bold"),
    bg=PANEL,
    fg=TEAL_DARK
).pack(anchor=tk.W, pady=(0, 4))

frm_port_row = tk.Frame(
    frm_serial_sec,
    bg=PANEL
)

frm_port_row.pack(fill=tk.X, pady=1)

tk.Label(
    frm_port_row,
    text="Port",
    font=("Courier New", 8),
    bg=PANEL,
    fg=SUBTEXT,
    width=12,
    anchor=tk.W
).pack(side=tk.LEFT)

port_var = tk.StringVar(value=DEFAULT_PORT)

tk.Entry(
    frm_port_row,
    textvariable=port_var,
    font=("Courier New", 8),
    bg="#f2f9f5",
    fg=TEAL_DARK,
    relief=tk.FLAT,
    bd=2,
    width=12,
    insertbackground=TEAL_DARK
).pack(side=tk.LEFT)

frm_baud_row = tk.Frame(
    frm_serial_sec,
    bg=PANEL
)

frm_baud_row.pack(fill=tk.X, pady=1)

tk.Label(
    frm_baud_row,
    text="Baud Rate",
    font=("Courier New", 8),
    bg=PANEL,
    fg=SUBTEXT,
    width=12,
    anchor=tk.W
).pack(side=tk.LEFT)

baud_var = tk.StringVar(value=str(BAUD_RATE))

ttk.Combobox(
    frm_baud_row,
    textvariable=baud_var,
    values=["9600", "19200", "38400", "57600", "115200"],
    font=("Courier New", 8),
    width=10
).pack(side=tk.LEFT)

frm_serial_conn = tk.Frame(
    frm_serial_sec,
    bg=PANEL
)

frm_serial_conn.pack(fill=tk.X, pady=1)

tk.Label(
    frm_serial_conn,
    text="Connection",
    font=("Courier New", 8),
    bg=PANEL,
    fg=SUBTEXT,
    width=12,
    anchor=tk.W
).pack(side=tk.LEFT)

lbl_serial_conn_val = tk.Label(
    frm_serial_conn,
    text="● Disconnected",
    font=("Courier New", 8, "bold"),
    bg=PANEL,
    fg=RED
)

lbl_serial_conn_val.pack(side=tk.LEFT)

frm_serial_info = tk.Frame(
    frm_serial_sec,
    bg=PANEL
)

frm_serial_info.pack(
    fill=tk.X,
    pady=(2, 0)
)

lbl_serial_port_val = tk.Label(
    frm_serial_info,
    text="",
    font=("Courier New", 7),
    bg=PANEL,
    fg=SUBTEXT
)

lbl_serial_port_val.pack(anchor=tk.W)

lbl_serial_baud_val = tk.Label(
    frm_serial_info,
    text="",
    font=("Courier New", 7),
    bg=PANEL,
    fg=SUBTEXT
)

lbl_serial_baud_val.pack(anchor=tk.W)

tk.Button(
    frm_serial_sec,
    text="Connect Serial",
    command=connect_serial,
    bg=ACCENT2,
    fg="#ffffff",
    font=("Courier New", 8, "bold"),
    relief=tk.FLAT,
    cursor="hand2",
    pady=4
).pack(
    fill=tk.X,
    pady=(6, 0)
)

tk.Frame(
    frm_conn_card,
    bg=DIVIDER,
    height=1
).pack(
    fill=tk.X,
    padx=10,
    pady=6
)

# ============================================================
# MQTT SECTION
# ============================================================
frm_mqtt_sec = tk.Frame(
    frm_conn_card,
    bg=PANEL
)

frm_mqtt_sec.pack(
    fill=tk.X,
    padx=10,
    pady=(0, 8)
)

tk.Label(
    frm_mqtt_sec,
    text="(ᵠ)  MQTT BROKER",
    font=("Courier New", 8, "bold"),
    bg=PANEL,
    fg=TEAL_DARK
).pack(anchor=tk.W, pady=(0, 4))

frm_broker_row = tk.Frame(
    frm_mqtt_sec,
    bg=PANEL
)

frm_broker_row.pack(fill=tk.X, pady=1)

tk.Label(
    frm_broker_row,
    text="Broker IP",
    font=("Courier New", 8),
    bg=PANEL,
    fg=SUBTEXT,
    width=12,
    anchor=tk.W
).pack(side=tk.LEFT)

broker_var = tk.StringVar(value=MQTT_BROKER)

tk.Entry(
    frm_broker_row,
    textvariable=broker_var,
    font=("Courier New", 8),
    bg="#f2f9f5",
    fg=TEAL_DARK,
    relief=tk.FLAT,
    bd=2,
    width=14,
    insertbackground=TEAL_DARK
).pack(side=tk.LEFT)

frm_mqttport_row = tk.Frame(
    frm_mqtt_sec,
    bg=PANEL
)

frm_mqttport_row.pack(fill=tk.X, pady=1)

tk.Label(
    frm_mqttport_row,
    text="Port",
    font=("Courier New", 8),
    bg=PANEL,
    fg=SUBTEXT,
    width=12,
    anchor=tk.W
).pack(side=tk.LEFT)

mqttport_var = tk.StringVar(value=str(MQTT_PORT))

tk.Entry(
    frm_mqttport_row,
    textvariable=mqttport_var,
    font=("Courier New", 8),
    bg="#f2f9f5",
    fg=TEAL_DARK,
    relief=tk.FLAT,
    bd=2,
    width=8,
    insertbackground=TEAL_DARK
).pack(side=tk.LEFT)

frm_topic_row = tk.Frame(
    frm_mqtt_sec,
    bg=PANEL
)

frm_topic_row.pack(fill=tk.X, pady=1)

tk.Label(
    frm_topic_row,
    text="Topic",
    font=("Courier New", 8),
    bg=PANEL,
    fg=SUBTEXT,
    width=12,
    anchor=tk.W
).pack(side=tk.LEFT)

tk.Label(
    frm_topic_row,
    text=MQTT_TOPIC_DATA,
    font=("Courier New", 8),
    bg=PANEL,
    fg=TEXT
).pack(side=tk.LEFT)

frm_mqtt_conn = tk.Frame(
    frm_mqtt_sec,
    bg=PANEL
)

frm_mqtt_conn.pack(fill=tk.X, pady=1)

tk.Label(
    frm_mqtt_conn,
    text="Connection",
    font=("Courier New", 8),
    bg=PANEL,
    fg=SUBTEXT,
    width=12,
    anchor=tk.W
).pack(side=tk.LEFT)

lbl_mqtt_conn_val = tk.Label(
    frm_mqtt_conn,
    text="● Disconnected",
    font=("Courier New", 8, "bold"),
    bg=PANEL,
    fg=RED
)

lbl_mqtt_conn_val.pack(side=tk.LEFT)

tk.Button(
    frm_mqtt_sec,
    text="Connect MQTT",
    command=connect_mqtt,
    bg=YELLOW,
    fg="#1a1a2e",
    font=("Courier New", 8, "bold"),
    relief=tk.FLAT,
    cursor="hand2",
    pady=4
).pack(
    fill=tk.X,
    pady=(6, 0)
)

# ============================================================
# CONTROL CARD
# ============================================================
frm_ctrl_card = tk.Frame(
    frm_right_inner,
    bg=PANEL,
    relief=tk.FLAT,
    highlightbackground=DIVIDER,
    highlightthickness=1
)

frm_ctrl_card.pack(
    fill=tk.X,
    pady=(0, 6)
)

frm_ctrl_hdr = tk.Frame(
    frm_ctrl_card,
    bg=PANEL
)

frm_ctrl_hdr.pack(
    fill=tk.X,
    padx=10,
    pady=(8, 2)
)

tk.Label(
    frm_ctrl_hdr,
    text="⚙  ACQUISITION CONTROL",
    font=("Courier New", 9, "bold"),
    bg=PANEL,
    fg=TEAL_DARK
).pack(anchor=tk.W)

tk.Frame(
    frm_ctrl_card,
    bg=DIVIDER,
    height=1
).pack(
    fill=tk.X,
    padx=10,
    pady=(2, 6)
)

frm_ctrl_btns = tk.Frame(
    frm_ctrl_card,
    bg=PANEL
)

frm_ctrl_btns.pack(
    fill=tk.X,
    padx=10,
    pady=(0, 4)
)

tk.Button(
    frm_ctrl_btns,
    text="▶  START",
    command=mulai,
    bg=GREEN,
    fg="#ffffff",
    font=("Courier New", 9, "bold"),
    relief=tk.FLAT,
    cursor="hand2",
    pady=6
).pack(
    fill=tk.X,
    pady=(0, 3)
)

tk.Button(
    frm_ctrl_btns,
    text="■  STOP",
    command=berhenti,
    bg=YELLOW,
    fg="#1a1a2e",
    font=("Courier New", 9, "bold"),
    relief=tk.FLAT,
    cursor="hand2",
    pady=6
).pack(
    fill=tk.X,
    pady=(0, 3)
)

frm_btns2 = tk.Frame(
    frm_ctrl_btns,
    bg=PANEL
)

frm_btns2.pack(
    fill=tk.X,
    pady=(0, 3)
)

tk.Button(
    frm_btns2,
    text="RESET",
    command=reset_data,
    bg="#e2ede6",
    fg=TEXT,
    font=("Courier New", 8, "bold"),
    relief=tk.FLAT,
    cursor="hand2",
    pady=5
).pack(
    side=tk.LEFT,
    fill=tk.X,
    expand=True,
    padx=(0, 2)
)

tk.Button(
    frm_btns2,
    text="EXCEL",
    command=simpan_excel,
    bg="#e2ede6",
    fg=TEXT,
    font=("Courier New", 8, "bold"),
    relief=tk.FLAT,
    cursor="hand2",
    pady=5
).pack(
    side=tk.LEFT,
    fill=tk.X,
    expand=True,
    padx=(0, 2)
)

tk.Button(
    frm_btns2,
    text="IMAGE",
    command=simpan_gambar,
    bg="#e2ede6",
    fg=TEXT,
    font=("Courier New", 8, "bold"),
    relief=tk.FLAT,
    cursor="hand2",
    pady=5
).pack(
    side=tk.LEFT,
    fill=tk.X,
    expand=True
)

tk.Button(
    frm_ctrl_btns,
    text="EXIT PROGRAM",
    command=keluar,
    bg=RED,
    fg="#ffffff",
    font=("Courier New", 9, "bold"),
    relief=tk.FLAT,
    cursor="hand2",
    pady=6
).pack(
    fill=tk.X,
    pady=(0, 6)
)

# ============================================================
# RUN
# ============================================================
ani = animation.FuncAnimation(
    fig,
    update,
    interval=100,
    cache_frame_data=False
)

root.protocol(
    "WM_DELETE_WINDOW",
    keluar
)

log(
    f"Platform: {sys.platform} | "
    f"Default port: {DEFAULT_PORT}"
)

log(
    "Connect Serial & MQTT, then press START."
)

root.mainloop()

# signed by:
# Gilang Pratama Putra Siswanto (2026-05-16)