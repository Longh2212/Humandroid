# -*- coding: utf-8 -*-

import os
import time
import tempfile


from supertonic import TTS


class TTSSupertonic:
    def __init__(
        self,
        model_name="supertonic",
        voice="M2",
    ):
        self.model_name = (model_name)
        self.voice = voice
        self.client = TTS(auto_download=True)
        print("TTS loaded")

    def synthesize(self,text: str) -> str:
        """
        Generate speech audio
        from text and return
        wav file path.
        """
        if not text.strip():
            raise ValueError(
                "Text is empty"
            )
        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        ) as tmp:
            output_path = (
                tmp.name
            )
        start_time = time.time()
        
        style = (self.client.get_voice_style(voice_name=self.voice))
        # synthesize
        wav, duration = (
            self.client.synthesize(
                text=text,
                voice_style=style,
                lang="vi",
            )
        )

        # save wav
        self.client.save_audio(
            wav,
            output_path,
        )

        elapsed = (
            time.time()
            - start_time
        )

        print(
            f"TTS generation time: "
            f"{elapsed:.2f}s"
        )

        return output_path


if __name__ == "__main__":

    tts = TTSSupertonic()

    audio_path = (
        tts.synthesize(
            "Xin chào, bạn cần tôi giúp gì hôm nay?"
        )
    )

    print(
        "Saved audio:",
        audio_path
    )