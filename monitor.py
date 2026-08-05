import os
import time
import psutil
from datetime import timedelta


def get_cpu_temp():
    try:
        temp = os.popen("vcgencmd measure_temp").readline()
        return temp.replace("temp=", "").strip()
    except:
        return "N/A"


def get_cpu_clock():
    try:
        clock = os.popen("vcgencmd measure_clock arm").readline()
        hz = int(clock.split("=")[1])
        return round(hz / 1_000_000, 1)
    except:
        return "N/A"


def get_throttled():
    try:
        result = os.popen("vcgencmd get_throttled").readline()
        return result.strip()
    except:
        return "N/A"


def clear_screen():

    print("\033[2J\033[H", end="")


while True:
    clear_screen()

    cpu_usage = psutil.cpu_percent(interval=1)
    cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)

    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    net = psutil.net_io_counters()

    uptime_seconds = time.time() - psutil.boot_time()
    uptime = str(timedelta(seconds=int(uptime_seconds)))

    print("=" * 60)
    print("         RASPBERRY PI 5 SYSTEM MONITOR")
    print("=" * 60)

    print(f"Uptime         : {uptime}")
    print(f"CPU Usage      : {cpu_usage}%")
    print(f"CPU Frequency  : {get_cpu_clock()} MHz")
    print(f"CPU Temp       : {get_cpu_temp()}")
    print(f"Throttling     : {get_throttled()}")

    print("\n--- CPU Per Core ---")
    for i, usage in enumerate(cpu_per_core):
        print(f"Core {i}: {usage}%")

    print("\n--- RAM ---")
    print(
        f"Used: {ram.used / 1e9:.2f} GB / "
        f"{ram.total / 1e9:.2f} GB "
        f"({ram.percent}%)"
    )

    print("\n--- Disk ---")
    print(
        f"Used: {disk.used / 1e9:.2f} GB / "
        f"{disk.total / 1e9:.2f} GB "
        f"({disk.percent}%)"
    )

    print("\n--- Network ---")
    print(f"Sent     : {net.bytes_sent / 1e6:.2f} MB")
    print(f"Received : {net.bytes_recv / 1e6:.2f} MB")

    time.sleep(1)
