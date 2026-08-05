import os
import tempfile
import subprocess

import sounddevice as sd
import numpy as np
import webrtcvad
import yaml

from scipy.signal import resample_poly
from collections import deque


class MicManager:
    def __init__(
        self,
        config_path="/home/hhl/humandroid/config.yaml",
        mic_sr=48000,
        target_sr=16000
    ):

        with open(config_path, "r") as file:
            config = yaml.safe_load(file)

        self.MIC_DEVICE = config["device"]["mic_device"]

        self.mic_sr = mic_sr
        self.target_sr = target_sr

        self.stream = None

        # ==========================
        # VAD
        # ==========================
        self.frame_ms = 30

        self.vad_frame = int(
            self.target_sr * self.frame_ms / 1000
        )

        self.mic_frame = int(
            self.mic_sr * self.frame_ms / 1000
        )

        self.silence_limit = int(
            2000 / self.frame_ms
        )

        self.vad = webrtcvad.Vad(3)

    # ==================================
    # STREAM
    # ==================================
    def start_mic(self):

        self.stream = sd.InputStream(
            samplerate=self.mic_sr,
            channels=1,
            dtype="float32",
            device=self.MIC_DEVICE
        )

        self.stream.start()

        print(
            f"Mic started: "
            f"{self.MIC_DEVICE}"
        )

    def stop(self):

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        print("🛑 Audio stopped")

    # ==================================
    # READ
    # ==================================
    def read(self, frames):

        audio, _ = self.stream.read(frames)

        return audio.flatten()

    def read_16k(self, frames):

        audio = self.read(frames)

        return resample_poly(
            audio,
            self.target_sr,
            self.mic_sr
        )

    # ==================================
    # RECORD WITH VAD
    # ==================================
    def record_until_silence(self):

        duration = 5.0

        total_frames = int(
            self.mic_sr * duration
        )

        audio = self.read(total_frames)

        audio_16k = resample_poly(
            audio,
            self.target_sr,
            self.mic_sr
        )

        return audio_16k
