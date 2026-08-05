import os
import time
import yaml
import threading

from Manager.Manager_Audio import AudioManager
from Manager.Manager_Robot import RobotController
from AI.TTS_Supertonic import TTSSupertonic


class HumandroidSpeak:
    def __init__(
        self,
        config_path="/home/hhl/humandroid/config.yaml"
    ):
        self.config_path = config_path

        with open(self.config_path,"r") as file:
            self.config = yaml.safe_load(file)

        config = self.config

        self.db = config["device"]["output_db"]

        # ======================
        # INIT MODULES
        # ======================
        self.audio = AudioManager(
            config_path=config_path
        )

        self.TTS = TTSSupertonic()

        self.robot = RobotController()

        # ======================
        # MOUTH CONFIG
        # ======================
        # Trong __init__
        mouth_config = config.get("mouth", {})
        self.mouth_closed_angle = mouth_config.get("closed_angle", 80)   
        self.mouth_open_range   = mouth_config.get("open_range", 70)     # 150 - 80 = 70
        self.mouth_servo_id = mouth_config.get("servo_id",0)

        self.default_speed = mouth_config.get(
            "default_speed",
            1.0
        )

        # ======================
        # STATE
        # ======================
        self.running = False
        self._speak_lock = threading.Lock()

    # ======================
    # SERVO ASYNC
    # ======================
    def move_mouth_async(
        self,
        angle: int,
    ):
        """
        Send mouth servo command
        without waiting ACK.
        """

        angle = max(0,min(180, int(angle)))
        if angle<120 and angle>100:
            angle+=20

        try:
            self.robot.send_command({
                "type": "servo",
                "id": self.mouth_servo_id,
                "angle": angle
            })

        except Exception as e:
            print(
                f"[WARNING] Mouth servo error: {e}"
            )
    # ======================
    # ANIMATE MOUTH 
    # ======================
    def animate_mouth(
        self,
        mouth_values,
        interval: float = 0.03,
        window_sec: float = 0.25,
    ):
        """
        Animate mouth using averaged
        mouth values every window_sec.
        """

        CLOSED_ANGLE = self.mouth_closed_angle
        OPEN_RANGE = self.mouth_open_range

        if not mouth_values:
            self.move_mouth_async(CLOSED_ANGLE)
            return

        chunk_size = max(
            1,
            int(window_sec / interval)
        )

        for i in range(
            0,
            len(mouth_values),
            chunk_size
        ):

            if not self.running:
                break

            chunk = mouth_values[
                i : i + chunk_size
            ]

            avg_value = (
                sum(chunk)
                / len(chunk)
            )

            avg_value = max(
                0.0,
                min(1.0, avg_value)
            )

            mouth_gain = 1.3
            avg_value = min(
                avg_value * mouth_gain,
                1.0
            )

            target_angle = (
                CLOSED_ANGLE
                + avg_value
                * OPEN_RANGE
            )

            self.move_mouth_async(
                int(target_angle)
            )

            time.sleep(window_sec)

        # close mouth
        self.move_mouth_async(
            CLOSED_ANGLE
    )


    # ======================
    # SPEAK
    # ======================
    def speak(
        self,
        text: str,
        speed: float = None,
        mouth_interval: float = 0.03,
        delete_audio: bool = True,
        ready_event=None,   
    ):
        """
        Generate speech,
        play audio,
        animate mouth.
        """

        if not text.strip():
            return

        with self._speak_lock:

            if speed is None:
                speed = (
                    self.default_speed
                )

            original_audio = None
            processed_audio = None

            self.running = True

            try:
                print(
                    "[INFO] Generating TTS..."
                )

                # ======================
                # Generate speech
                # ======================
                original_audio = (
                    self.TTS.synthesize(
                        text
                    )
                )

                # ======================
                # Speed processing
                # ======================
                # ======================
                # Speed processing
                # ======================
                processed_audio = (
                    self.audio.process_audio_speed(
                        original_audio,
                        speed,
                    )
                )

                # ======================
                # Increase speaker volume
                # ======================
                processed_audio = (
                    self.audio.amplify_audio(
                        processed_audio,
                        gain_db=self.db
                    )
                )

                # ======================
                # Extract mouth motion
                # ======================
                mouth_values = (
                    self.audio.extract_audio_values(
                        processed_audio,
                        interval=mouth_interval,
                    )
                )
                if ready_event is not None:
                    ready_event.set()
                    
                print(
                    "[INFO] Speaking..."
                )

                # ======================
                # Start audio
                # ======================
                audio_process = (
                    self.audio.start_audio(
                        processed_audio,
                        blocking=False
                    )
                )

                # allow player startup
                time.sleep(0.08)

                # ======================
                # Mouth thread
                # ======================
                mouth_thread = (
                    threading.Thread(
                        target=self.animate_mouth,
                        args=(
                            mouth_values,
                            mouth_interval,
                        ),
                    )
                )

                mouth_thread.start()

                # ======================
                # Wait finish
                # ======================
                audio_process.wait()
                self.running = False

                mouth_thread.join()

            except Exception as e:
                print(
                    f"[ERROR] Speak failed: {e}"
                )

            finally:
                self.running = False

                # Always close mouth
                try:
                    self.move_mouth_async(
                        self.mouth_closed_angle
                    )

                except Exception:
                    pass

                # Cleanup temp files
                if delete_audio:
                    for path in [
                        original_audio,
                        processed_audio,
                    ]:
                        if (
                            path
                            and os.path.exists(
                                path
                            )
                        ):
                            try:
                                os.remove(path)

                            except Exception:
                                pass

    # ======================
    # STOP SPEAK
    # ======================
    def stop(self):
        """
        Stop mouth animation.
        """

        self.running = False

        self.move_mouth_async(
            self.mouth_closed_angle
        )

    # ======================
    # CLEANUP
    # ======================
    def close(self):
        self.stop()
        self.robot.close()


# ======================
# TEST
# ======================
if __name__ == "__main__":

    speaker = HumandroidSpeak()

    try:
        speaker.speak(
            "trông giống humanoid nói chậm, thay vì rung liên tục.",
            speed=0.7,
        )

    finally:
        speaker.close()