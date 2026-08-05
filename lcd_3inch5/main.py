#!/usr/bin/python
# -*- coding: UTF-8 -*-

import time
import sys
from lcd_3inch5 import st7796
from lcd_3inch5 import hr2046
import RPi.GPIO as GPIO

from PIL import Image, ImageDraw, ImageFont

# ================= GPIO =================
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# ================= LCD & TOUCH =================
disp = st7796.st7796()
touch = hr2046.hr2046()
disp.clear()

# ================= SCREEN =================
SCREEN_W = 320
SCREEN_H = 480

BTN_X = 30
BTN_W = 260
BTN_H = 60
BTN_GAP = 20

# ================= FONT =================
font_title = ImageFont.load_default()
font_btn   = ImageFont.load_default()
font_log   = ImageFont.load_default()

# ================= TOUCH MAP (CALIBRATION CỦA BẠN) =================
def map_touch(rx, ry):
    x = int((ry + 7) * SCREEN_W / (290 + 7))
    y = int((rx - 48) * SCREEN_H / (464 - 48))

    x = max(0, min(SCREEN_W - 1, x))
    y = max(0, min(SCREEN_H - 1, y))

    # đảo tọa độ vì màn hình rotate 180
    x = SCREEN_W - x
    y = SCREEN_H - y

    return x, y

# ================= CANVAS =================
def new_canvas():
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), "black")
    return img, ImageDraw.Draw(img)

def show(img):
    img = img.rotate(180)
    disp.show_image(img)

# ================= LOG =================
log_lines = []

def log(msg):
    global log_lines
    print("[UI]", msg)
    log_lines.append(msg)
    if len(log_lines) > 5:
        log_lines = log_lines[-5:]

def draw_logs(draw):
    y = 380
    for line in log_lines:
        draw.text((10, y), line, fill="yellow", font=font_log)
        y += 18

# ================= COMMAND DISPATCH =================
def send_cmd(cmd):
    log(f"CMD -> {cmd}")
    # Sau này:
    # - gửi UART
    # - MQTT
    # - ROS2
    # - Socket

# ================= BUTTON =================
class Button:
    def __init__(self, x, y, w, h, text, action):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.text = text
        self.action = action

    def draw(self, draw):
        draw.rectangle(
            (self.x, self.y, self.x+self.w, self.y+self.h),
            outline="green",
            width=2
        )
        draw.text((self.x+20, self.y+20), self.text, fill="white", font=font_btn)

    def hit(self, tx, ty):
        return self.x <= tx <= self.x+self.w and self.y <= ty <= self.y+self.h

# ================= GENERIC MENU =================
def show_menu(title, items):
    global buttons
    buttons = []
    img, draw = new_canvas()

    draw.text((80, 10), title, fill="white", font=font_title)

    y = 80
    for text, action in items:
        btn = Button(BTN_X, y, BTN_W, BTN_H, text, action)
        buttons.append(btn)
        btn.draw(draw)
        y += BTN_H + BTN_GAP

    draw_logs(draw)
    show(img)

# ================= MAIN MENU =================
def main_menu():
    log("MAIN MENU")
    show_menu("HUMANOID", [
        ("VISION", vision_menu),
        ("AUDIO", audio_menu),
        ("MOTION", motion_menu),
        ("AI", ai_menu),
        ("SYSTEM", system_menu),
    ])

# ================= VISION =================
def vision_camera_view():
    log("OPEN CAMERA")

    try:
        cap0, cap1 = open_cameras()
    except Exception as e:
        log(str(e))
        main_menu()
        return

    while True:
        frame = read_combined_frame(cap0, cap1)
        if frame is None:
            break

        # Convert OpenCV -> PIL -> LCD
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        img = Image.fromarray(frame)

        # Resize để fit màn ST7796 (320x480 dọc)
        img = img.resize((SCREEN_W, SCREEN_H))

        show(img)

        # ----- touch để thoát -----
        if GPIO.input(17) == GPIO.LOW:
            time.sleep(0.25)  # debounce
            break

    close_cameras(cap0, cap1)
    log("EXIT CAMERA")
    vision_menu()
 
def vision_cam1_view():
    log("OPEN CAM1")

    try:
        cap = open_single_camera(0)
    except Exception as e:
        log(str(e))
        main_menu()
        return

    while True:
        frame = read_single_frame(cap, "CAM 1")
        if frame is None:
            break

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame).resize((SCREEN_W, SCREEN_H))
        show(img)

        if GPIO.input(17) == GPIO.LOW:
            time.sleep(0.25)
            break

    close_single_camera(cap)
    vision_menu()
 
def vision_cam2_view():
    log("OPEN CAM2")

    try:
        cap = open_single_camera(1)
    except Exception as e:
        log(str(e))
        main_menu()
        return

    while True:
        frame = read_single_frame(cap, "CAM 2")
        if frame is None:
            break

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame).resize((SCREEN_W, SCREEN_H))
        show(img)

        if GPIO.input(17) == GPIO.LOW:
            time.sleep(0.25)
            break

    close_single_camera(cap)
    vision_menu()
def vision_menu():
    log("VISION MENU")
    show_menu("VISION", [
        ("Camera 1", vision_cam1_view),
        ("Camera 2", vision_cam2_view),
        ("Dual View", vision_camera_view),
        ("BACK", main_menu),
    ])

# ================= AUDIO =================
def audio_menu():
    log("AUDIO MENU")
    show_menu("AUDIO", [
        ("Listen", lambda: send_cmd("AUDIO_LISTEN")),
        ("Speak Hello", lambda: send_cmd("AUDIO_SPEAK_HELLO")),
        ("Volume +", lambda: send_cmd("AUDIO_VOL_UP")),
        ("BACK", main_menu),
    ])

# ================= MOTION =================
def motion_menu():
    log("MOTION MENU")
    show_menu("MOTION", [
        ("Head Left", lambda: send_cmd("HEAD_LEFT")),
        ("Head Right", lambda: send_cmd("HEAD_RIGHT")),
        ("Arms Test", lambda: send_cmd("ARMS_TEST")),
        ("BACK", main_menu),
    ])

# ================= AI =================
def ai_menu():
    log("AI MENU")
    show_menu("AI", [
        ("Chat Mode", lambda: send_cmd("AI_CHAT")),
        ("Follow Me", lambda: send_cmd("AI_FOLLOW")),
        ("BACK", main_menu),
    ])

# ================= SYSTEM =================
def system_menu():
    log("SYSTEM MENU")
    show_menu("SYSTEM", [
        ("Status", lambda: send_cmd("SYS_STATUS")),
        ("Calibration", lambda: send_cmd("SYS_CALIB")),
        ("Shutdown", shutdown),
        ("BACK", main_menu),
    ])

def shutdown():
    log("SHUTDOWN")
    disp.clear()
    GPIO.cleanup()
    sys.exit(0)

# ================= MAIN LOOP =================
main_menu()

try:
    while True:
        time.sleep(0.1)
        if GPIO.input(17) == GPIO.LOW:
            rx, ry = touch.read_touch_data()
            x, y = map_touch(rx, ry)
            for b in buttons:
                if b.hit(x, y):
                    b.action()
                    time.sleep(0.3)
                    break

except KeyboardInterrupt:
    GPIO.cleanup()
