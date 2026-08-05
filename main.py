import sounddevice as sd
import numpy as np
import time
import threading
import yaml
import random
import cv2
import os
import getpass

with open("/home/hhl/humandroid/config.yaml", "r") as file:
    config = yaml.safe_load(file)

MIC_DEVICE = config["device"]["mic_device"]
AUDIO_DEVICE = config["device"]["output_device"]

model_path = config["location"]["model_path"]
audio_path = config["location"]["audio_path"]
prompt_path = config["location"]["prompt_path"]

DEBUG_PASSWORD = "221203"
DEBUG_SCREEN_FILE = "/home/hhl/humandroid/Debug_screen.py"

from AI_Listen import HumandroidListen
from AI_Planner import Planner
from AI_assisstant import Answer
from AI_speak import HumandroidSpeak

from Manager.Manager_Robot import RobotController
from Manager.Manager_Audio import AudioManager
from Manager.Manager_Camera import CameraManager

from Robot_lightcontrol import LED
from Robot_headcontrol import RobotHeadControl
from Robot_handcontrol import RobotArmControl
from Robot_Vision import RobotVision


# ===== Manager =====

robot = RobotController()
audio = AudioManager()
camera = CameraManager()


# ===== Led =====

led = LED(robot)
led.loading()


# ===== Vision =====

vision = RobotVision(camera=camera, head=None)


# ===== Robot =====

robotHand = RobotArmControl(robot)
robotHead = RobotHeadControl(robot=robot, vision=vision)
vision.head = robotHead


# ===== AI =====

listener = HumandroidListen()
thingker = Planner()
answer = Answer()
speaker = HumandroidSpeak()


listener.start()
camera.start()


# ==================================================
# Helper result
# ==================================================

def make_result(success, status, message, data=None):
    return {
        "success": success,
        "status": status,
        "message": message,
        "data": data
    }


def save_task_context(task_name, user_text, result):
    """
    Lưu kết quả task vào history của LLM.

    Sau đó nếu người dùng hỏi tiếp:
    - Có lấy được không?
    - Sao không lấy được?
    - Vừa làm gì?
    thì answer.get_answer() sẽ có context để trả lời.
    """

    try:
        answer.add_task_result(
            task_name=task_name,
            user_text=user_text,
            result=result
        )
    except Exception as e:
        print("[WARN] Không lưu được task context:", e)


# ==================================================
# Robot basic action
# ==================================================

def go_home():
    robotHand.home_arm("right")
    time.sleep(1)

    robotHand.home_arm("left")
    time.sleep(1)

    robotHand.home_hand("right")
    time.sleep(1)

    robotHand.home_hand("left")


def ready():
    led.happy()

    robotHand.set_arm_pose("right", "ready")
    robotHand.set_arm_pose("left", "ready")

    robotHand.set_hand_pose("right", "ready")
    robotHand.set_hand_pose("left", "ready")


# ==================================================
# Task: take object
# ==================================================

def take_obj(obj_name):
    GRAB_X_OFFSET = 3
    GRAB_Y_OFFSET = 5
    GRAB_Z_OFFSET = 0.0

    print()
    print("================================")
    print(f"[TASK] Scan and grab: {obj_name}")
    print("================================")

    # 1. Mở tay trước khi tìm vật
    robotHand.release_obj("right")
    time.sleep(0.3)

    # 2. Đưa đầu về giữa
    robotHead.center()
    time.sleep(0.5)

    # 3. Scan vật
    try:
        scan_result = robotHead.scan(
            obj_type=obj_name,
            stable_delay=1.0,
            detect_duration=0.5,
            detect_interval=0.5,
            align_times=2
        )
    except Exception as e:
        print("[SCAN ERROR]", e)

        robotHead.center()

        return make_result(
            success=False,
            status="scan_error",
            message=f"Tôi gặp lỗi khi tìm {obj_name}.",
            data={
                "obj_type": obj_name,
                "error": str(e)
            }
        )

    if scan_result is None:
        print("[RESULT] Không tìm thấy vật.")
        robotHead.center()

        return make_result(
            success=False,
            status="not_found",
            message=f"Tôi không tìm thấy {obj_name}.",
            data={
                "obj_type": obj_name,
                "scan": None,
                "ik": None
            }
        )

    print()
    print("[FOUND OBJECT]")
    print(scan_result)

    # 4. Lấy tọa độ vật
    try:
        x = float(scan_result["x"]) + GRAB_X_OFFSET
        y = float(scan_result["y"]) + GRAB_Y_OFFSET
        z = float(scan_result["z"]) + GRAB_Z_OFFSET
    except Exception as e:
        print("[POSITION ERROR]", e)

        return make_result(
            success=False,
            status="position_error",
            message=f"Tôi đã thấy {obj_name}, nhưng không đọc được tọa độ của vật.",
            data={
                "obj_type": obj_name,
                "scan": scan_result,
                "ik": None,
                "error": str(e)
            }
        )

    print()
    print("[TARGET FOR RIGHT HAND]")
    print(f"x={x:.2f}, y={y:.2f}, z={z:.2f}")

    # 5. Gắp vật bằng tay phải
    try:
        ik_result = robotHand.grab_at_xyz(
            x=x,
            y=y,
            z=z,
            approach_z_offset=-5.0,
            move_even_if_unreachable=True
        )
    except Exception as e:
        print("[IK / GRAB ERROR]", e)

        return make_result(
            success=False,
            status="ik_failed",
            message=f"Tôi đã thấy {obj_name}, nhưng chưa thể đưa tay đến vị trí đó.",
            data={
                "obj_type": obj_name,
                "target": {
                    "x": x,
                    "y": y,
                    "z": z
                },
                "scan": scan_result,
                "ik": None,
                "error": str(e)
            }
        )

    print()
    print("[GRAB DONE]")
    print("IK result:")
    print(ik_result)

    if ik_result is None:
        return make_result(
            success=False,
            status="ik_failed",
            message=f"Tôi đã thấy {obj_name}, nhưng chưa thể tính toán chuyển động để lấy vật.",
            data={
                "obj_type": obj_name,
                "target": {
                    "x": x,
                    "y": y,
                    "z": z
                },
                "scan": scan_result,
                "ik": None
            }
        )

    # Nếu grab_at_xyz trả dict có success=False
    if isinstance(ik_result, dict):
        ik_success = ik_result.get("success", True)
    else:
        ik_success = True

    if not ik_success:
        return make_result(
            success=False,
            status="unreachable",
            message=f"Tôi đã thấy {obj_name}, nhưng vật nằm ngoài tầm với.",
            data={
                "obj_type": obj_name,
                "target": {
                    "x": x,
                    "y": y,
                    "z": z
                },
                "scan": scan_result,
                "ik": ik_result
            }
        )

    return make_result(
        success=True,
        status="grabbed",
        message=f"Tôi đã cầm được {obj_name}.",
        data={
            "obj_type": obj_name,
            "target": {
                "x": x,
                "y": y,
                "z": z
            },
            "scan": scan_result,
            "ik": ik_result
        }
    )


# ==================================================
# Task: recognize
# ==================================================

def get_detection_name(det):
    """
    Lấy tên object từ detection.
    Tùy code YOLO của bạn có thể trả về:
    - class_name
    - name
    - obj
    """

    if det is None:
        return None

    return (
        det.get("class_name")
        or det.get("name")
        or det.get("obj")
    )

def recognize():
    """
    Nhận diện vật trước mặt robot bằng YOLO.

    Nhiệm vụ của hàm này:
    - Lấy frame hiện tại từ camera
    - Detect bằng YOLO
    - Bỏ qua person
    - Bỏ qua các vật quá to / quá nhỏ
    - Bỏ qua một số class không phù hợp
    - Chọn vật hợp lệ tốt nhất
    - Trả về result để gửi cho LLM viết câu trả lời tự nhiên

    Lưu ý:
    - Hàm này KHÔNG tự tạo câu trả lời tự nhiên.
    - Câu trả lời tự nhiên nên để LLM xử lý ở ngoài bằng get_recognize_response().
    """

    print()
    print("================================")
    print("[TASK] Recognize object")
    print("================================")

    # =========================
    # Config lọc object
    # =========================

    IGNORE_CLASSES = {
        # người
        "person",

        # phương tiện
        "bicycle", "car", "motorcycle", "airplane", "bus",
        "train", "truck", "boat",

        # vật ngoài đường / nền lớn
        "traffic light", "fire hydrant", "stop sign",
        "parking meter", "bench",

        # động vật
        "bird", "cat", "dog", "horse", "sheep", "cow",
        "elephant", "bear", "zebra", "giraffe",

        # nội thất lớn / vật nền
        "chair", "couch", "bed", "dining table",
        "toilet", "tv", "refrigerator",

        # thiết bị lớn trong nhà
        "oven", "sink"
    }

    PREFER_CLASSES = {
        "bottle", "cup", "fork", "knife", "spoon", "bowl",
        "banana", "apple", "sandwich", "orange", "broccoli",
        "carrot", "hot dog", "pizza", "donut", "cake",

        "remote", "keyboard", "mouse", "cell phone",
        "book", "clock", "vase", "scissors",
        "teddy bear", "hair drier", "toothbrush"
    }

    MIN_CONFIDENCE = 0.35
    MIN_AREA_RATIO = 0.002
    MAX_AREA_RATIO = 0.45

    # =========================
    # Helper trong recognize
    # =========================

    def _get_name(det):
        if det is None:
            return None

        return (
            det.get("class_name")
            or det.get("name")
            or det.get("obj")
        )

    def _get_confidence(det):
        if det is None:
            return 0.0

        return float(
            det.get("confidence", det.get("conf", 0.0))
        )

    def _get_bbox(det):
        """
        Hỗ trợ nhiều kiểu bbox:
        - x1, y1, x2, y2
        - bbox = [x1, y1, x2, y2]
        - box = [x1, y1, x2, y2]
        """

        if det is None:
            return None

        if all(k in det for k in ["x1", "y1", "x2", "y2"]):
            return (
                float(det["x1"]),
                float(det["y1"]),
                float(det["x2"]),
                float(det["y2"])
            )

        if "bbox" in det:
            bbox = det["bbox"]

            if bbox is not None and len(bbox) == 4:
                return tuple(map(float, bbox))

        if "box" in det:
            box = det["box"]

            if box is not None and len(box) == 4:
                return tuple(map(float, box))

        return None

    def _get_area_ratio(det, frame):
        """
        Tính diện tích bbox / diện tích frame.
        Ví dụ:
        - 0.05 nghĩa là object chiếm 5% ảnh
        - 0.50 nghĩa là object chiếm 50% ảnh
        """

        bbox = _get_bbox(det)

        if bbox is None:
            return 0.0

        x1, y1, x2, y2 = bbox

        frame_h, frame_w = frame.shape[:2]
        frame_area = frame_w * frame_h

        bbox_w = max(0.0, x2 - x1)
        bbox_h = max(0.0, y2 - y1)
        bbox_area = bbox_w * bbox_h

        if frame_area <= 0:
            return 0.0

        return bbox_area / frame_area

    def _is_valid_object(det, frame):
        name = _get_name(det)

        if name is None:
            return False

        if name in IGNORE_CLASSES:
            return False

        confidence = _get_confidence(det)

        if confidence < MIN_CONFIDENCE:
            return False

        area_ratio = _get_area_ratio(det, frame)

        if area_ratio < MIN_AREA_RATIO:
            return False

        if area_ratio > MAX_AREA_RATIO:
            return False

        return True

    def _object_score(det, frame):
        """
        Điểm chọn object tốt nhất.
        Ưu tiên:
        - confidence cao
        - class là vật nhỏ/có thể cầm
        - không quá to
        """

        name = _get_name(det)
        confidence = _get_confidence(det)
        area_ratio = _get_area_ratio(det, frame)

        score = confidence

        if name in PREFER_CLASSES:
            score += 0.3

        if area_ratio > 0.25:
            score -= 0.2

        return score

    # =========================
    # 1. Lấy frame hiện tại
    # =========================

    frame0, _ = camera.get_frames()

    if frame0 is None:
        print("[RECOGNIZE] Không lấy được frame.")

        return make_result(
            success=False,
            status="no_frame",
            message="Tôi chưa nhìn thấy hình ảnh.",
            data=None
        )

    # =========================
    # 2. Detect bằng YOLO
    # =========================

    try:
        detections = vision.detection(frame0)

    except Exception as e:
        print("[RECOGNIZE ERROR]", e)

        return make_result(
            success=False,
            status="vision_error",
            message="Tôi gặp lỗi khi nhận diện hình ảnh.",
            data={
                "error": str(e)
            }
        )

    print("[DETECTIONS]")
    print(detections)

    if not detections:
        return make_result(
            success=False,
            status="not_found",
            message="Tôi chưa nhận ra vật nào trước mặt.",
            data={
                "detections": []
            }
        )

    # =========================
    # 3. Lọc object hợp lệ
    # =========================

    valid_objects = []
    ignored_objects = []

    for det in detections:
        name = _get_name(det)
        confidence = _get_confidence(det)
        area_ratio = _get_area_ratio(det, frame0)

        info = {
            "name": name,
            "confidence": round(confidence, 4),
            "area_ratio": round(area_ratio, 4),
            "raw": det
        }

        if _is_valid_object(det, frame0):
            valid_objects.append(det)
        else:
            ignored_objects.append(info)

    print("[VALID OBJECTS]")
    print(valid_objects)

    print("[IGNORED OBJECTS]")
    print(ignored_objects)

    if not valid_objects:
        return make_result(
            success=False,
            status="no_valid_object",
            message="Tôi chưa thấy vật phù hợp để nhận diện.",
            data={
                "detections": detections,
                "valid_objects": [],
                "ignored_objects": ignored_objects
            }
        )

    # =========================
    # 4. Chọn object tốt nhất
    # =========================

    best_obj = max(
        valid_objects,
        key=lambda det: _object_score(det, frame0)
    )

    obj_name = _get_name(best_obj)
    confidence = _get_confidence(best_obj)
    area_ratio = _get_area_ratio(best_obj, frame0)
    bbox = _get_bbox(best_obj)

    print("[RECOGNIZED OBJECT]")
    print(best_obj)

    print("[BEST OBJECT INFO]")
    print({
        "name": obj_name,
        "confidence": confidence,
        "area_ratio": area_ratio,
        "bbox": bbox
    })

    # =========================
    # 5. Trả result cho LLM xử lý tiếp
    # =========================

    return make_result(
        success=True,
        status="recognized",
        message="Đã nhận diện được vật.",
        data={
            "object_name": obj_name,
            "confidence": confidence,
            "area_ratio": area_ratio,
            "bbox": bbox,
            "object": best_obj,
            "all_valid_objects": valid_objects,
            "ignored_objects": ignored_objects
        }
    )



# ==================================================
# Task: debug mode
# ==================================================

def _ask_debug_password(max_attempts=3):
    """
    Nhập mật khẩu trên terminal trước khi vào debug mode.

    Lưu ý: nếu main.py chạy bằng systemd không gắn terminal,
    input/getpass có thể không nhập được. Khi đó nên chạy main.py
    trong terminal khi cần mở debug mode.
    """

    for attempt in range(1, max_attempts + 1):
        print()
        print("================================")
        print("[DEBUG MODE] Yêu cầu mật khẩu")
        print(f"[DEBUG MODE] Lần thử {attempt}/{max_attempts}")
        print("================================")

        try:
            password = getpass.getpass(
                "Nhập mật khẩu debug: "
            ).strip()
        except Exception:
            password = input(
                "Nhập mật khẩu debug: "
            ).strip()

        if password == DEBUG_PASSWORD:
            return True

        print("[DEBUG MODE] Sai mật khẩu.")

        try:
            speaker.speak(
                "Mật khẩu chưa đúng.",
                speed=0.7
            )
        except Exception:
            pass

    return False


def _cleanup_before_debug():
    """
    Dừng các tài nguyên đang chạy trước khi exec sang Debug_screen.py.
    Tránh lỗi camera/mic/uart bị giữ bởi main.py.
    """

    print("[DEBUG MODE] Cleaning resources...")

    # Dừng thread camera preview nếu đang chạy
    try:
        if "cam_stop_event" in globals():
            cam_stop_event.set()
    except Exception as e:
        print("[DEBUG CLEANUP] cam_stop_event:", e)

    # Dừng action tay
    try:
        robotHand.stop_arm_action()
    except Exception as e:
        print("[DEBUG CLEANUP] robotHand:", e)

    # Đưa miệng về đóng / dừng TTS animation
    try:
        speaker.stop()
    except Exception as e:
        print("[DEBUG CLEANUP] speaker.stop:", e)

    # Dừng mic/wakeword
    try:
        listener.running = False
    except Exception:
        pass

    try:
        if hasattr(listener, "wake"):
            listener.wake.close()
    except Exception as e:
        print("[DEBUG CLEANUP] wake:", e)

    try:
        if hasattr(listener, "mic") and hasattr(listener.mic, "stop"):
            listener.mic.stop()
    except Exception as e:
        print("[DEBUG CLEANUP] mic:", e)

    # Dừng camera manager
    try:
        camera.stop()
    except Exception as e:
        print("[DEBUG CLEANUP] camera:", e)

    try:
        cv2.destroyAllWindows()
    except Exception:
        pass

    # Tắt LED nhẹ trước khi chuyển, nếu UART còn phản hồi
    try:
        led.info()
    except Exception:
        pass

    # Đóng serial chính và serial riêng của speaker nếu có
    try:
        robot.close()
    except Exception as e:
        print("[DEBUG CLEANUP] robot.close:", e)

    try:
        speaker.close()
    except Exception as e:
        print("[DEBUG CLEANUP] speaker.close:", e)


def debug_mode():
    """
    Chuyển từ main.py sang Debug_screen.py sau khi nhập đúng mật khẩu.
    Mật khẩu hiện tại: DEBUG_PASSWORD.
    """

    print()
    print("================================")
    print("[TASK] Debug mode request")
    print("================================")

    try:
        speaker.speak(
            "Vui lòng nhập mật khẩu trên terminal.",
            speed=0.7
        )
    except Exception:
        pass

    ok = _ask_debug_password(max_attempts=3)

    if not ok:
        return make_result(
            success=False,
            status="wrong_debug_password",
            message="Mật khẩu không đúng. Không vào chế độ nhà phát triển.",
            data=None
        )

    if not os.path.exists(DEBUG_SCREEN_FILE):
        return make_result(
            success=False,
            status="debug_file_not_found",
            message="Không tìm thấy file Debug_screen.py.",
            data={
                "debug_file": DEBUG_SCREEN_FILE
            }
        )

    try:
        speaker.speak(
            "Mật khẩu đúng. Đang chuyển sang chế độ nhà phát triển.",
            speed=0.7
        )
    except Exception:
        pass

    _cleanup_before_debug()

    print(f"[DEBUG MODE] Exec -> {DEBUG_SCREEN_FILE}")

    os.execvp(
        "python3",
        ["python3", DEBUG_SCREEN_FILE]
    )

    # Nếu exec lỗi thì mới chạy tới đây
    return make_result(
        success=False,
        status="exec_failed",
        message="Không thể chuyển sang chế độ nhà phát triển.",
        data={
            "debug_file": DEBUG_SCREEN_FILE
        }
    )


# ==================================================
# Speak
# ==================================================

def speak(response, speed=0.8, head_action="none"):
    tts_ready = threading.Event()

    speech_thread = threading.Thread(
        target=speaker.speak,
        args=(response,),
        kwargs={
            "speed": speed,
            "ready_event": tts_ready
        },
        daemon=True
    )

    speech_thread.start()

    tts_ready.wait()

    # Nếu planner có trả head_action thì dùng
    try:
        if head_action == "nod":
            robotHead.action_head("nod")
        elif head_action == "shake":
            robotHead.action_head("shake")
    except Exception as e:
        print("[WARN] head_action error:", e)

    robotHand.start_arm_action(
        random.choice(["right", "left"]),
        "talking"
    )

    try:
        speech_thread.join()
    finally:
        robotHand.stop_arm_action()


# ==================================================
# Main
# ==================================================
def show_camera_thread(stop_event):
    """
    Hiển thị 2 camera trên cùng 1 cửa sổ.
    Không camera.start() lại, chỉ lấy frame từ CameraManager.
    """

    print("[CAM THREAD] Start show 2 cameras")

    while not stop_event.is_set():
        frame0, frame1 = camera.get_frames()

        if frame0 is None and frame1 is None:
            time.sleep(0.01)
            continue

        # Nếu thiếu 1 camera thì tạo ảnh đen thay thế
        if frame0 is None and frame1 is not None:
            frame0 = np.zeros_like(frame1)

        if frame1 is None and frame0 is not None:
            frame1 = np.zeros_like(frame0)

        # Đảm bảo 2 frame cùng kích thước
        h0, w0 = frame0.shape[:2]
        h1, w1 = frame1.shape[:2]

        if h0 != h1 or w0 != w1:
            frame1 = cv2.resize(frame1, (w0, h0))

        # Thêm chữ phân biệt camera
        show0 = frame0.copy()
        show1 = frame1.copy()

        cv2.putText(
            show0,
            "CAM 0",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2
        )

        cv2.putText(
            show1,
            "CAM 1",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2
        )

        # Ghép ngang 2 camera
        combined = np.hstack((show0, show1))
        combined = cv2.resize(combined, (1280, 480))

        cv2.imshow("Humandroid Dual Camera", combined)

        # Nhấn q để đóng cửa sổ camera
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            print("[CAM THREAD] Quit by user")
            stop_event.set()
            break

    cv2.destroyAllWindows()
    print("[CAM THREAD] Stop show camera")
if __name__ == "__main__":
    led.success()
    time.sleep(2)
    cam_stop_event = threading.Event()

    cam_thread = threading.Thread(
        target=show_camera_thread,
        args=(cam_stop_event,),
        daemon=True
    )

    cam_thread.start()
    print("="*30)
    while True:
        led.idle()
        go_home()
        robotHead.set_angle(yaw=80, pitch=180)

        last_detect_time = 0
        detections = []

        if listener.listen_wakeword():

            robotHead.center()
            ready()
            robot.move_servo(0, 130)
            audio.start_audio("/home/hhl/humandroid/Source/Audio/heard2.wav")
            robot.move_servo(0, 80)

            while True:

                frame0, _ = camera.get_frames()

                if frame0 is None:
                    print("[WARN] frame")
                    continue

                detections = vision.detection(frame0)

                head = robotHead.look_at_human(
                    frame=frame0,
                    detections=detections
                )

                led.listen()
                text = listener.listen_stt()

                if text:
                    print(text)
                    led.think()
                    robotHead.action_head("thinking")

                    plan = thingker.get_plan(text)

                    print(plan)

                    # ==================================================
                    # Từ đây trở xuống là phần đã sửa
                    # ==================================================

                    if not isinstance(plan, dict):
                        print("[PLAN ERROR] plan ")

                        result = make_result(
                            success=False,
                            status="plan_error",
                            message="Mình không thể nghĩ được.",
                            data={
                                "text": text,
                                "plan": plan
                            }
                        )

                        save_task_context(
                            task_name="plan_error",
                            user_text=text,
                            result=result
                        )

                        speaker.speak(result["message"], speed=0.7)
                        break

                    task = plan.get("task")
                    params = plan.get("params", {})

                    if params is None:
                        params = {}

                    if task == "speak":
                        response = answer.get_answer(
                            text,
                            stream_output=True
                        )

                        if response:
                            led.info()

                            head_action = params.get(
                                "head_action",
                                "none"
                            )

                            speak(
                                response,
                                head_action=head_action
                            )
                        else:
                            led.error()
                            speaker.speak(
                                "Mình không xử lý được câu này",
                                speed=0.6
                            )

                        # Sau khi trả lời xong, tiếp tục chờ câu tiếp theo
                        ready()
                        continue

                    elif task == "take_obj":
                        obj_type = params.get("obj_type")

                        if not obj_type:
                            led.error()

                            result = make_result(
                                success=False,
                                status="missing_obj_type",
                                message="Tôi chưa biết cần lấy vật gì.",
                                data={
                                    "text": text,
                                    "plan": plan
                                }
                            )

                            save_task_context(
                                task_name="take_obj",
                                user_text=text,
                                result=result
                            )

                            speaker.speak(
                                result["message"],
                                speed=0.7
                            )

                            ready()
                            continue

                        result = take_obj(obj_type)

                        print()
                        print("[TAKE OBJ RESULT]")
                        print(result)

                        save_task_context(
                            task_name="take_obj",
                            user_text=text,
                            result=result
                        )

                        if result is None:
                            led.error()
                            speaker.speak(
                                "Tôi chưa xử lý được nhiệm vụ này.",
                                speed=0.7
                            )
                            ready()
                            continue

                        if result.get("success"):
                            led.success()
                        else:
                            led.error()

                        speaker.speak(
                            result.get(
                                "message",
                                "Tôi đã xử lý xong nhiệm vụ."
                            ),
                            speed=0.7
                        )

                        ready()
                        continue

                    elif task == "recognize":
                        result = recognize()

                        print()
                        print("[RECOGNIZE RESULT]")
                        print(result)

                        if result is None:
                            result = make_result(
                                success=False,
                                status="recognize_error",
                                message="Tôi chưa nhận diện được vật nào.",
                                data=None
                            )

                        save_task_context(
                            task_name="recognize",
                            user_text=text,
                            result=result
                        )

                        if result.get("success"):
                            led.success()
                        else:
                            led.error()

                        response = answer.get_task_response(
                            task_name="recognize",
                            user_text=text,
                            result=result,
                            stream_output=True
                        )

                        speak(
                            response,
                            speed=0.7
                        )

                        ready()
                        continue
                    elif task == "finish":
                        result = make_result(
                            success=True,
                            status="finished",
                            message="Người dùng muốn kết thúc cuộc trò chuyện.",
                            data=None
                        )

                        save_task_context(
                            task_name="finish",
                            user_text=text,
                            result=result
                        )

                        speaker.speak(
                            random.choice([
                                "Tạm biệt!",
                                "Hẹn gặp lại!",
                                "Tạm biệt nhé",
                                "Gặp sau nhé!"
                            ]),
                            speed=0.7
                        )

                        break

                    elif task == "debug_mode":
                        result = debug_mode()

                        print()
                        print("[DEBUG RESULT]")
                        print(result)

                        save_task_context(
                            task_name="debug_mode",
                            user_text=text,
                            result=result
                        )

                        if result is None:
                            speaker.speak(
                                "Không thể khởi tạo chế độ nhà phát triển.",
                                speed=0.7
                            )
                            ready()
                            continue

                        if result.get("success"):
                            led.success()
                        else:
                            led.error()

                        speaker.speak(
                            result.get(
                                "message",
                                "Đã khởi tạo chế độ nhà phát triển."
                            ),
                            speed=0.7
                        )

                        ready()
                        continue

                    else:
                        result = make_result(
                            success=False,
                            status="unknown_task",
                            message="Mình chưa hiểu nhiệm vụ này.",
                            data={
                                "task": task,
                                "params": params,
                                "plan": plan
                            }
                        )

                        save_task_context(
                            task_name="unknown_task",
                            user_text=text,
                            result=result
                        )

                        speaker.speak(
                            result["message"],
                            speed=0.7
                        )

                        break

                # Nếu không có text, kiểm tra thời gian im lặng
                else:
                    speaker.speak(
                        random.choice([
                            "Tạm biệt!",
                            "Hẹn gặp lại!",
                            "Tạm biệt nhé",
                            "Gặp sau nhé!"
                        ]),
                        speed=0.7
                    )
                    break

            answer.print_history()
            answer.clear_history()