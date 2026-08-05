from Manager.Manager_Robot import RobotController
from time import sleep
import yaml
import threading
import random
import time

from IK import InMoovRightArmDH


POSE_FILE = "/home/hhl/humandroid/config_pose.yaml"
MOTION_FILE = "config_servo_angles.yaml"


with open(POSE_FILE, "r") as file:
    pose = yaml.safe_load(file)


class RobotArmControl:
    """Control robot arms/hands + IK right arm."""

    SERVO_CONFIG = {
        # Right arm
        3: {"home": 150, "min": 120, "max": 150},
        4: {"home": 80, "min": 0, "max": 150},
        5: {"home": 80, "min": 0, "max": 150},
        6: {"home": 170, "min": 110, "max": 180},
        7: {"home": 90, "min": 0, "max": 180},

        # Right hand
        8: {"home": 180, "min": 0, "max": 180},
        9: {"home": 180, "min": 0, "max": 180},
        10: {"home": 160, "min": 0, "max": 160},
        11: {"home": 180, "min": 50, "max": 180},
        12: {"home": 180, "min": 0, "max": 180},

        # Left arm
        19: {"home": 145, "min": 100, "max": 145},
        20: {"home": 80, "min": 0, "max": 150},
        21: {"home": 80, "min": 0, "max": 150},
        22: {"home": 170, "min": 110, "max": 170},
        23: {"home": 90, "min": 0, "max": 180},

        # Left hand
        24: {"home": 180, "min": 0, "max": 180},
        25: {"home": 180, "min": 0, "max": 180},
        26: {"home": 160, "min": 0, "max": 180},
        27: {"home": 120, "min": 0, "max": 120},
        28: {"home": 180, "min": 0, "max": 180},
    }

    ARM_SERVOS = {
        "right": [3, 4, 5, 6, 7],
        "left": [19, 20, 21, 22, 23],
    }

    HAND_SERVOS = {
        "right": [8, 9, 10, 11, 12],
        "left": [24, 25, 26, 27, 28],
    }

    def __init__(self, robot: RobotController):
        self.robot = robot

        self._stop_action = threading.Event()
        self._action_thread = None

        self.motion_file = MOTION_FILE
        self.current_angles = self._load_current_angles()

        # IK DH cho tay phải
        self.right_ik = InMoovRightArmDH()

    # ==================================================
    # Current angle YAML
    # ==================================================

    def _load_current_angles(self):
        try:
            with open(self.motion_file, "r") as f:
                data = yaml.safe_load(f) or {}

            servos = data.get("servos", {}) or {}

            return {
                int(k): int(v)
                for k, v in servos.items()
            }

        except FileNotFoundError:
            return {}

    def _save_current_angle(self, servo_id, angle):
        self.current_angles[int(servo_id)] = int(angle)

        data = {
            "servos": self.current_angles
        }

        with open(self.motion_file, "w") as f:
            yaml.safe_dump(
                data,
                f,
                sort_keys=True
            )

    # ==================================================
    # Low-level move
    # ==================================================

    def _clamp_angle(self, servo_id: int, angle: float) -> int:
        cfg = self.SERVO_CONFIG[servo_id]

        angle = int(round(angle))
        angle = max(
            cfg["min"],
            min(angle, cfg["max"])
        )

        return angle

    def _move_servo(self, servo_id: int, angle: float):
        safe_angle = self._clamp_angle(
            servo_id,
            angle
        )

        result = self.robot.move_servo(
            servo_id,
            safe_angle
        )

        self._save_current_angle(
            servo_id,
            safe_angle
        )

        return result

    def _move_group(self, servo_ids, angles, delay=0.05):
        for servo_id, angle in zip(servo_ids, angles):
            self._move_servo(
                servo_id,
                angle
            )

            if delay > 0:
                sleep(delay)

    def move_servos_dict(self, servo_angles: dict, delay=0.05):
        """
        Move servo theo dict:
            {3: 150, 4: 80, 5: 75, 6: 110, 7: 90}
        """

        for servo_id, angle in servo_angles.items():
            self._move_servo(
                int(servo_id),
                angle
            )

            if delay > 0:
                sleep(delay)

    # ==================================================
    # IK movement
    # ==================================================

    def move_right_to_xyz(
        self,
        x: float,
        y: float,
        z: float,
        move_even_if_unreachable: bool = False,
        delay: float = 0.08,
        initial_joints=None,
    ):
        """
        Di chuyển tay phải đến tọa độ lòng bàn tay.

        Hệ tọa độ:
            X: lên trên
            Y: sang trái
            Z: ra phía trước

        Gốc tọa độ: mắt/đầu robot.
        Đơn vị: cm.

        Tay phải thường:
            X âm
            Y âm
            Z tùy vị trí trước/sau
        """

        # Dừng action đang chạy trước khi IK điều khiển tay
        self.stop_arm_action()

        # Gọi đúng hàm IK DH
        result = self.right_ik.solve_dh(
            x,
            y,
            z,
            initial_joints=initial_joints,
        )

        print()
        print("========== IK RESULT ==========")
        print("Success:", result["success"])
        print("Target:", result["target"])
        print("Joints:", result["joints"])
        print("Servos:", result["servos"])
        print("Palm:", result.get("palm"))
        print("Points:", result["points"])
        print("Error cm:", result["error_cm"])
        print("===============================")
        print()

        if (not result["success"]) and (not move_even_if_unreachable):
            print("[WARN] Target ngoài vùng với hoặc sai số lớn.")
            print("[WARN] Không di chuyển servo.")
            print("[WARN] Nếu vẫn muốn test ép servo, đặt move_even_if_unreachable=True.")
            return result

        self.move_servos_dict(
            result["servos"],
            delay=delay
        )

        return result

    def move_right_to_obj(
        self,
        obj_xyz: dict,
        move_even_if_unreachable: bool = False,
        delay: float = 0.08,
    ):
        """
        Dùng khi vision trả về dict dạng:
            {
                "x": ...,
                "y": ...,
                "z": ...
            }
        """

        x = obj_xyz["x"]
        y = obj_xyz["y"]
        z = obj_xyz["z"]

        return self.move_right_to_xyz(
            x,
            y,
            z,
            move_even_if_unreachable=move_even_if_unreachable,
            delay=delay,
        )

    def grab_at_xyz(
        self,
        x: float,
        y: float,
        z: float,
        approach_z_offset: float = -5.0,
        move_even_if_unreachable: bool = False,
    ):
        """
        Quy trình gắp đơn giản:
        1. Mở tay
        2. Di chuyển đến gần vật
        3. Di chuyển tới vật
        4. Kẹp tay

        approach_z_offset:
            Nếu Z là hướng ra trước, có thể chỉnh offset này theo thực tế.
        """

        self.release_obj("right")

        self.move_right_to_xyz(
            x,
            y,
            z + approach_z_offset,
            move_even_if_unreachable=move_even_if_unreachable,
        )

        sleep(0.3)

        result = self.move_right_to_xyz(
            x,
            y,
            z,
            move_even_if_unreachable=move_even_if_unreachable,
        )

        sleep(0.3)

        if result["success"] or move_even_if_unreachable:
            self.grab_obj("right")

        return result

    # ==================================================
    # Direct arm/hand control
    # ==================================================

    def move_arm(
        self,
        side: str,
        angle_1,
        angle_2,
        angle_3,
        angle_4,
        angle_5
    ):
        if side not in self.ARM_SERVOS:
            raise ValueError("side must be 'right' or 'left'")

        self._move_group(
            self.ARM_SERVOS[side],
            [
                angle_1,
                angle_2,
                angle_3,
                angle_4,
                angle_5,
            ],
        )

    def move_hand(
        self,
        side: str,
        angle_1,
        angle_2,
        angle_3,
        angle_4,
        angle_5
    ):
        if side not in self.HAND_SERVOS:
            raise ValueError("side must be 'right' or 'left'")

        self._move_group(
            self.HAND_SERVOS[side],
            [
                angle_1,
                angle_2,
                angle_3,
                angle_4,
                angle_5,
            ],
        )

    def home_arm(self, side: str):
        if side not in self.ARM_SERVOS:
            raise ValueError("side must be 'right' or 'left'")

        self.stop_arm_action()

        for sid in self.ARM_SERVOS[side]:
            self._move_servo(
                sid,
                self.SERVO_CONFIG[sid]["home"]
            )

    def home_hand(self, side: str):
        if side not in self.HAND_SERVOS:
            raise ValueError("side must be 'right' or 'left'")

        for sid in self.HAND_SERVOS[side]:
            self._move_servo(
                sid,
                self.SERVO_CONFIG[sid]["home"]
            )

    def home_right_all(self):
        self.home_arm("right")
        self.home_hand("right")

    # ==================================================
    # Pose from YAML
    # ==================================================

    def set_arm_pose(self, side: str, pose_name: str):
        if side not in ["right", "left"]:
            raise ValueError("side must be 'right' or 'left'")

        self.stop_arm_action()

        key = f"{side}_arm"

        try:
            pose_data = pose["poses"][key][pose_name]
        except KeyError:
            raise ValueError(
                f"Pose '{pose_name}' not found for {key}"
            )

        for servo_id, angle in pose_data.items():
            self._move_servo(
                int(servo_id),
                angle
            )

    def set_hand_pose(self, side: str, pose_name: str):
        if side not in ["right", "left"]:
            raise ValueError("side must be 'right' or 'left'")

        key = f"{side}_hand"

        try:
            pose_data = pose["poses"][key][pose_name]
        except KeyError:
            raise ValueError(
                f"Pose '{pose_name}' not found for {key}"
            )

        for servo_id, angle in pose_data.items():
            self._move_servo(
                int(servo_id),
                angle
            )

    # ==================================================
    # Hand actions
    # ==================================================

    def grab_obj(self, side="right"):
        """
        Kẹp vật.
        Chỉnh lại các góc này theo cơ khí thực tế.
        """

        if side == "right":
            angles = {
                8: 0,
                9: 0,
                10: 0,
                11: 0,
                12: 0,
            }
        elif side == "left":
            angles = {
                24: 0,
                25: 0,
                26: 0,
                27: 0,
                28: 0,
            }
        else:
            raise ValueError("side must be 'right' or 'left'")

        self.move_servos_dict(
            angles,
            delay=0.03
        )

    def release_obj(self, side="right"):
        """
        Thả vật.
        """

        if side == "right":
            angles = {
                8: 180,
                9: 180,
                10: 160,
                11: 180,
                12: 180,
            }
        elif side == "left":
            angles = {
                24: 180,
                25: 180,
                26: 180,
                27: 120,
                28: 180,
            }
        else:
            raise ValueError("side must be 'right' or 'left'")

        self.move_servos_dict(
            angles,
            delay=0.03
        )

    # ==================================================
    # Action thread
    # ==================================================

    def start_arm_action(
        self,
        side,
        action,
        delay=0.3,
        loop=False,
        duration=None
    ):
        self.stop_arm_action()
        self._stop_action.clear()

        self._action_thread = threading.Thread(
            target=self.set_arm_action,
            args=(side, action),
            kwargs={
                "delay": delay,
                "loop": loop,
                "duration": duration,
            },
            daemon=True,
        )

        self._action_thread.start()

    def stop_arm_action(self):
        self._stop_action.set()

        if self._action_thread and self._action_thread.is_alive():
            self._action_thread.join(timeout=1.0)

    def set_arm_action(
        self,
        side: str,
        action,
        delay=1.0,
        loop=False,
        duration=None
    ):
        if side not in self.ARM_SERVOS:
            raise ValueError("side must be 'right' or 'left'")

        key = f"{side}_arm"

        def sleep_interruptible(seconds: float, step: float = 0.05):
            elapsed = 0.0

            while elapsed < seconds:
                if self._stop_action.is_set():
                    return False

                time.sleep(
                    min(step, seconds - elapsed)
                )

                elapsed += step

            return True

        if action == "talking":
            try:
                base_pose = pose["poses"][key]["talking"]
            except KeyError:
                raise ValueError(
                    f"Pose 'talking' not found for {key}"
                )

            for servo_id, angle in base_pose.items():
                if self._stop_action.is_set():
                    return

                self._move_servo(
                    int(servo_id),
                    angle
                )

            if not sleep_interruptible(0.3):
                return

            start_time = time.time()

            while not self._stop_action.is_set():
                if duration is not None and time.time() - start_time >= duration:
                    break

                for servo_id, base_angle in base_pose.items():
                    if self._stop_action.is_set():
                        return

                    delta = random.choice(
                        [0, 5, 10, 15]
                    )

                    sign = random.choice(
                        [-1, 1]
                    )

                    self._move_servo(
                        int(servo_id),
                        base_angle + sign * delta
                    )

                if not sleep_interruptible(
                    random.uniform(0.5, 1.0)
                ):
                    return

            for servo_id, angle in base_pose.items():
                if self._stop_action.is_set():
                    return

                self._move_servo(
                    int(servo_id),
                    angle
                )

            return

        if isinstance(action, list):
            if not action:
                raise ValueError("action list cannot be empty")

            while not self._stop_action.is_set():
                for pose_name in action:
                    if self._stop_action.is_set():
                        return

                    self.set_arm_pose(
                        side,
                        pose_name
                    )

                    if not sleep_interruptible(delay):
                        return

                if not loop:
                    break

            return

        if isinstance(action, str):
            self.set_arm_pose(
                side,
                action
            )
            return

        raise ValueError("action must be str or list")


# ==========================================================
# Test IK right arm
# ==========================================================

if __name__ == "__main__":
    uart = RobotController()
    robotHand = RobotArmControl(uart)

    print()
    print("Robot hand IK test")
    print("Coordinate:")
    print("  X: up")
    print("  Y: left")
    print("  Z: forward")
    print("Unit: cm")
    print()
    print("Right hand usually:")
    print("  X negative")
    print("  Y negative")
    print()
    print("Commands:")
    print("  h              : home right arm")
    print("  o              : open right hand")
    print("  c              : close right hand")
    print("  g x y z        : grab at xyz")
    print("  x y z          : move right palm to xyz")
    print("  q              : quit")
    print()

    robotHand.home_arm("right")
    robotHand.home_hand("right")
    robotHand.home_arm("left")
    robotHand.home_hand("left")
    while True:
        text = input("Nhap lenh: ").strip()

        if not text:
            continue

        if text.lower() in ["q", "quit", "exit"]:
            break

        if text.lower() in ["h", "home"]:
            robotHand.home_arm("right")
            continue

        if text.lower() in ["o", "open"]:
            robotHand.release_obj("right")
            continue

        if text.lower() in ["c", "close"]:
            robotHand.grab_obj("right")
            continue

        try:
            parts = text.split()

            if parts[0].lower() == "g":
                x, y, z = map(float, parts[1:4])

                robotHand.grab_at_xyz(x,y,z,move_even_if_unreachable=True,)

                continue

            x, y, z = map(float, parts)

            robotHand.move_right_to_xyz(x,y,z,move_even_if_unreachable=True,delay=0.08,)

        except Exception as e:
            print("Error:", e)