from Vision.Yolo import yoloCamera
from Vision.Depth_cam import StereoDepthCamera

import yaml
import numpy as np


class RobotVision:
    """
    Kết hợp YOLO + Stereo Depth.

    Camera không start/stop trong class này.
    Camera chạy ở main hoặc Manager_Camera.
    """

    def __init__(
        self,
        resolution=(640, 480),
        camera=None,
        head=None
    ):
        self.yolo = yoloCamera()

        self.depth = StereoDepthCamera(
            resolution=resolution
        )

        self.camera = camera
        self.head = head

        self.last_detections = []
        self.last_depth_map = None

    # ==================================================
    # 1. Detection
    # ==================================================

    def detection(self, frame):
        detections = self.yolo.detect(frame)
        self.last_detections = detections
        return detections

    # ==================================================
    # 2. Servo angle -> real head angle
    # ==================================================

    def _map_piecewise(
        self,
        value,
        in_min,
        in_mid,
        in_max,
        out_min,
        out_mid,
        out_max
    ):
        """
        Mapping 3 điểm để đảm bảo home đúng tuyệt đối.
        """

        value = float(value)

        if value <= in_mid:
            return out_min + (
                (value - in_min)
                * (out_mid - out_min)
                / (in_mid - in_min)
            )

        return out_mid + (
            (value - in_mid)
            * (out_max - out_mid)
            / (in_max - in_mid)
        )

    def servo_to_head_angles(
        self,
        servo1,
        servo2
    ):
        """
        Servo 1: pitch
            30  -> -10 độ, ngẩng lên
            110 -> 0 độ, home
            180 -> +30 độ, cúi xuống

        Servo 2: yaw
            10  -> -90 độ, quay trái
            75  -> 0 độ, home
            130 -> +90 độ, quay phải
        """

        pitch_deg = self._map_piecewise(
            servo1,
            30,
            110,
            180,
            -10,
            0,
            30
        )

        yaw_deg = self._map_piecewise(
            servo2,
            10,
            75,
            130,
            -90,
            0,
            90
        )

        return pitch_deg, yaw_deg

    # ==================================================
    # 3. Read head servo angles
    # ==================================================

    def read_head_servo_angles(
        self,
        path="/home/hhl/humandroid/config_servo_angles.yaml"
    ):
        """
        Đọc góc hiện tại servo 1 và 2 từ file yaml.

        Hỗ trợ dạng:

        servos:
          1: 121
          2: 63

        Hoặc:

        1: 121
        2: 63

        Hoặc:

        servo_1: 121
        servo_2: 63
        """

        with open(path, "r") as file:
            data = yaml.safe_load(file)

        if data is None:
            raise ValueError(
                f"File yaml rỗng: {path}"
            )

        if "servos" in data:
            data = data["servos"]

        def get_angle(servo_id):
            keys = [
                servo_id,
                str(servo_id),
                f"servo_{servo_id}",
                f"servo{servo_id}"
            ]

            for key in keys:
                if key in data:
                    value = data[key]

                    if isinstance(value, dict):
                        for angle_key in [
                            "angle",
                            "current",
                            "current_angle",
                            "servo_angle"
                        ]:
                            if angle_key in value:
                                return float(value[angle_key])

                    return float(value)

            raise KeyError(
                f"Không tìm thấy servo {servo_id} trong {path}"
            )

        servo1 = get_angle(1)
        servo2 = get_angle(2)

        return servo1, servo2

    # ==================================================
    # 4. Current head xyz -> home head xyz
    # ==================================================

    def current_head_xyz_to_home_xyz(
        self,
        x,
        y,
        z,
        pitch_deg,
        yaw_deg
    ):
        """
        Chuyển tọa độ từ hệ đầu hiện tại về hệ đầu home.

        Hệ tọa độ robot:
            x: lên trên
            y: sang trái
            z: ra phía trước

        Quy ước:
            pitch dương: cúi xuống
            yaw dương: quay phải
        """

        x = float(x)
        y = float(y)
        z = float(z)

        pitch = np.deg2rad(pitch_deg)
        yaw = np.deg2rad(yaw_deg)

        # Pitch quay quanh trục Y
        R_pitch = np.array([
            [np.cos(pitch), 0, -np.sin(pitch)],
            [0,             1,  0],
            [np.sin(pitch), 0,  np.cos(pitch)]
        ])

        # Yaw quay quanh trục X
        R_yaw = np.array([
            [1, 0,            0],
            [0, np.cos(yaw), -np.sin(yaw)],
            [0, np.sin(yaw),  np.cos(yaw)]
        ])

        p_current = np.array([
            [x],
            [y],
            [z]
        ])

        p_home = R_yaw @ R_pitch @ p_current

        return {
            "x": int(round(p_home[0, 0])),
            "y": int(round(p_home[1, 0])),
            "z": int(round(p_home[2, 0]))
        }

    # ==================================================
    # 5. Pixel + depth -> camera/current head xyz
    # ==================================================

    def pixel_to_camera_xyz(
        self,
        u,
        v,
        z
    ):
        """
        Đổi pixel + depth sang hệ tọa độ đầu hiện tại.

        Hệ tọa độ robot:
            x: lên trên
            y: sang trái
            z: ra phía trước

        u: pixel ngang ảnh, tăng sang phải
        v: pixel dọc ảnh, tăng xuống dưới
        z: depth lấy từ depth_map
        """

        K = self.depth.calib.K1

        fx = K[0, 0]
        fy = K[1, 1]
        cx = K[0, 2]
        cy = K[1, 2]

        right = (u - cx) * z / fx
        down = (v - cy) * z / fy

        # Scale thực nghiệm depth
        front = z 

        # Đổi sang hệ robot:
        # x: lên trên  = -down
        # y: sang trái = -right
        # z: phía trước = front
        x = -down
        y = -right
        z = front

        return {
            "x": int(round(x * 100)),
            "y": int(round(y * 100)),
            "z": int(round(z * 100))
        }

    # ==================================================
    # 6. Pixel + depth -> home xyz
    # ==================================================

    def pixel_to_home_xyz(
        self,
        u,
        v,
        z
    ):
        """
        Đổi pixel + depth sang tọa độ trong hệ đầu home.
        """

        xyz_current = self.pixel_to_camera_xyz(
            u,
            v,
            z
        )

        if self.head is None:
            raise ValueError(
                "RobotVision chưa có head. "
                "Hãy truyền head vào RobotVision(head=head)"
            )

        servo1 = self.head.current_pitch
        servo2 = self.head.current_yaw

        pitch_deg, yaw_deg = self.servo_to_head_angles(
            servo1,
            servo2
        )

        xyz_home = self.current_head_xyz_to_home_xyz(
            xyz_current["x"],
            xyz_current["y"],
            xyz_current["z"],
            pitch_deg,
            yaw_deg
        )

        return {
            "x": xyz_home["x"],
            "y": xyz_home["y"],
            "z": xyz_home["z"],

            "current_x": xyz_current["x"],
            "current_y": xyz_current["y"],
            "current_z": xyz_current["z"],

            "pitch_deg": round(pitch_deg, 2),
            "yaw_deg": round(yaw_deg, 2),

            "servo1": servo1,
            "servo2": servo2
        }

    # ==================================================
    # 7. Find human face
    # ==================================================

    def find_human_face(
        self,
        frame,
        detections=None
    ):
        if detections is None:
            detections = self.detection(frame)

        return self.yolo.human_face(
            detections
        )

    # ==================================================
    # 8. Internal: frame -> object position
    # ==================================================

    def _get_obj_position_from_frames(
        self,
        frame_left,
        frame_right,
        obj_type,
        detections=None
    ):
        """
        Hàm nội bộ.

        Input:
            frame_left
            frame_right
            obj_type: ví dụ "bottle", "cup", "chair"

        Output:
            None nếu không thấy vật hoặc depth lỗi.

            Nếu thấy:
            {
                "obj": "bottle",
                "x": ...,
                "y": ...,
                "z": ...,
                ...
            }
        """

        if detections is None:
            detections = self.detection(frame_left)

        obj = self.yolo.detect_obj(
            detections,
            obj_type
        )

        if obj is None:
            return None

        depth_map = self.depth.compute_depth(
            frame_left,
            frame_right
        )

        self.last_depth_map = depth_map

        depth_z = self.depth.get_depth(
            obj["x"],
            obj["y"],
            depth_map
        )

        if depth_z is None or depth_z <= 0:
            return None

        xyz = self.pixel_to_home_xyz(
            obj["x"],
            obj["y"],
            depth_z
        )

        return {
            "obj": obj["obj"],

            "x": xyz["x"],
            "y": xyz["y"],
            "z": xyz["z"],

            "current_x": xyz["current_x"],
            "current_y": xyz["current_y"],
            "current_z": xyz["current_z"],

            "pitch_deg": xyz["pitch_deg"],
            "yaw_deg": xyz["yaw_deg"],

            "servo1": xyz["servo1"],
            "servo2": xyz["servo2"],

            "pixel_x": obj["x"],
            "pixel_y": obj["y"],
            "depth_raw": depth_z
        }

    # ==================================================
    # 9. Public: get object position
    # ==================================================

    def get_obj_position(
        self,
        obj_type,
        detections=None
    ):
        """
        Hàm chính dùng bên ngoài.

        Ví dụ:
            pos = vision.get_obj_position("bottle")

        Trả về:
            None nếu không thấy vật hoặc depth lỗi.

            {
                "obj": "bottle",
                "x": ...,
                "y": ...,
                "z": ...,
                "current_x": ...,
                "current_y": ...,
                "current_z": ...,
                "pitch_deg": ...,
                "yaw_deg": ...,
                "servo1": ...,
                "servo2": ...,
                "pixel_x": ...,
                "pixel_y": ...,
                "depth_raw": ...
            }
        """

        if self.camera is None:
            raise ValueError(
                "RobotVision chưa có camera. "
                "Hãy truyền camera vào RobotVision(camera=camera)"
            )

        frame_left, frame_right = self.camera.get_frames()

        if frame_left is None or frame_right is None:
            return None

        return self._get_obj_position_from_frames(
            frame_left=frame_left,
            frame_right=frame_right,
            obj_type=obj_type,
            detections=detections
        )

if __name__ == "__main__":

    import cv2
    import time
    import threading

    from Manager.Manager_Camera import CameraManager
    from Manager.Manager_Robot import RobotController

    # Nếu bạn có RobotHeadControl thì import
    # Nếu chưa muốn điều khiển đầu thật, có thể dùng FakeHead bên dưới
    try:
        from Robot_headcontrol import RobotHeadControl
        USE_REAL_HEAD = True
    except Exception:
        RobotHeadControl = None
        USE_REAL_HEAD = False


    # ==================================================
    # Fake head dùng để test khi không muốn chạy servo thật
    # ==================================================
    class FakeHead:
        """
        Dùng để test tọa độ khi đầu ở home.
        current_pitch = 110
        current_yaw = 75

        Theo code hiện tại:
            pitch servo 110 -> pitch_deg = 0
            yaw servo 75    -> yaw_deg = 0
        """

        def __init__(self):
            self.current_pitch = 180
            self.current_yaw = 75


    # ==================================================
    # Hàm vẽ kết quả lên frame
    # ==================================================
    def draw_result(frame, result):
        if result is None:
            cv2.putText(
                frame,
                "Object: NOT FOUND",
                (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )
            return frame

        px = int(result["pixel_x"])
        py = int(result["pixel_y"])

        cv2.circle(
            frame,
            (px, py),
            6,
            (0, 255, 0),
            -1
        )

        lines = [
            f"obj: {result['obj']}",
            f"pixel: ({result['pixel_x']:.1f}, {result['pixel_y']:.1f})",
            f"depth_raw: {result['depth_raw']:.3f}",
            f"current xyz: ({result['current_x']}, {result['current_y']}, {result['current_z']}) cm",
            f"home xyz: ({result['x']}, {result['y']}, {result['z']}) cm",
            f"pitch/yaw deg: ({result['pitch_deg']}, {result['yaw_deg']})",
            f"servo1/servo2: ({result['servo1']}, {result['servo2']})"
        ]

        y0 = 30
        for i, text in enumerate(lines):
            cv2.putText(
                frame,
                text,
                (20, y0 + i * 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 255, 0),
                2
            )

        return frame


    # ==================================================
    # Main test
    # ==================================================
    running = True

    print("===================================")
    print(" RobotVision Coordinate Test")
    print("===================================")
    print("Phim:")
    print("  q / ESC : thoat")
    print("  h       : test voi dau home fake")
    print("===================================")

    obj_type = input("Nhap ten vat can detect, vi du bottle/cup/person: ").strip()

    if obj_type == "":
        obj_type = "bottle"

    # =====================
    # Init camera
    # =====================
    camera = CameraManager()
    camera.start()

    # =====================
    # Init head
    # =====================
    robot = None
    head = None

    if USE_REAL_HEAD:
        try:
            robot = RobotController()

            # Tạo vision tạm trước, lát nữa gán lại head
            vision = RobotVision(
                camera=camera,
                head=None
            )

            head = RobotHeadControl(
                vision=vision,
                robot=robot
            )

            vision.head = head

            print("[INFO] Dang dung RobotHeadControl that.")
            print("[INFO] Neu khong muon servo dau chay, sua USE_REAL_HEAD = False.")

        except Exception as e:
            print("[WARN] Khong khoi tao duoc RobotHeadControl, dung FakeHead.")
            print("[WARN]", e)

            head = FakeHead()

            vision = RobotVision(
                camera=camera,
                head=head
            )

    else:
        head = FakeHead()

        vision = RobotVision(
            camera=camera,
            head=head
        )

        print("[INFO] Dang dung FakeHead home.")


    try:
        while running:

            frame_left, frame_right = camera.get_frames()

            if frame_left is None or frame_right is None:
                print("[WARN] Khong lay duoc frame.")
                time.sleep(0.05)
                continue

            # Copy frame de ve
            display = frame_left.copy()

            # ==================================================
            # Test tinh toa do
            # ==================================================
            result = vision._get_obj_position_from_frames(
                frame_left=frame_left,
                frame_right=frame_right,
                obj_type=obj_type
            )

            display = draw_result(display, result)

            # Ve tam anh de de test
            h, w = display.shape[:2]
            cx = w // 2
            cy = h // 2

            cv2.line(display, (cx - 20, cy), (cx + 20, cy), (255, 0, 0), 2)
            cv2.line(display, (cx, cy - 20), (cx, cy + 20), (255, 0, 0), 2)

            cv2.imshow("RobotVision Coordinate Test - Left", display)

            if frame_right is not None:
                cv2.imshow("Right Camera", frame_right)

            # ==================================================
            # In console de debug
            # ==================================================
            if result is not None:
                print("\n========== RESULT ==========")
                print(f"Object       : {result['obj']}")
                print(f"Pixel        : x={result['pixel_x']:.1f}, y={result['pixel_y']:.1f}")
                print(f"Depth raw    : {result['depth_raw']:.4f}")
                print(f"Current XYZ  : x={result['current_x']}, y={result['current_y']}, z={result['current_z']} cm")
                print(f"Home XYZ     : x={result['x']}, y={result['y']}, z={result['z']} cm")
                print(f"Head deg     : pitch={result['pitch_deg']}, yaw={result['yaw_deg']}")
                print(f"Servo        : servo1={result['servo1']}, servo2={result['servo2']}")
                print("============================")

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q") or key == 27:
                running = False
                break

            elif key == ord("h"):
                # Reset fake head ve home neu dang fake
                if isinstance(head, FakeHead):
                    head.current_pitch = 110
                    head.current_yaw = 75
                    print("[INFO] FakeHead reset ve home: pitch=110, yaw=75")

    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user.")

    finally:
        running = False

        try:
            if hasattr(camera, "release"):
                camera.release()
        except Exception:
            pass

        cv2.destroyAllWindows()

        print("[INFO] Camera released.")