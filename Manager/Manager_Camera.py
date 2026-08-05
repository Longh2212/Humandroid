import cv2
import time
from picamera2 import Picamera2
import time

class CameraManager:
    def __init__(
        self,
        cam0_id=0,
        cam1_id=1,
        resolution=(640, 480),
        rotate=True,
    ):
        self.cam0_id = cam0_id
        self.cam1_id = cam1_id
        self.resolution = resolution
        self.rotate = rotate

        self.picam0 = None
        self.picam1 = None

    def start(self):
        try:
            self.picam0 = Picamera2(self.cam0_id)
            self.picam1 = Picamera2(self.cam1_id)

            config0 = self.picam0.create_preview_configuration(
                main={"size": self.resolution}
            )

            config1 = self.picam1.create_preview_configuration(
                main={"size": self.resolution}
            )

            self.picam0.configure(config0)
            self.picam1.configure(config1)

            self.picam0.start()
            self.picam1.start()

            time.sleep(0.5)

            print("[INFO] Cameras started.")

        except Exception as e:
            print(f"[ERROR] {e}")
            self.stop()
            raise

    def get_frames(self):
        if self.picam0 is None or self.picam1 is None:
            raise RuntimeError(
                "Camera not started."
            )

        frame0 = self.preprocess(
            self.picam0.capture_array()
        )

        frame1 = self.preprocess(
            self.picam1.capture_array()
        )


        return frame0, frame1

    def preprocess(self, frame):
        
                
        if len(frame.shape) == 3 and frame.shape[2] == 4:
            frame = cv2.cvtColor(frame,cv2.COLOR_BGRA2BGR)

            if self.rotate:
                frame = cv2.rotate(
                    frame,
                    cv2.ROTATE_180
                )

        return frame

    def stop(self):

        if self.picam0:
            self.picam0.stop()
            self.picam0.close()
            self.picam0 = None

        if self.picam1:
            self.picam1.stop()
            self.picam1.close()
            self.picam1 = None

        print("[INFO] Cameras stopped.")
if __name__ == "__main__":
    frame_count=0
    cam_manager = CameraManager(
        cam0_id=0,
        cam1_id=1,
        resolution=(640, 480),
        rotate=True
    )

    try:
        cam_manager.start()
        last = 0
        while True:
            now = time.time()
            if now - last  >=1:
                print(frame_count)
                frame_count = 0
                last = now
            else:
                frame_count +=1
            frame0, frame1 = (
                cam_manager.get_frames()
            )

            cv2.putText(
                frame0,
                "Cam1",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

            cv2.putText(
                frame1,
                "Cam2",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

            panel = cv2.hconcat([
                frame0,
                frame1
            ])

            cv2.imshow(
                "Dual Camera Panel",
                panel
            )

            if (
                cv2.waitKey(1) & 0xFF
                == ord("q")
            ):
                break

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")

    except Exception as e:
        print(f"[ERROR] {e}")

    finally:
        cam_manager.stop()
        cv2.destroyAllWindows()
