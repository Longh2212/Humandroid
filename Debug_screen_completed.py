#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Humandroid Debug Screen
- LCD 3.5 inch ST7796 menu
- Keyboard control: W/S move, Enter select, Q back, E stop, H home all
- Lazy initialization: camera/mic/servo/AI modules are loaded only when needed

Copy file to:
    /home/hhl/humandroid/Debug_screen.py
Run:
    python3 /home/hhl/humandroid/Debug_screen.py
"""

import os
import sys
import time
import json
import math
import yaml
import signal
import importlib
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import cv2
except Exception:  # pragma: no cover - available on Pi
    cv2 = None

try:
    import numpy as np
except Exception:  # pragma: no cover - available on Pi
    np = None

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except Exception as e:
    raise RuntimeError("Pillow is required for Debug_screen.py") from e

try:
    from pynput import keyboard
except Exception:  # pragma: no cover - available on Pi desktop
    keyboard = None


# ==================================================
# PATHS
# ==================================================

PROJECT_ROOT = os.environ.get("HUMANDROID_ROOT", "/home/hhl/humandroid")
PROJECT_ROOT = os.path.abspath(PROJECT_ROOT)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

CONFIG_FILE = os.path.join(PROJECT_ROOT, "config.yaml")
SERVO_FILE = os.path.join(PROJECT_ROOT, "config_servo_angles.yaml")
POSE_FILE = os.path.join(PROJECT_ROOT, "config_pose.yaml")
ACTION_FILE = os.path.join(PROJECT_ROOT, "actions.txt")
DEBUG_LOG_FILE = os.path.join(PROJECT_ROOT, "debug.log")
FRAME_SAVE_DIR = os.path.join(PROJECT_ROOT, "debug_frames")
MAIN_FILE = os.path.join(PROJECT_ROOT, "main.py")

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


# ==================================================
# LCD INIT WITH SAFE FALLBACK
# ==================================================

class DummyDisplay:
    """Fallback display so the file can still run in terminal for syntax/debug."""

    def clear(self):
        print("[LCD] clear")

    def show_image(self, img):
        print("[LCD] show_image", img.size)

    def bl_DutyCycle(self, value):
        print(f"[LCD] backlight={value}")

    def module_exit(self):
        print("[LCD] module_exit")


def init_lcd():
    try:
        from lcd_3inch5 import st7796
        d = st7796.st7796()
        d.clear()
        return d
    except Exception as e:
        print(f"[WARN] LCD init failed, using DummyDisplay: {e}")
        return DummyDisplay()


disp = init_lcd()


# ==================================================
# SCREEN CONFIG
# ==================================================

SCREEN_W = 320
SCREEN_H = 480
BTN_X = 30
BTN_W = 260


# ==================================================
# FONT
# ==================================================

def load_font(size: int):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()


font_title = load_font(28)
font_btn = load_font(22)
font_log = load_font(15)
font_text = load_font(22)
font_small = load_font(16)


# ==================================================
# GLOBAL UI STATE
# ==================================================

buttons: List["Button"] = []
selected_idx = 0
current_title = ""
log_lines: List[str] = []

screen_mode = "menu"      # menu | head_control | preview | info | input
input_mode = False
preview_stop = False

head_pitch = 110
head_yaw = 75
HEAD_STEP = 10

HEAD_PITCH_MIN = 30
HEAD_PITCH_MAX = 180
HEAD_YAW_MIN = 10
HEAD_YAW_MAX = 130


# ==================================================
# BASIC HELPERS
# ==================================================

def clamp(value, low, high):
    return max(low, min(high, value))


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def safe_str(value: Any, limit: int = 80) -> str:
    text = str(value)
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def load_yaml_file(path: str, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if data is not None else default
    except Exception:
        return default


def save_yaml_file(path: str, data: dict):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=True, allow_unicode=True)


# ==================================================
# CANVAS
# ==================================================

def new_canvas():
    img = Image.new("RGB", (SCREEN_W, SCREEN_H), "black")
    return img, ImageDraw.Draw(img)


def show(img: Image.Image):
    try:
        img = img.rotate(180)
        disp.show_image(img)
    except Exception as e:
        print(f"[LCD] show failed: {e}")


def clear_screen():
    try:
        disp.clear()
    except Exception:
        pass


def safe_backlight_off():
    try:
        disp.bl_DutyCycle(0)
    except Exception:
        pass

    try:
        disp.module_exit()
    except Exception:
        pass


# ==================================================
# LOG
# ==================================================

def log(msg: str):
    global log_lines

    text = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print("[DEBUG]", text)

    log_lines.append(text)
    if len(log_lines) > 8:
        log_lines = log_lines[-8:]

    try:
        ensure_dir(os.path.dirname(DEBUG_LOG_FILE))
        with open(DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception:
        pass


def draw_logs(draw: ImageDraw.ImageDraw):
    y = 395
    for line in log_lines[-4:]:
        draw.text((8, y), line[-38:], fill="yellow", font=font_log)
        y += 18


# ==================================================
# TEXT DRAWING
# ==================================================

def wrap_line(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> List[str]:
    text = str(text)
    if text == "":
        return [""]

    words = text.split(" ")
    lines = []
    current = ""

    for word in words:
        candidate = word if current == "" else current + " " + word
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines or [text]


def draw_text_screen(text: str, size: int = 24, color: str = "white"):
    img, draw = new_canvas()
    font = load_font(size)
    lines = str(text).split("\n")

    rendered: List[str] = []
    for line in lines:
        rendered.extend(wrap_line(draw, line, font, SCREEN_W - 24))

    line_heights = []
    for line in rendered:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_heights.append(bbox[3] - bbox[1])

    total_h = sum(line_heights) + (len(rendered) - 1) * 8
    y = max(10, (SCREEN_H - total_h) // 2)

    for line in rendered:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((SCREEN_W - tw) // 2, y), line, fill=color, font=font)
        y += (bbox[3] - bbox[1]) + 8

    show(img)


def draw_info_screen(title: str, lines: List[Any], color: str = "white"):
    global screen_mode
    screen_mode = "info"

    img, draw = new_canvas()
    title_font = load_font(25)
    body_font = load_font(17)

    title = str(title)
    bbox = draw.textbbox((0, 0), title, font=title_font)
    tw = bbox[2] - bbox[0]
    draw.text(((SCREEN_W - tw) // 2, 18), title, fill="cyan", font=title_font)

    y = 65
    max_y = 425

    for raw_line in lines:
        for line in wrap_line(draw, str(raw_line), body_font, SCREEN_W - 28):
            if y > max_y:
                draw.text((15, y), "...", fill="yellow", font=body_font)
                break
            draw.text((15, y), line, fill=color, font=body_font)
            y += 23
        if y > max_y:
            break

    draw.text((15, 448), "Q: BACK   E: STOP   H: HOME", fill="yellow", font=font_log)
    show(img)


def draw_frame_to_lcd(frame, title="CAMERA", footer="Q: BACK"):
    if cv2 is None:
        draw_text_screen("OpenCV missing", color="red")
        return

    if frame is None:
        draw_text_screen("NO FRAME", color="red")
        return

    try:
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        elif len(frame.shape) == 3 and frame.shape[2] == 4:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
        else:
            rgb = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)

        img = Image.fromarray(rgb)
        img = ImageOps.contain(img, (SCREEN_W, SCREEN_H - 42))

        canvas = Image.new("RGB", (SCREEN_W, SCREEN_H), "black")
        x = (SCREEN_W - img.width) // 2
        y = 34
        canvas.paste(img, (x, y))

        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 0, SCREEN_W, 32), fill="black")
        draw.text((8, 7), title[:28], fill="cyan", font=font_log)
        draw.rectangle((0, SCREEN_H - 24, SCREEN_W, SCREEN_H), fill="black")
        draw.text((8, SCREEN_H - 20), footer, fill="yellow", font=font_log)
        show(canvas)

    except Exception as e:
        draw_text_screen(f"FRAME ERROR\n{e}", size=16, color="red")


# ==================================================
# BUTTON
# ==================================================

class Button:
    def __init__(self, x, y, w, h, text, action):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.text = text
        self.action = action

    def draw(self, draw, pressed=False, selected=False):
        color = "green"
        if selected:
            color = "yellow"
        if pressed:
            color = "darkgreen"

        draw.rectangle(
            (self.x, self.y, self.x + self.w, self.y + self.h),
            outline=color,
            width=4,
        )

        font = font_btn if len(self.text) <= 14 else load_font(18)
        bbox = draw.textbbox((0, 0), self.text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = self.x + (self.w - tw) // 2
        ty = self.y + (self.h - th) // 2
        draw.text((tx, ty), self.text, fill="white", font=font)


# ==================================================
# MENU DRAW
# ==================================================

def get_button_layout(num_items: int):
    if num_items <= 5:
        return 85, 58, 14
    if num_items == 6:
        return 75, 48, 8
    return 70, 42, 6


def redraw_menu(pressed_button=None):
    img, draw = new_canvas()

    bbox = draw.textbbox((0, 0), current_title, font=font_title)
    tw = bbox[2] - bbox[0]
    draw.text(((SCREEN_W - tw) // 2, 18), current_title, fill="white", font=font_title)

    for i, b in enumerate(buttons):
        b.draw(draw, pressed=(b == pressed_button), selected=(i == selected_idx))

    draw_logs(draw)
    show(img)


def show_menu(title: str, items: List[Tuple[str, Any]]):
    global buttons, selected_idx, current_title, screen_mode

    screen_mode = "menu"
    current_title = title
    selected_idx = 0
    buttons = []

    start_y, btn_h, gap = get_button_layout(len(items))
    y = start_y

    for text, action in items:
        buttons.append(Button(BTN_X, y, BTN_W, btn_h, text, action))
        y += btn_h + gap

    redraw_menu()


def animate_button(btn: Button):
    redraw_menu(pressed_button=btn)
    time.sleep(0.12)
    redraw_menu()


# ==================================================
# COMMAND RESULT
# ==================================================

def make_result(success=True, message="OK", data=None):
    return {"success": bool(success), "message": str(message), "data": data}


# ==================================================
# LAZY ROBOT CONTEXT
# ==================================================

class DebugContext:
    def __init__(self):
        self.robot = None
        self.camera = None
        self.yolo = None
        self.vision = None
        self.head = None
        self.hand = None
        self.audio = None
        self.mic = None
        self.listener = None
        self.speaker = None
        self.planner = None
        self.answer = None

    def import_class(self, module_names: List[str], class_name: str):
        last_error = None
        for module_name in module_names:
            try:
                module = importlib.import_module(module_name)
                return getattr(module, class_name)
            except Exception as e:
                last_error = e
        raise ImportError(f"Cannot import {class_name}: {last_error}")

    def get_robot(self):
        if self.robot is None:
            RobotController = self.import_class(
                ["Manager.Manager_Robot", "Manager_Robot"],
                "RobotController",
            )
            self.robot = RobotController()
        return self.robot

    def get_camera(self):
        if self.camera is None:
            CameraManager = self.import_class(
                ["Manager.Manager_Camera", "Manager_Camera"],
                "CameraManager",
            )
            self.camera = CameraManager()
            self.camera.start()
        return self.camera

    def get_yolo(self):
        if self.yolo is None:
            yoloCamera = self.import_class(["Vision.Yolo", "Yolo"], "yoloCamera")
            self.yolo = yoloCamera()
        return self.yolo

    def get_vision(self):
        if self.vision is None:
            RobotVision = self.import_class(["Robot_Vision", "Vision.Robot_Vision"], "RobotVision")
            camera = self.get_camera()
            self.vision = RobotVision(camera=camera, head=self.head)

            # If head was created before real vision, reconnect it now.
            if self.head is not None:
                try:
                    self.head.vision = self.vision
                    self.vision.head = self.head
                except Exception:
                    pass

        return self.vision

    def get_head(self):
        if self.head is None:
            RobotHeadControl = self.import_class(["Robot_headcontrol"], "RobotHeadControl")
            robot = self.get_robot()

            # Head center/nod/shake should not force camera + depth initialization.
            class MinimalVision:
                def find_human_face(self, *args, **kwargs):
                    return None

            vision = self.vision if self.vision is not None else MinimalVision()
            self.head = RobotHeadControl(vision=vision, robot=robot)

            if self.vision is not None:
                self.vision.head = self.head

        return self.head

    def get_hand(self):
        if self.hand is None:
            RobotArmControl = self.import_class(["Robot_handcontrol"], "RobotArmControl")
            robot = self.get_robot()
            self.hand = RobotArmControl(robot)
        return self.hand

    def get_audio(self):
        if self.audio is None:
            AudioManager = self.import_class(
                ["Manager.Manager_Audio", "Manager_Audio"],
                "AudioManager",
            )
            self.audio = AudioManager()
        return self.audio

    def get_mic(self):
        if self.mic is None:
            MicManager = self.import_class(
                ["Manager.Manager_Mic", "Manager_Mic"],
                "MicManager",
            )
            self.mic = MicManager()
            self.mic.start_mic()
        return self.mic

    def get_listener(self):
        if self.listener is None:
            HumandroidListen = self.import_class(["AI_Listen"], "HumandroidListen")
            self.listener = HumandroidListen()
            self.listener.start()
        return self.listener

    def get_speaker(self):
        if self.speaker is None:
            HumandroidSpeak = self.import_class(["AI_speak"], "HumandroidSpeak")
            self.speaker = HumandroidSpeak()
        return self.speaker

    def get_planner(self):
        if self.planner is None:
            Planner = self.import_class(["AI_Planner"], "Planner")
            self.planner = Planner()
        return self.planner

    def get_answer(self):
        if self.answer is None:
            Answer = self.import_class(["AI_assisstant"], "Answer")
            self.answer = Answer()
        return self.answer

    def close_all(self):
        for obj_name in ["hand", "speaker", "listener", "camera", "robot"]:
            obj = getattr(self, obj_name, None)
            if obj is None:
                continue
            try:
                if obj_name == "hand" and hasattr(obj, "stop_arm_action"):
                    obj.stop_arm_action()
                elif hasattr(obj, "stop"):
                    obj.stop()
                elif hasattr(obj, "close"):
                    obj.close()
            except Exception as e:
                print(f"[WARN] close {obj_name}: {e}")


ctx = DebugContext()


def call_safe(title: str, func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except SystemExit as e:
        return make_result(False, f"{title} failed: SystemExit {e}")
    except Exception as e:
        return make_result(False, f"{title} failed: {e}")


# ==================================================
# DEBUG COMMAND RUNNER
# ==================================================

def run_cmd(cmd: str):
    log(f"RUN -> {cmd}")
    draw_text_screen(f"RUNNING\n{cmd}", size=22, color="yellow")

    try:
        result = execute_debug_command(cmd)

        if not isinstance(result, dict):
            result = make_result(False, f"Invalid result: {result}")

        if result.get("success"):
            log(f"OK: {result.get('message')}")
            data = result.get("data")
            if data is not None:
                if not isinstance(data, list):
                    data = [data]
                draw_info_screen(cmd, data, color="white")
            else:
                draw_text_screen(result.get("message", "OK"), size=22, color="green")
                time.sleep(0.8)
                redraw_menu()
        else:
            log(f"FAIL: {result.get('message')}")
            draw_text_screen(result.get("message", "FAIL"), size=18, color="red")
            time.sleep(1.3)
            redraw_menu()

    except Exception as e:
        log(f"ERROR: {e}")
        draw_text_screen(f"ERROR\n{e}", size=18, color="red")
        time.sleep(1.5)
        redraw_menu()


# ==================================================
# EXECUTE DEBUG COMMAND
# ==================================================

def execute_debug_command(cmd: str):
    # STATUS
    if cmd == "SYS_INFO":
        return sys_info()
    if cmd == "CAMERA_STATUS":
        return camera_status()
    if cmd == "MIC_STATUS":
        return mic_status()
    if cmd == "SERVO_STATUS":
        return servo_status()

    # VISION
    if cmd == "CAMERA_VIEW":
        return camera_view()
    if cmd == "YOLO_TEST":
        return yolo_test()
    if cmd == "DEPTH_TEST":
        return depth_test()
    if cmd == "SAVE_FRAME":
        return save_frame()

    # AUDIO
    if cmd == "MIC_LEVEL":
        return mic_level()
    if cmd == "VAD_TEST":
        return vad_test()
    if cmd == "ASR_TEST":
        return asr_test()
    if cmd == "WAKE_WORD":
        return wake_word_test()
    if cmd == "TTS_TEST":
        return tts_test_input()

    # HEAD
    if cmd == "HEAD_CENTER":
        return head_center()
    if cmd == "HEAD_NOD":
        return head_action("nod")
    if cmd == "HEAD_SHAKE":
        return head_action("shake")

    # ARM
    if cmd == "RIGHT_HOME":
        return arm_home("right")
    if cmd == "LEFT_HOME":
        return arm_home("left")
    if cmd == "RIGHT_TALK":
        return arm_talk("right")

    # HAND
    if cmd == "RIGHT_OPEN":
        return hand_open("right")
    if cmd == "RIGHT_CLOSE":
        return hand_close("right")
    if cmd == "LEFT_OPEN":
        return hand_open("left")
    if cmd == "LEFT_CLOSE":
        return hand_close("left")
    if cmd == "HOME_ALL":
        return home_all()

    # AI / PLAN
    if cmd == "TEST_CHAT":
        return test_chat_input()
    if cmd == "TEST_PLAN":
        return test_plan_input()
    if cmd == "TEST_RECOGNIZE":
        return test_recognize()

    # SYSTEM
    if cmd == "STOP_ROBOT":
        return stop_robot()
    if cmd == "CLEAR_SCREEN":
        clear_screen()
        return make_result(True, "Screen cleared")
    if cmd == "START_MAIN":
        return start_main()
    if cmd == "SHUTDOWN_PI":
        return shutdown_pi()

    return make_result(False, f"Unknown CMD: {cmd}")


# ==================================================
# STATUS COMMANDS
# ==================================================

def run_shell(cmd: str) -> str:
    try:
        out = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL)
        return out.decode(errors="ignore").strip()
    except Exception:
        return "N/A"


def sys_info():
    cpu_temp = run_shell("vcgencmd measure_temp")
    cpu_clock = run_shell("vcgencmd measure_clock arm | awk -F= '{printf \"%.0f MHz\", $2/1000000}'")
    throttled = run_shell("vcgencmd get_throttled")
    ip_addr = run_shell("hostname -I | awk '{print $1}'")
    uptime = run_shell("uptime -p")
    ram = run_shell("free -m | awk 'NR==2{printf \"%s/%s MB %.0f%%\", $3,$2,$3*100/$2}'")
    disk = run_shell("df -h / | awk 'NR==2{print $3\"/\"$2\" \"$5}'")

    lines = [
        f"CPU temp : {cpu_temp}",
        f"CPU freq : {cpu_clock}",
        f"Throttle : {throttled}",
        f"RAM      : {ram}",
        f"Disk     : {disk}",
        f"IP       : {ip_addr}",
        f"Uptime   : {uptime}",
        "",
        "Mode     : DEBUG",
    ]
    return make_result(True, "System info", lines)


def camera_status():
    def _status():
        camera = ctx.get_camera()
        f0, f1 = camera.get_frames()
        lines = [
            "CameraManager: OK",
            f"Cam0 frame: {None if f0 is None else str(f0.shape)}",
            f"Cam1 frame: {None if f1 is None else str(f1.shape)}",
            f"Rotate: {getattr(camera, 'rotate', 'N/A')}",
        ]
        return make_result(True, "Camera OK", lines)

    return call_safe("Camera status", _status)


def mic_status():
    def _status():
        mic = ctx.get_mic()
        lines = [
            "MicManager: OK",
            f"Device: {getattr(mic, 'MIC_DEVICE', 'N/A')}",
            f"Mic SR: {getattr(mic, 'mic_sr', 'N/A')}",
            f"Target SR: {getattr(mic, 'target_sr', 'N/A')}",
            f"VAD frame: {getattr(mic, 'frame_ms', 'N/A')} ms",
        ]
        return make_result(True, "Mic OK", lines)

    return call_safe("Mic status", _status)


def servo_status():
    def _status():
        lines = []
        data = load_yaml_file(SERVO_FILE, default={}) or {}
        servos = data.get("servos", data)

        if servos:
            lines.append("Saved servo angles:")
            for sid in sorted(servos, key=lambda x: int(x)):
                lines.append(f"ID {sid}: {servos[sid]}")
        else:
            lines.append("No saved servo data")

        try:
            robot = ctx.get_robot()
            is_open = bool(getattr(robot, "ser", None) and robot.ser.is_open)
            lines.insert(0, f"UART: {'OPEN' if is_open else 'CLOSED'}")
        except Exception as e:
            lines.insert(0, f"UART: ERROR {e}")

        return make_result(True, "Servo status", lines)

    return call_safe("Servo status", _status)


# ==================================================
# VISION COMMANDS
# ==================================================

def camera_view(duration_sec: float = 8.0):
    global screen_mode, preview_stop

    def _view():
        global screen_mode, preview_stop
        camera = ctx.get_camera()
        screen_mode = "preview"
        preview_stop = False
        start = time.time()
        frames = 0

        while time.time() - start < duration_sec and not preview_stop:
            f0, f1 = camera.get_frames()
            frame = f0 if f0 is not None else f1
            if frame is not None:
                frames += 1
                left = max(0, int(duration_sec - (time.time() - start)))
                draw_frame_to_lcd(frame, title=f"CAMERA VIEW {left}s", footer="Q: BACK")
            time.sleep(0.03)

        screen_mode = "menu"
        redraw_menu()
        return make_result(True, "Camera view done", [f"Frames shown: {frames}"])

    return call_safe("Camera view", _view)


def save_frame():
    def _save():
        if cv2 is None:
            return make_result(False, "OpenCV missing")

        camera = ctx.get_camera()
        f0, f1 = camera.get_frames()
        ensure_dir(FRAME_SAVE_DIR)

        filename = time.strftime("frame_%Y%m%d_%H%M%S.jpg")
        path0 = os.path.join(FRAME_SAVE_DIR, "left_" + filename)
        path1 = os.path.join(FRAME_SAVE_DIR, "right_" + filename)

        saved = []
        if f0 is not None:
            cv2.imwrite(path0, f0)
            saved.append(path0)
        if f1 is not None:
            cv2.imwrite(path1, f1)
            saved.append(path1)

        if not saved:
            return make_result(False, "No frame to save")

        return make_result(True, "Frame saved", ["Saved:"] + saved)

    return call_safe("Save frame", _save)


def yolo_test():
    def _test():
        camera = ctx.get_camera()
        yolo = ctx.get_yolo()
        f0, _ = camera.get_frames()
        if f0 is None:
            return make_result(False, "No camera frame")

        detections = yolo.detect(f0)
        lines = [f"Detections: {len(detections)}"]
        for det in detections[:8]:
            name = det.get("class_name", det.get("name", "?"))
            conf = float(det.get("confidence", 0.0))
            bbox = det.get("bbox", "")
            lines.append(f"{name}: {conf:.2f}")
            lines.append(f"  {bbox}")

        if not detections:
            lines.append("No object detected")

        return make_result(True, "YOLO done", lines)

    return call_safe("YOLO test", _test)


def depth_test():
    def _test():
        vision = ctx.get_vision()
        camera = ctx.get_camera()
        f0, f1 = camera.get_frames()
        if f0 is None or f1 is None:
            return make_result(False, "Need both cameras")

        depth_map = vision.depth.compute_depth(f0, f1)
        h, w = depth_map.shape[:2]
        cx, cy = w // 2, h // 2
        center_depth = vision.depth.get_depth(cx, cy, depth_map)

        valid = depth_map[depth_map > 0]
        if valid.size > 0:
            mean_depth = float(valid.mean())
            min_depth = float(valid.min())
            max_depth = float(valid.max())
        else:
            mean_depth = min_depth = max_depth = 0.0

        return make_result(
            True,
            "Depth done",
            [
                f"Map: {w}x{h}",
                f"Center depth: {center_depth:.3f} m",
                f"Valid pixels: {valid.size}",
                f"Mean: {mean_depth:.3f} m",
                f"Min : {min_depth:.3f} m",
                f"Max : {max_depth:.3f} m",
            ],
        )

    return call_safe("Depth test", _test)


def test_recognize():
    def _test():
        camera = ctx.get_camera()
        yolo = ctx.get_yolo()
        f0, _ = camera.get_frames()
        if f0 is None:
            return make_result(False, "No camera frame")

        detections = yolo.detect(f0)
        ignored = {"person", "chair", "couch", "bed", "dining table", "tv"}
        candidates = []
        for det in detections:
            name = det.get("class_name")
            conf = float(det.get("confidence", 0.0))
            if name in ignored:
                continue
            candidates.append((conf, name, det))

        if not candidates:
            return make_result(
                True,
                "Recognize result",
                [
                    "No valid object",
                    f"Raw detections: {len(detections)}",
                ],
            )

        candidates.sort(reverse=True, key=lambda x: x[0])
        conf, name, det = candidates[0]
        return make_result(
            True,
            "Recognized",
            [
                f"Best: {name}",
                f"Confidence: {conf:.2f}",
                f"BBox: {det.get('bbox')}",
                "",
                "Natural answer:",
                f"Tôi thấy đây có vẻ là {name}.",
            ],
        )

    return call_safe("Recognize", _test)


# ==================================================
# AUDIO COMMANDS
# ==================================================

def mic_level(duration_sec: float = 1.0):
    def _level():
        if np is None:
            return make_result(False, "numpy missing")

        mic = ctx.get_mic()
        chunks = []
        start = time.time()
        while time.time() - start < duration_sec:
            data = mic.read_16k(getattr(mic, "mic_frame", 1440))
            chunks.append(data)

        audio = np.concatenate(chunks) if chunks else np.array([], dtype=np.float32)
        if audio.size == 0:
            return make_result(False, "No audio data")

        rms = float(np.sqrt(np.mean(audio ** 2)))
        peak = float(np.max(np.abs(audio)))
        db = 20 * math.log10(max(rms, 1e-9))

        return make_result(
            True,
            "Mic level",
            [
                f"RMS : {rms:.5f}",
                f"Peak: {peak:.5f}",
                f"dBFS: {db:.1f}",
                "",
                "Tip: speak near mic and retry",
            ],
        )

    return call_safe("Mic level", _level)


def vad_test():
    def _vad():
        if np is None:
            return make_result(False, "numpy missing")

        mic = ctx.get_mic()
        draw_text_screen("VAD TEST\nSpeak now", size=22, color="cyan")
        audio = mic.record_until_silence()

        if audio is None or len(audio) == 0:
            return make_result(False, "No speech detected")

        dur = len(audio) / float(getattr(mic, "target_sr", 16000))
        rms = float(np.sqrt(np.mean(audio ** 2)))
        return make_result(True, "Speech detected", [f"Duration: {dur:.2f}s", f"RMS: {rms:.5f}"])

    return call_safe("VAD test", _vad)


def asr_test():
    def _asr():
        listener = ctx.get_listener()
        draw_text_screen("ASR TEST\nSpeak now", size=22, color="cyan")
        text = listener.listen_stt()
        if not text:
            return make_result(False, "No text recognized")
        return make_result(True, "ASR done", ["Text:", text])

    return call_safe("ASR test", _asr)


def wake_word_test():
    def _wake():
        listener = ctx.get_listener()
        draw_text_screen("WAKE WORD\nSay: Hey Robot", size=21, color="cyan")
        detected = listener.listen_wakeword()
        return make_result(bool(detected), "Wake word detected" if detected else "Wake word failed")

    return call_safe("Wake word", _wake)


def tts_test_input():
    global input_mode
    input_mode = True
    draw_text_screen("TTS TEST\nType in terminal", size=22, color="cyan")

    try:
        text = input("\n[TTS TEST] Nhập câu robot sẽ nói: ").strip()
        if not text:
            return make_result(False, "Empty text")

        log(f"TTS TEXT: {text}")
        speaker = ctx.get_speaker()
        speaker.speak(text, speed=0.8)

        return make_result(True, "TTS done", ["Text:", text])
    except Exception as e:
        return make_result(False, str(e))
    finally:
        input_mode = False


# ==================================================
# AI COMMANDS
# ==================================================

def test_chat_input():
    global input_mode
    input_mode = True
    draw_text_screen("TEST CHAT\nType in terminal", size=21, color="cyan")

    try:
        text = input("\n[TEST CHAT] Nhập câu hỏi: ").strip()
        if not text:
            return make_result(False, "Empty input")

        answer = ctx.get_answer()
        response = answer.get_answer(text, stream_output=False)
        return make_result(True, "Chat done", ["Input:", text, "", "Answer:", response])
    except Exception as e:
        return make_result(False, str(e))
    finally:
        input_mode = False


def test_plan_input():
    global input_mode
    input_mode = True
    draw_text_screen("TEST PLAN\nType in terminal", size=21, color="cyan")

    try:
        text = input("\n[TEST PLAN] Nhập lệnh robot: ").strip()
        if not text:
            return make_result(False, "Empty input")

        planner = ctx.get_planner()
        plan = planner.get_plan(text)
        pretty = json.dumps(plan, ensure_ascii=False, indent=2)
        return make_result(True, "Plan done", ["Input:", text, "", "Plan:"] + pretty.splitlines())
    except Exception as e:
        return make_result(False, str(e))
    finally:
        input_mode = False


# ==================================================
# HEAD CONTROL
# ==================================================

def head_center():
    global head_pitch, head_yaw

    def _center():
        global head_pitch, head_yaw
        head_pitch = 110
        head_yaw = 75
        head = ctx.get_head()
        head.center()
        return make_result(True, "Head centered", ["HEAD CENTER", "", f"Pitch: {head_pitch}", f"Yaw: {head_yaw}"])

    return call_safe("Head center", _center)


def head_action(action_name: str):
    def _action():
        head = ctx.get_head()
        head.action_head(action_name)
        return make_result(True, f"Head {action_name}", [f"Action: {action_name}"])

    return call_safe(f"Head {action_name}", _action)


def draw_head_control_screen():
    img, draw = new_canvas()
    title = "HEAD CONTROL"
    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    draw.text(((SCREEN_W - tw) // 2, 20), title, fill="white", font=font_title)

    lines = [
        f"Pitch: {head_pitch}",
        f"Yaw:   {head_yaw}",
        "",
        "W: PITCH +",
        "S: PITCH -",
        "A: YAW +",
        "D: YAW -",
        "",
        "STEP: 10 deg",
        "Q: BACK",
    ]

    y = 88
    for line in lines:
        draw.text(
            (42, y),
            line,
            fill="cyan" if "Pitch" in line or "Yaw" in line else "white",
            font=font_text,
        )
        y += 31

    show(img)


def enter_head_control():
    global screen_mode
    screen_mode = "head_control"
    log("HEAD CONTROL MODE")
    draw_head_control_screen()


def move_head_control(key_char: str):
    global head_pitch, head_yaw

    c = key_char.lower()
    if c == "w":
        head_pitch += HEAD_STEP
    elif c == "s":
        head_pitch -= HEAD_STEP
    elif c == "a":
        head_yaw += HEAD_STEP
    elif c == "d":
        head_yaw -= HEAD_STEP

    head_pitch = clamp(head_pitch, HEAD_PITCH_MIN, HEAD_PITCH_MAX)
    head_yaw = clamp(head_yaw, HEAD_YAW_MIN, HEAD_YAW_MAX)

    log(f"HEAD P:{head_pitch} Y:{head_yaw}")

    try:
        head = ctx.get_head()
        head.set_angle(yaw=head_yaw, pitch=head_pitch)
    except Exception as e:
        log(f"HEAD MOVE ERROR: {e}")

    draw_head_control_screen()


# ==================================================
# ARM / HAND COMMANDS
# ==================================================

def arm_home(side: str):
    def _home():
        hand = ctx.get_hand()
        hand.home_arm(side)
        return make_result(True, f"{side} arm home", [f"{side.upper()} ARM HOME"])

    return call_safe(f"{side} arm home", _home)


def arm_talk(side: str):
    def _talk():
        hand = ctx.get_hand()
        hand.start_arm_action(side, "talking", duration=3)
        time.sleep(3.2)
        hand.stop_arm_action()
        return make_result(True, f"{side} arm talk", [f"{side.upper()} TALK 3s"])

    return call_safe(f"{side} arm talk", _talk)


def hand_open(side: str):
    def _open():
        hand = ctx.get_hand()
        hand.release_obj(side)
        return make_result(True, f"{side} hand opened", [f"{side.upper()} HAND OPEN"])

    return call_safe(f"{side} hand open", _open)


def hand_close(side: str):
    def _close():
        hand = ctx.get_hand()
        hand.grab_obj(side)
        return make_result(True, f"{side} hand closed", [f"{side.upper()} HAND CLOSE"])

    return call_safe(f"{side} hand close", _close)


def home_all():
    def _home_all():
        errors = []

        try:
            ctx.get_head().center()
        except Exception as e:
            errors.append(f"Head: {e}")

        try:
            hand = ctx.get_hand()
            hand.home_arm("right")
            hand.home_arm("left")
            hand.home_hand("right")
            hand.home_hand("left")
        except Exception as e:
            errors.append(f"Hand: {e}")

        if errors:
            return make_result(False, "Home all partial fail", errors)

        return make_result(True, "Home all done", ["Head center", "Right arm home", "Left arm home", "Hands open/home"])

    return call_safe("Home all", _home_all)


# ==================================================
# ACTION TEST
# ==================================================

def read_actions():
    if not os.path.exists(ACTION_FILE):
        return []

    actions = []
    try:
        with open(ACTION_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                actions.append(line)
    except Exception:
        pass

    return actions


def action_test_menu():
    log("ACTION TEST MENU")
    actions = read_actions()
    items = []

    if not actions:
        items.append(("NO ACTION FILE", lambda: draw_info_screen(
            "ACTION TEST",
            ["No action file found", "", ACTION_FILE, "", "Create actions.txt", "then press REFRESH"],
            color="red",
        )))
    else:
        for action_name in actions[:4]:
            items.append((action_name[:18], lambda name=action_name: run_action(name)))

    items.append(("REFRESH", action_test_menu))
    items.append(("BACK", motion_menu))
    show_menu("ACTION TEST", items)


def run_action(action_name: str):
    log(f"ACTION -> {action_name}")
    draw_text_screen(f"ACTION\n{action_name}", size=22, color="yellow")

    def _run():
        hand = ctx.get_hand()
        hand.start_arm_action("right", action_name, duration=3)
        time.sleep(3.2)
        hand.stop_arm_action()
        return make_result(True, "Action done", ["Action selected:", action_name, "", "Side: right"])

    result = call_safe("Run action", _run)
    if result.get("success"):
        draw_info_screen("ACTION TEST", result.get("data") or [result.get("message")])
    else:
        draw_text_screen(result.get("message"), size=18, color="red")
        time.sleep(1)
        redraw_menu()


# ==================================================
# SYSTEM COMMANDS
# ==================================================

def stop_robot():
    log("STOP ROBOT")
    messages = []

    try:
        if ctx.hand is not None:
            ctx.hand.stop_arm_action()
        messages.append("Arm stopped")
    except Exception as e:
        messages.append(f"Arm stop error: {e}")

    try:
        if ctx.speaker is not None:
            ctx.speaker.stop()
        messages.append("Speaker stopped")
    except Exception as e:
        messages.append(f"Speaker stop error: {e}")

    try:
        if ctx.robot is not None:
            # stop mouth servo to closed angle if possible
            ctx.robot.move_servo(0, 80)
        messages.append("Mouth closed")
    except Exception as e:
        messages.append(f"Mouth close error: {e}")

    return make_result(True, "Robot stopped", messages)


def start_main():
    log("START MAIN")

    if not os.path.exists(MAIN_FILE):
        return make_result(False, f"main.py not found: {MAIN_FILE}")

    draw_text_screen("START MAIN\nLCD OFF", size=22, color="green")
    time.sleep(1)
    clear_screen()
    safe_backlight_off()
    ctx.close_all()

    try:
        os.execvp("python3", ["python3", MAIN_FILE])
    except Exception as e:
        return make_result(False, f"Start main failed: {e}")


def shutdown_pi():
    draw_text_screen("SHUTDOWN PI", size=26, color="red")
    log("SHUTDOWN PI")
    time.sleep(1)
    clear_screen()
    safe_backlight_off()
    os.system("sudo shutdown -h now")
    return make_result(True, "Shutdown")


# ==================================================
# MENUS
# ==================================================

def main_menu():
    log("MAIN MENU")
    show_menu("DEBUG MODE", [
        ("STATUS", status_menu),
        ("VISION", vision_menu),
        ("AUDIO", audio_menu),
        ("MOTION", motion_menu),
        ("AI PLAN", ai_plan_menu),
        ("SYSTEM", system_menu),
    ])


def status_menu():
    log("STATUS MENU")
    show_menu("STATUS", [
        ("SYS INFO", lambda: run_cmd("SYS_INFO")),
        ("CAMERA STATUS", lambda: run_cmd("CAMERA_STATUS")),
        ("MIC STATUS", lambda: run_cmd("MIC_STATUS")),
        ("SERVO STATUS", lambda: run_cmd("SERVO_STATUS")),
        ("BACK", main_menu),
    ])


def vision_menu():
    log("VISION MENU")
    show_menu("VISION", [
        ("CAMERA VIEW", lambda: run_cmd("CAMERA_VIEW")),
        ("YOLO TEST", lambda: run_cmd("YOLO_TEST")),
        ("DEPTH TEST", lambda: run_cmd("DEPTH_TEST")),
        ("SAVE FRAME", lambda: run_cmd("SAVE_FRAME")),
        ("BACK", main_menu),
    ])


def audio_menu():
    log("AUDIO MENU")
    show_menu("AUDIO", [
        ("MIC LEVEL", lambda: run_cmd("MIC_LEVEL")),
        ("VAD TEST", lambda: run_cmd("VAD_TEST")),
        ("ASR TEST", lambda: run_cmd("ASR_TEST")),
        ("WAKE WORD", lambda: run_cmd("WAKE_WORD")),
        ("TTS TEST", lambda: run_cmd("TTS_TEST")),
        ("BACK", main_menu),
    ])


def motion_menu():
    log("MOTION MENU")
    show_menu("MOTION", [
        ("HEAD TEST", head_test_menu),
        ("ARM TEST", arm_test_menu),
        ("HAND TEST", hand_test_menu),
        ("ACTION TEST", action_test_menu),
        ("HOME ALL", lambda: run_cmd("HOME_ALL")),
        ("BACK", main_menu),
    ])


def head_test_menu():
    log("HEAD TEST MENU")
    show_menu("HEAD TEST", [
        ("CENTER", lambda: run_cmd("HEAD_CENTER")),
        ("CONTROL", enter_head_control),
        ("NOD", lambda: run_cmd("HEAD_NOD")),
        ("SHAKE", lambda: run_cmd("HEAD_SHAKE")),
        ("BACK", motion_menu),
    ])


def arm_test_menu():
    log("ARM TEST MENU")
    show_menu("ARM TEST", [
        ("RIGHT HOME", lambda: run_cmd("RIGHT_HOME")),
        ("LEFT HOME", lambda: run_cmd("LEFT_HOME")),
        ("RIGHT TALK", lambda: run_cmd("RIGHT_TALK")),
        ("BACK", motion_menu),
    ])


def hand_test_menu():
    log("HAND TEST MENU")
    show_menu("HAND TEST", [
        ("RIGHT OPEN", lambda: run_cmd("RIGHT_OPEN")),
        ("RIGHT CLOSE", lambda: run_cmd("RIGHT_CLOSE")),
        ("LEFT OPEN", lambda: run_cmd("LEFT_OPEN")),
        ("LEFT CLOSE", lambda: run_cmd("LEFT_CLOSE")),
        ("BACK", motion_menu),
    ])


def ai_plan_menu():
    log("AI PLAN MENU")
    show_menu("AI PLAN", [
        ("TEST CHAT", lambda: run_cmd("TEST_CHAT")),
        ("TEST PLAN", lambda: run_cmd("TEST_PLAN")),
        ("RECOGNIZE", lambda: run_cmd("TEST_RECOGNIZE")),
        ("BACK", main_menu),
    ])


def system_menu():
    log("SYSTEM MENU")
    show_menu("SYSTEM", [
        ("START MAIN", lambda: run_cmd("START_MAIN")),
        ("STOP ROBOT", lambda: run_cmd("STOP_ROBOT")),
        ("CLEAR SCREEN", lambda: run_cmd("CLEAR_SCREEN")),
        ("SHUTDOWN PI", lambda: run_cmd("SHUTDOWN_PI")),
        ("BACK", main_menu),
    ])


# ==================================================
# KEYBOARD CONTROL
# ==================================================

def on_press(key):
    global selected_idx, screen_mode, preview_stop

    if input_mode:
        return

    try:
        c = key.char.lower()

        # CAMERA PREVIEW MODE
        if screen_mode == "preview":
            if c == "q":
                preview_stop = True
            elif c == "e":
                preview_stop = True
                run_cmd("STOP_ROBOT")
            return

        # INFO SCREEN
        if screen_mode == "info":
            if c == "q":
                main_menu()
            elif c == "e":
                run_cmd("STOP_ROBOT")
            elif c == "h":
                run_cmd("HOME_ALL")
            return

        # HEAD CONTROL MODE
        if screen_mode == "head_control":
            if c in ["w", "a", "s", "d"]:
                move_head_control(c)
            elif c == "q":
                head_test_menu()
            elif c == "e":
                run_cmd("STOP_ROBOT")
            return

        # MENU MODE
        if screen_mode == "menu":
            if c == "w":
                if buttons:
                    selected_idx = (selected_idx - 1) % len(buttons)
                    redraw_menu()
            elif c == "s":
                if buttons:
                    selected_idx = (selected_idx + 1) % len(buttons)
                    redraw_menu()
            elif c == "q":
                main_menu()
            elif c == "e":
                run_cmd("STOP_ROBOT")
            elif c == "h":
                run_cmd("HOME_ALL")

    except AttributeError:
        if key == keyboard.Key.enter and screen_mode == "menu":
            if not buttons:
                return
            btn = buttons[selected_idx]
            animate_button(btn)
            btn.action()


# ==================================================
# TERMINAL FALLBACK CONTROL
# ==================================================

def terminal_control_loop():
    """Fallback if pynput is not available."""
    main_menu()
    print("[KEYBOARD] pynput unavailable. Terminal fallback:")
    print("  w/s: move, enter: select, q: main/back, e: stop, h: home, exit: quit")

    global selected_idx
    while True:
        cmd = input("debug> ").strip().lower()
        if cmd in ["exit", "quit"]:
            break
        if cmd == "w" and buttons:
            selected_idx = (selected_idx - 1) % len(buttons)
            redraw_menu()
        elif cmd == "s" and buttons:
            selected_idx = (selected_idx + 1) % len(buttons)
            redraw_menu()
        elif cmd == "":
            if buttons:
                btn = buttons[selected_idx]
                animate_button(btn)
                btn.action()
        elif cmd == "q":
            main_menu()
        elif cmd == "e":
            run_cmd("STOP_ROBOT")
        elif cmd == "h":
            run_cmd("HOME_ALL")


# ==================================================
# START
# ==================================================

def handle_exit(signum=None, frame=None):
    try:
        clear_screen()
        ctx.close_all()
    finally:
        sys.exit(0)


def main():
    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)

    main_menu()

    if keyboard is None:
        terminal_control_loop()
        return

    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        handle_exit()


if __name__ == "__main__":
    main()
