#!/usr/bin/env python3
import os
import subprocess

from dotenv import load_dotenv
from piper import PiperVoice, SynthesisConfig

load_dotenv()

SPEAKER_DEVICE = os.environ.get("SPEAKER_DEVICE", "hw:2,0")  # BUTTER_SPEAKER
PIPER_MODEL_PATH = os.environ.get("PIPER_MODEL_PATH", "models/piper/en_US-lessac-medium.onnx")
PIPER_VOLUME = float(os.environ.get("PIPER_VOLUME", "1.0"))

_voice = None


def _get_voice():
    """Lazily loads the Piper ONNX model once and caches it. Loading costs
    ~1.5s (ONNX Runtime session init) - paying that per speak() call (the
    old subprocess-per-call approach) was the dominant latency cost once
    streaming TTS started calling speak() once per sentence."""
    global _voice
    if _voice is None:
        _voice = PiperVoice.load(PIPER_MODEL_PATH)
    return _voice


def speak(text, volume=None):
    """Synthesizes text via a warm-loaded Piper voice and plays it on
    BUTTER_SPEAKER."""
    if volume is None:
        volume = PIPER_VOLUME

    voice = _get_voice()
    syn_config = SynthesisConfig(volume=volume)
    chunks = list(voice.synthesize(text, syn_config=syn_config))
    if not chunks:
        return
    sample_rate = chunks[0].sample_rate
    pcm_bytes = b"".join(c.audio_int16_bytes for c in chunks)

    sox = subprocess.Popen(
        [
            "sox",
            "-t", "raw", "-r", str(sample_rate), "-e", "signed", "-b", "16", "-c", "1", "-",
            "-t", "wav", "-r", "44100", "-c", "2", "-",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    aplay = subprocess.Popen(
        ["aplay", "-D", SPEAKER_DEVICE],
        stdin=sox.stdout,
    )
    sox.stdin.write(pcm_bytes)
    sox.stdin.close()
    aplay.wait()


if __name__ == "__main__":
    speak("Hello, I'm Butter, your home robot assistant.")
