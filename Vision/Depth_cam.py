import cv2
import numpy as np
import yaml


with open("/home/hhl/humandroid/config.yaml", "r") as file:
    config = yaml.safe_load(file)

MODEL_PATH = config["location"]["model_path"]
DEPTH_SCALE = 0.4


class StereoCalibration:
    def __init__(
        self,
        calibration_file=MODEL_PATH + "/stereo_calib.npz"
    ):
        self.K1 = None
        self.D1 = None
        self.K2 = None
        self.D2 = None
        self.R = None
        self.T = None
        self.fx = None

        self._load(calibration_file)

    def _load(self, calibration_file):
        data = np.load(calibration_file)

        self.K1 = data["K1"]
        self.D1 = data["D1"]
        self.K2 = data["K2"]
        self.D2 = data["D2"]
        self.R = data["R"]
        self.T = data["T"]
        self.fx = self.K1[0, 0]

        print("[Calibration] Loaded successfully.")
        print(f"[Calibration] fx = {self.fx}")
        print(f"[Calibration] baseline = {np.linalg.norm(self.T):.4f} m")


class StereoRectifier:
    def __init__(
        self,
        calib: StereoCalibration,
        resolution=(640, 480)
    ):
        self.Q = None
        self.map1x = None
        self.map1y = None
        self.map2x = None
        self.map2y = None

        self._init(calib, resolution)

    def _init(self, calib, resolution):
        w, h = resolution

        R1, R2, P1, P2, Q, _, _ = cv2.stereoRectify(
            calib.K1,
            calib.D1,
            calib.K2,
            calib.D2,
            (w, h),
            calib.R,
            calib.T
        )

        self.Q = Q

        self.map1x, self.map1y = cv2.initUndistortRectifyMap(
            calib.K1,
            calib.D1,
            R1,
            P1,
            (w, h),
            cv2.CV_32FC1
        )

        self.map2x, self.map2y = cv2.initUndistortRectifyMap(
            calib.K2,
            calib.D2,
            R2,
            P2,
            (w, h),
            cv2.CV_32FC1
        )

        print("[Rectifier] Maps ready.")

    def rectify(self, left, right):
        left_rect = cv2.remap(
            left,
            self.map1x,
            self.map1y,
            cv2.INTER_LINEAR
        )

        right_rect = cv2.remap(
            right,
            self.map2x,
            self.map2y,
            cv2.INTER_LINEAR
        )

        return left_rect, right_rect


class DepthEstimator:
    def __init__(
        self,
        rectifier: StereoRectifier,
        depth_scale=DEPTH_SCALE,
        min_depth=0.0,
        max_depth=10.0
    ):
        self.rectifier = rectifier
        self.depth_scale = depth_scale
        self.min_depth = min_depth
        self.max_depth = max_depth

        self.stereo = cv2.StereoSGBM_create(
            minDisparity=0,
            numDisparities=16 * 8,
            blockSize=7,
            P1=8 * 3 * 7 ** 2,
            P2=32 * 3 * 7 ** 2,
            uniquenessRatio=10,
            speckleWindowSize=100,
            speckleRange=32,
            disp12MaxDiff=1
        )

        print("[DepthEstimator] SGBM matcher ready.")

    def compute(self, left, right):
        left_rect, right_rect = self.rectifier.rectify(
            left,
            right
        )

        gray_left = cv2.cvtColor(
            left_rect,
            cv2.COLOR_BGR2GRAY
        )

        gray_right = cv2.cvtColor(
            right_rect,
            cv2.COLOR_BGR2GRAY
        )

        disparity = (
            self.stereo.compute(gray_left, gray_right)
            .astype(np.float32) / 16.0
        )

        points_3d = cv2.reprojectImageTo3D(
            disparity,
            self.rectifier.Q
        )

        raw_depth = points_3d[:, :, 2]
        depth_map = raw_depth * self.depth_scale

        invalid_mask = (
            (depth_map < self.min_depth) |
            (depth_map > self.max_depth)
        )

        depth_map[invalid_mask] = 0.0

        return left_rect, right_rect, disparity, depth_map


class StereoDepthCamera:
    """
    Chỉ tính toán depth từ frame.
    Không start camera.
    Không stop camera.
    Không giữ CameraManager.
    """

    def __init__(
        self,
        calibration_file=MODEL_PATH + "/stereo_calib.npz",
        resolution=(640, 480),
        depth_scale=DEPTH_SCALE,
        min_depth=0.0,
        max_depth=10.0
    ):
        self.resolution = resolution

        self.calib = StereoCalibration(
            calibration_file=calibration_file
        )

        self.rectifier = StereoRectifier(
            calib=self.calib,
            resolution=resolution
        )

        self.depth_estimator = DepthEstimator(
            rectifier=self.rectifier,
            depth_scale=depth_scale,
            min_depth=min_depth,
            max_depth=max_depth
        )

        self.depth_map = None
        self.left_rect = None
        self.right_rect = None
        self.disparity = None

        print("[StereoDepthCamera] Ready.")

    def compute_depth(self, frame_left, frame_right):
        _, _, _, depth_map = self.compute_all(
            frame_left,
            frame_right
        )

        return depth_map

    def compute_all(self, frame_left, frame_right):
        left_rect, right_rect, disparity, depth_map = (
            self.depth_estimator.compute(
                frame_left,
                frame_right
            )
        )

        self.left_rect = left_rect
        self.right_rect = right_rect
        self.disparity = disparity
        self.depth_map = depth_map

        return left_rect, right_rect, disparity, depth_map

    def get_depth(self, x, y, depth_map=None):
        if depth_map is None:
            depth_map = self.depth_map

        if depth_map is None:
            return 0.0

        h, w = depth_map.shape

        x = int(x)
        y = int(y)

        if not (0 <= x < w and 0 <= y < h):
            print(f"[get_depth] ({x}, {y}) out of bounds ({w}x{h})")
            return 0.0

        return float(depth_map[y, x])

