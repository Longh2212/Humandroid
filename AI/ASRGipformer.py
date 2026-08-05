import time
import yaml
import numpy as np
import sherpa_onnx


class GipformerASR:

    def __init__(
        self,
        audio,
        config_path=
        "/home/hhl/humandroid/config.yaml"
    ):

        self.audio = audio

        with open(config_path) as file:
            config = yaml.safe_load(file)

        model_path = (
            config["location"]
            ["model_path"]
        )

        self.recognizer = (
            sherpa_onnx
            .OfflineRecognizer
            .from_transducer(
                encoder=
                f"{model_path}/avg/encoder-epoch-35-avg-6.int8.onnx",

                decoder=
                f"{model_path}/avg/decoder-epoch-35-avg-6.int8.onnx",

                joiner=
                f"{model_path}/avg/joiner-epoch-35-avg-6.int8.onnx",

                tokens=
                f"{model_path}/avg/tokens.txt",

                num_threads=6,
                sample_rate=16000,
                feature_dim=80
            )
        )

    def listen(self):

        audio = (
            self.audio
            .record_until_silence()
        )

        if audio is None:
            return ""

        start = time.time()

        stream = (
            self.recognizer
            .create_stream()
        )

        stream.accept_waveform(
            16000,
            audio.astype(np.float32)
        )

        self.recognizer.decode_streams(
            [stream]
        )

        text = (
            stream.result.text
            .strip()
            .lower()
        )

        print(
            f"⚡ ASR:"
            f" {time.time()-start:.2f}s"
        )

        return text