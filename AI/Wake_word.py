import os
import pvporcupine
import numpy as np

from dotenv import load_dotenv
from scipy.signal import resample_poly


class WakeWord:

    def __init__(
        self,
        mic,
        audio,
        keyword_path
    ):

        load_dotenv()
        if not os.path.exists(
            keyword_path
        ):
            raise FileNotFoundError(
                f"Keyword file not found: "
                f"{keyword_path}"
            )
        self.audio = audio
        self.mic = mic
        if (self.mic.mic_sr% 16000 != 0):
            raise ValueError(
                "mic_sr must be "
                "divisible by 16000"
            )

        self.porcupine = (pvporcupine.create(
            access_key=os.getenv("PORCUPINE_KEY"),
            keyword_paths=[keyword_path]
            )
        )

        self.frame_length = (
            self.porcupine.frame_length
        )

        self.target_sr = 16000

        self.mic_frame = int(
            self.frame_length
            * self.mic.mic_sr
            / self.target_sr
        )

        self.wake_file_path = (
            "/home/hhl/"
            "humandroid/"
            "Source/Audio/"
            "heard1.wav"
        )

    def listen(self):

        while True:

            mic = self.mic.read(
                self.mic_frame
            )

            audio_16k = (
                resample_poly(
                    mic,
                    self.target_sr,
                    self.mic.mic_sr
                )
            )

            if (
                len(audio_16k)
                != self.frame_length
            ):
                continue

            audio_int16 = (
                audio_16k * 32767
            ).astype(np.int16)

            result = (
                self.porcupine.process(
                    audio_int16
                )
            )

            if result >= 0:

                print(
                    "Wake word!"
                )

                self.audio.start_audio(
                    self.wake_file_path
                )

                return True

    def close(self):

        if self.porcupine:
            self.porcupine.delete()