import time
import json
import st7796
import hr2046
import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)

disp = st7796.st7796()
touch = hr2046.hr2046()
disp.clear()

points = []
targets = [
    ("TOP-LEFT",  20, 20),
    ("TOP-RIGHT", 300, 20),
    ("BOTTOM-RIGHT", 300, 460),
    ("BOTTOM-LEFT", 20, 460),
]

print("=== TOUCH CALIBRATION ===")

for name, x, y in targets:
    disp.clear()
    disp.dre_rectangle(x-5, y-5, x+5, y+5, 0xF800)
    print(f"Touch {name}")

    while GPIO.input(17) == GPIO.HIGH:
        time.sleep(0.05)

    rx, ry = touch.read_touch_data()
    points.append((rx, ry))
    time.sleep(0.5)

calib = {
    "xmin": min(p[0] for p in points),
    "xmax": max(p[0] for p in points),
    "ymin": min(p[1] for p in points),
    "ymax": max(p[1] for p in points),
}

with open("touch_calib.json", "w") as f:
    json.dump(calib, f, indent=2)

print("Calibration saved:", calib)
disp.clear()
