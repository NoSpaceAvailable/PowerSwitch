import subprocess
import threading
import time
import ctypes
from ctypes import wintypes

import customtkinter as ctk
from tkinter import messagebox
from PIL import Image, ImageDraw
import pystray

SHORT = 1
LONG = 60

INTERVAL = 3  # seconds

current_mode = SHORT
is_plugged = False
running = True
tray_icon = None

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")


# Power settings
def apply_time(minutes):
    try:
        subprocess.run(["powercfg", "/change", "monitor-timeout-dc", str(minutes)], check=True)
        subprocess.run(["powercfg", "/change", "monitor-timeout-ac", str(minutes)], check=True)
        subprocess.run(["powercfg", "/change", "standby-timeout-dc", str(minutes)], check=True)
        subprocess.run(["powercfg", "/change", "standby-timeout-ac", str(minutes)], check=True)
    except subprocess.CalledProcessError:
        messagebox.showerror("Error", "Run as Administrator")

def toggle():
    global current_mode
    current_mode = LONG if current_mode == SHORT else SHORT
    apply_time(current_mode)
    update_ui()


# Real-time AC detection
class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", wintypes.BYTE),
        ("BatteryFlag", wintypes.BYTE),
        ("BatteryLifePercent", wintypes.BYTE),
        ("Reserved1", wintypes.BYTE),
        ("BatteryLifeTime", wintypes.DWORD),
        ("BatteryFullLifeTime", wintypes.DWORD),
    ]

def check_ac_status():
    status = SYSTEM_POWER_STATUS()
    ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status))
    return status.ACLineStatus == 1


# User interface
def update_ui():
    mode_text = "1 minute" if current_mode == SHORT else "60 minutes"
    ac_text = "⚡ Plugged in" if is_plugged else "🔋 On battery"

    status_label.configure(
        text=f"{mode_text}\n{ac_text}"
    )

    toggle_button.configure(
        text=f"Switch to {'60 minutes' if current_mode == SHORT else '1 minute'}"
    )


# Mica effect
def enable_mica(hwnd):
    DWMWA_SYSTEMBACKDROP_TYPE = 38
    DWMSBT_MAINWINDOW = 2

    value = ctypes.c_int(DWMSBT_MAINWINDOW)
    ctypes.windll.dwmapi.DwmSetWindowAttribute(
        hwnd,
        DWMWA_SYSTEMBACKDROP_TYPE,
        ctypes.byref(value),
        ctypes.sizeof(value)
    )


# Tray icon
def on_double_click():
    show_window()

def ac_monitor_loop():
    global is_plugged, tray_icon
    while running:
        new_status = check_ac_status()
        if new_status != is_plugged:
            is_plugged = new_status
            # Schedule UI and tray updates on the Tk main thread
            def do_update():
                update_ui()
                if tray_icon is not None:
                    tray_icon.icon = create_battery_icon(is_plugged)
            app.after(0, do_update)
        time.sleep(INTERVAL)

def create_battery_icon(plugged):
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((10, 20, 50, 44), radius=6, outline=(255,255,255), width=3)
    draw.rectangle((50, 26, 56, 38), fill=(255,255,255))
    if plugged:
        fill_color = (0, 200, 0)
    else:
        fill_color = (255, 200, 0)
    draw.rectangle((14, 24, 46, 40), fill=fill_color)
    if plugged:
        draw.polygon(
            [(30,22),(24,34),(30,34),(26,44),(38,30),(32,30)],
            fill=(255,255,255)
        )
    return img

def create_tray_icon():
    menu = pystray.Menu(
        pystray.MenuItem("Show", show_window, default=True),
        pystray.MenuItem("Toggle", lambda: toggle()),
        pystray.MenuItem("Exit", lambda: exit_app())
    )
    return pystray.Icon(
        "PowerSwitcher",
        create_battery_icon(is_plugged),
        "PowerSwitcher",
        menu
    )

def setup_tray():
    # Run the tray icon event loop in this background thread
    tray_icon.run()

def hide_window():
    app.withdraw()

def show_window(icon=None, item=None):
    app.after(0, app.deiconify)

def exit_app(icon=None, item=None):
    global running
    running = False
    tray_icon.stop()
    app.destroy()


# Application
app = ctk.CTk()
app.title("PowerSwitcher")
app.geometry("360x220")
app.resizable(False, False)

container = ctk.CTkFrame(app, corner_radius=20)
container.pack(padx=20, pady=20, fill="both", expand=True)

title = ctk.CTkLabel(
    container,
    text="Switch power settings",
    font=ctk.CTkFont(size=18, weight="bold")
)
title.pack(pady=(15, 5))

status_label = ctk.CTkLabel(
    container,
    text="",
    font=ctk.CTkFont(size=15)
)
status_label.pack(pady=10)

toggle_button = ctk.CTkButton(
    container,
    text="",
    command=toggle,
    height=40,
    corner_radius=12
)
toggle_button.pack(pady=15, padx=30, fill="x")

# Initialise AC status
is_plugged = check_ac_status()

update_ui()

# Enable mica
app.update()
hwnd = ctypes.windll.user32.GetParent(app.winfo_id())
enable_mica(hwnd)

# Tray icon
tray_icon = create_tray_icon()
threading.Thread(target=setup_tray, daemon=True).start()

# Start AC monitoring thread
threading.Thread(target=ac_monitor_loop, daemon=True).start()

# Minimize to tray
app.protocol("WM_DELETE_WINDOW", hide_window)

app.mainloop()
