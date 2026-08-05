from time import sleep
from Manager.Manager_Robot import RobotController
from Manager.Manager_Camera import CameraManager
from Robot_Vision import RobotVision
import random
import cv2
import time
import yaml

class RobotHeadControl:
    """Head & neck movement"""
    # =========================
    # Servo config
    # =========================
    PITCH_ID = 1
    YAW_ID = 2

    PITCH_MIN = 30
    PITCH_MAX = 180

    YAW_MIN = 10
    YAW_MAX = 130

    CENTER_PITCH = 110
    CENTER_YAW = 75

    # scan config
    SCAN_YAW_STEP = 20
    SCAN_PITCH_STEP = 40
    SCAN_DELAY = 1

    def __init__(
        self,
        vision,
        robot,
    ):
        self.robot = robot
        self.vision = vision
        self.current_yaw = self.CENTER_YAW
        self.current_pitch = self.CENTER_PITCH
        self.motion_file = "config_servo_angles.yaml"
        self.current_angles = {}
        
        with open(self.motion_file, "r") as f:
            self.yaml_data = yaml.safe_load(f) or {}

    # =========================
    # Low-level
    # =========================
    def _save_current_angle(self, servo_id, angle):

        if "servos" not in self.yaml_data:
            self.yaml_data["servos"] = {}

        self.yaml_data["servos"][int(servo_id)] = int(angle)

        with open(self.motion_file, "w") as f:
            yaml.safe_dump(
                self.yaml_data,
                f,
                sort_keys=True
            )
    def _move_servo(self, servo_id: int, angle: float):
        angle = int(round(angle))

        result = self.robot.move_servo(
            servo_id,
            angle
        )

        self._save_current_angle(
            servo_id,
            angle
        )

        return result

    # =========================
    # Main API
    # =========================
    def set_angle(
        self,
        yaw: float,
        pitch: float
    ):
        yaw = max(
            self.YAW_MIN,
            min(self.YAW_MAX, yaw)
        )

        pitch = max(
            self.PITCH_MIN,
            min(self.PITCH_MAX, pitch)
        )

        self._move_servo(
            self.PITCH_ID,
            pitch
        )

        self._move_servo(
            self.YAW_ID,
            yaw
        )
        self.current_yaw = yaw
        self.current_pitch = pitch

    def center(self):
        return self.set_angle(
            yaw=self.CENTER_YAW,
            pitch=self.CENTER_PITCH
        )

    # =========================
    # Scan object
    # =========================
    def action_head(self,action: str):
        """
        Head actions
        action:
        - nod
        - shake
        - thinking
        - home
        """

        action = action.lower()

        yaw_c = self.CENTER_YAW
        pitch_c = self.CENTER_PITCH


        if action == "nod":
            for _ in range(2):
                self.set_angle(
                    yaw=yaw_c,
                    pitch=pitch_c + 30
                )
                sleep(0.35)
                
                self.set_angle(
                    yaw=yaw_c,
                    pitch=pitch_c - 20
                )
                sleep(0.35)

            self.center()
            return True

            
        elif action == "shake":

            for _ in range(2):

                self.set_angle(
                    yaw=yaw_c - 25,
                    pitch=pitch_c
                )
                sleep(0.3)

                self.set_angle(
                    yaw=yaw_c + 25,
                    pitch=pitch_c
                )
                sleep(0.3)

            self.center()
            return True

        elif action == "thinking":

            # safe range
            YAW_MIN, YAW_MAX = 10, 130
            PITCH_MIN, PITCH_MAX = 30, 180

            # thinking thường ngẩng nhẹ
            thinking_pitch_range = (60, 80)

            # số động tác ngẫu nhiên
            n_moves = random.randint(2, 4)

            # bias nhìn sang 1 bên
            direction = random.choice([-1, 1])

            for _ in range(n_moves):

                # yaw offset nhẹ, không quá mạnh
                yaw_target = yaw_c + direction * random.randint(15, 30)

                # ngẩng lên (pitch nhỏ hơn center=110)
                pitch_target = random.randint(*thinking_pitch_range)

                # clamp range servo
                yaw_target = max(YAW_MIN, min(YAW_MAX, yaw_target))
                pitch_target = max(PITCH_MIN, min(PITCH_MAX, pitch_target))

                self.set_angle(
                    yaw=yaw_target,
                    pitch=pitch_target
                )

                # timing không đều
                sleep(random.uniform(0.25, 0.8))

                # micro adjustment
                if random.random() < 0.45:

                    micro_yaw = yaw_target + random.randint(-3, 3)
                    micro_pitch = pitch_target + random.randint(-2, 2)

                    micro_yaw = max(YAW_MIN, min(YAW_MAX, micro_yaw))
                    micro_pitch = max(PITCH_MIN, min(PITCH_MAX, micro_pitch))

                    self.set_angle(
                        yaw=micro_yaw,
                        pitch=micro_pitch
                    )

                    sleep(random.uniform(0.12, 0.35))

            # đôi lúc nhìn lên cao hơn kiểu "hmmm..."
            if random.random() < 0.2:
                self.set_angle(
                    yaw=max(YAW_MIN, min(YAW_MAX,
                        yaw_c + random.randint(-10, 10))),
                    pitch=random.randint(60, 80)
                )

                sleep(random.uniform(0.3, 0.6))

            # pause nhẹ trước khi reset
            sleep(random.uniform(0.1, 0.4))

            self.center()
            return True
        else:
            raise ValueError(
                f"Unknown action: {action}"
            )
        
    def look_at_human(
        self,
        frame,
        detections,
        dead_zone=40,
        yaw_gain=12,
        pitch_gain=10,
        
    ):
        if detections is None:
            return None

        face = self.vision.find_human_face(frame=frame, detections=detections)

        if face is None:
            return None

        h, w = frame.shape[:2]

        center_x = w / 2
        center_y = h / 2

        error_x = face["x"] - center_x
        error_y = face["y"] - center_y

        norm_x = error_x / center_x
        norm_y = error_y / center_y

        yaw = self.current_yaw
        pitch = self.current_pitch

        if abs(error_x) > dead_zone:
            yaw = yaw + norm_x * yaw_gain

        if abs(error_y) > dead_zone:
            pitch = pitch + norm_y * pitch_gain

        self.set_angle(
            yaw=yaw,
            pitch=pitch
        )

        return {
            "face_x": float(face["x"]),
            "face_y": float(face["y"]),
            "error_x": float(error_x),
            "error_y": float(error_y),
            "yaw": float(self.current_yaw),
            "pitch": float(self.current_pitch),
            "confidence": float(face["confidence"])
        }
                
    def look_at_object_pixel(
        self,
        pixel_x,
        pixel_y,
        frame_width=640,
        frame_height=480,
        dead_zone=30,
        yaw_gain=12,
        pitch_gain=10
    ):
        center_x = frame_width / 2
        center_y = frame_height / 2

        error_x = pixel_x - center_x
        error_y = pixel_y - center_y

        norm_x = error_x / center_x
        norm_y = error_y / center_y

        yaw = self.current_yaw
        pitch = self.current_pitch

        if abs(error_x) > dead_zone:
            yaw = yaw + norm_x * yaw_gain

        if abs(error_y) > dead_zone:
            pitch = pitch + norm_y * pitch_gain

        self.set_angle(
            yaw=yaw,
            pitch=pitch
        )

        return {
            "error_x": float(error_x),
            "error_y": float(error_y),
            "yaw": float(self.current_yaw),
            "pitch": float(self.current_pitch)
        }
        
    def scan(
        self,
        obj_type: str,
        stable_delay=0.5,
        detect_duration=1.0,
        detect_interval=0.15,
        align_times=2
    ) -> dict | None:

        pitch_angles = range(
            self.PITCH_MAX,
            self.PITCH_MIN + 20,
            -self.SCAN_PITCH_STEP
        )

        reverse = False

        for pitch in pitch_angles:

            yaw_angles = list(range(
                self.YAW_MIN + 20,
                self.YAW_MAX - 10,
                self.SCAN_YAW_STEP
            ))

            if reverse:
                yaw_angles.reverse()

            for yaw in yaw_angles:

                self.set_angle(
                    yaw=yaw,
                    pitch=pitch
                )

                print(f"[SCAN] Move to yaw={yaw}, pitch={pitch}")

                sleep(stable_delay)

                start_time = time.time()

                while time.time() - start_time < detect_duration:

                    obj_xyz = self.vision.get_obj_position(obj_type)

                    if obj_xyz is not None:
                        print("[FOUND]", obj_xyz)

                        # =========================
                        # Align head to object
                        # =========================
                        for _ in range(align_times):

                            pixel_x = obj_xyz["pixel_x"]
                            pixel_y = obj_xyz["pixel_y"]

                            self.look_at_object_pixel(
                                pixel_x=pixel_x,
                                pixel_y=pixel_y,
                                frame_width=640,
                                frame_height=480
                            )

                            sleep(0.5)

                            new_obj_xyz = self.vision.get_obj_position(obj_type)

                            if new_obj_xyz is not None:
                                obj_xyz = new_obj_xyz

                        print("[ALIGNED]", obj_xyz)

                        return {
                            "found": True,
                            "obj": obj_xyz["obj"],

                            "x": obj_xyz["x"],
                            "y": obj_xyz["y"],
                            "z": obj_xyz["z"],

                            "current_x": obj_xyz["current_x"],
                            "current_y": obj_xyz["current_y"],
                            "current_z": obj_xyz["current_z"],

                            "pixel_x": obj_xyz["pixel_x"],
                            "pixel_y": obj_xyz["pixel_y"],
                            "depth_raw": obj_xyz["depth_raw"],

                            "scan_yaw": self.current_yaw,
                            "scan_pitch": self.current_pitch,

                            "pitch_deg": obj_xyz["pitch_deg"],
                            "yaw_deg": obj_xyz["yaw_deg"],

                            "servo1": obj_xyz["servo1"],
                            "servo2": obj_xyz["servo2"]
                        }

                    sleep(detect_interval)

            reverse = not reverse

        self.center()
        return None
    
if __name__ == "__main__":

    import threading

    from Manager.Manager_Robot import RobotController
    from Manager.Manager_Camera import CameraManager
    from Robot_Vision import RobotVision

    running = True

    def show_camera(camera):
        global running

        while running:
            frame_left, frame_right = camera.get_frames()

            if frame_left is not None:
                cv2.imshow("Left Camera", frame_left)

            if frame_right is not None:
                cv2.imshow("Right Camera", frame_right)

            key = cv2.waitKey(1) & 0xFF

            if key == 27:  # ESC
                running = False
                break

        cv2.destroyAllWindows()

    # =====================
    # Init
    # =====================
    robot = RobotController()
    camera = CameraManager()
    camera.start()
    vision = RobotVision(
        camera=camera
    )

    head = RobotHeadControl(
        vision=vision,
        robot=robot
    )

    vision.head = head

    print("=== Robot Head Scan Test ===")
    print("ESC:  camera")


    cam_thread = threading.Thread(
        target=show_camera,
        args=(camera,),
        daemon=True
    )
    cam_thread.start()

    try:
        head.center()

        while running:
            obj_name = input(
                "\nObject name (bottle/cup/person/q): "
            ).strip()

            if obj_name.lower() == "q":
                running = False
                break

            start = time.time()

            result = head.scan(
                obj_type=obj_name,
                stable_delay=1.0,
                detect_duration=1.0,
                detect_interval=0.15,
                align_times=2
            )

            dt = time.time() - start

            print("\n===================")

            if result is None:
                print("NOT FOUND")
            else:
                print("RESULT:")
                print(result)

            print(f"Time: {dt:.2f}s")
            print("===================\n")

    except KeyboardInterrupt:
        print("\nStopped.")

    finally:
        running = False

        try:
            head.center()
        except Exception:
            pass

        if hasattr(camera, "release"):
            camera.release()

        cv2.destroyAllWindows()