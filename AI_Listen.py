import os
import yaml
import time

from Manager.Manager_Mic import MicManager
from Manager.Manager_Audio import AudioManager
from AI.Wake_word import WakeWord
from AI.ASRGipformer import GipformerASR


class HumandroidListen:

    STOP_WORDS = [
        "dung",
        "dừng",
        "stop",
        "shutdown"
    ]

    def __init__(
        self,
        config_path="/home/hhl/humandroid/config.yaml"
    ):
        self.config_path = config_path

        with open(self.config_path, "r") as file:
            self.config = yaml.safe_load(file)

        model_path = self.config["location"]["model_path"]

        self.keyword_path = os.path.join(
            model_path,
            "hey-robot_en_raspberry-pi_v4_0_0.ppn"
        )

        # ==================
        # MODULES
        # ==================
        self.mic = MicManager(
            config_path=config_path
        )

        self.audio = AudioManager(
            config_path=config_path
        )

        self.wake = WakeWord(
            audio=self.audio,
            mic=self.mic,
            keyword_path=self.keyword_path
        )

        self.asr = GipformerASR(
            audio=self.mic,
            config_path=config_path
        )

        self.running = False

    # ======================
    # START
    # ======================
    def start(self):
        if self.running:
            return

        self.mic.start_mic()
        self.running = True

        print("Humandroid voice started")

    # ======================
    # WAIT FOR WAKE WORD
    # ======================
    def listen_wakeword(self) -> bool:
        """
        Wait until wake word is detected
        Returns:
            bool: True if wake word detected
        """
        try:
            detected = self.wake.listen()

            return bool(detected)

        except Exception as e:
            print(f"WakeWord error: {e}")
            return False

    # ======================
    # LISTEN SPEECH TO TEXT
    # ======================
    def listen_stt(self) -> str:
        """
        Listen user speech after wakeword
        Returns:
            str: recognized text
        """
        try:
            delay = self.config.get(
                "audio", {}
            ).get("wake_delay", 0.2)

            time.sleep(delay)

            text = self.asr.listen()

            return text.strip() if text else ""

        except Exception as e:
            print(f"ASR error: {e}")
            return ""

    # ======================
    # LISTEN FULL COMMAND
    # (WAKEWORD + STT)
    # ======================
    def listen_once(self) -> str:
        """
        Compatibility function:
        wakeword -> stt
        """
        if self.listen_wakeword():
            return self.listen_stt()

        return ""

    # ======================
    # MAIN LOOP
    # ======================
    def run(self):
        self.start()

        try:
            while self.running:

                # wait wakeword
                detected = self.listen_wakeword()

                if not detected:
                    continue

                print("Wake word detected")

                # speech to text
                text = self.listen_stt()

                if not text:
                    continue

                print("Command:", text)

                normalized = text.lower().strip()

                # stop command
                if any(
                    word in normalized
                    for word in self.STOP_WORDS
                ):
                    break

        except KeyboardInterrupt:
            print("\nStopping...")

        finally:
            self.stop()

    # ======================
    # STOP
    # ======================
    def stop(self):
        self.running = False

        try:
            self.wake.close()
        except Exception:
            pass

        try:
            if hasattr(self.mic, "stop_mic"):
                self.mic.stop_mic()
        except Exception:
            pass

        try:
            self.audio.stop()
        except Exception:
            pass

        print("Humandroid stopped")
