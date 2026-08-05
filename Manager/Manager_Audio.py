import os
import tempfile
import subprocess
import yaml
import librosa
import numpy as np
class AudioManager:
    def __init__(
        self,
        config_path="/home/hhl/humandroid/config.yaml",
    ):
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)
        self.AUDIO_DEVICE = (
            config["device"]["output_device"]
        )
    # ======================
    # PLAY AUDIO
    # ======================
    def start_audio(
        self,
        file_path: str,
        blocking: bool = True
    ):
        """
        Play audio through ALSA.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(
                f"Audio file not found: {file_path}"
            )
        command = [
            "aplay",
            "-D",
            self.AUDIO_DEVICE,
            file_path,
        ]
        if blocking:
            subprocess.run(
                command,
                check=True,
            )
            return None
        return subprocess.Popen(command)
    # ======================
    # CHANGE SPEED
    # ======================
    def amplify_audio(
        self,
        input_path,
        gain_db=10
    ):
        """
        Increase audio volume in dB.
        +6 dB ≈ 2x louder
        +10 dB noticeably louder
        """

        output_path = tempfile.mktemp(
            suffix=".wav"
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            input_path,
            "-filter:a",
            f"volume={gain_db}dB",
            output_path
        ]

        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )

        return output_path
    def process_audio_speed(
        self,
        input_path: str,
        speed: float
    ) -> str:
        """
        Change audio playback speed.
        """
        speed = max(0.5,min(speed, 2.0))
        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        ) as tmp:
            output_path = tmp.name
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                input_path,
                "-filter:a",
                f"atempo={speed}",
                output_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return output_path
    # ======================
    # EXTRACT MOUTH VALUES
    # ======================
    def extract_audio_values(
        self,
        audio_path: str,
        interval: float = 0.04,
    ):

        try:
            y, sr = librosa.load(audio_path, sr=None, mono=True)
            
            if len(y) == 0:
                return [0.0]

            hop_length = int(sr * interval)
            rms = librosa.feature.rms(y=y, frame_length=hop_length*2, hop_length=hop_length)[0]

            rms_min = np.min(rms)
            rms_max = np.max(rms)
            
            if rms_max - rms_min < 0.0001: 
                return [0.0] * len(rms)


            normalized = (rms - rms_min) / (rms_max - rms_min)

 
            normalized = np.where(normalized < 0.08, 0.0, normalized)


            smoothed = []
            prev = 0.0
            for val in normalized:
                smooth_val = prev * 0.6 + val * 0.4
                smoothed.append(smooth_val)
                prev = smooth_val

            return smoothed

        except Exception as e:
            print(f"[ERROR] extract_audio_values: {e}")
            return [0.0]
