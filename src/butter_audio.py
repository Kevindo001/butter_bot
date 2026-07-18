#!/usr/bin/env python3
import os
import subprocess

from dotenv import load_dotenv

load_dotenv()

SPEAKER_DEVICE = os.environ.get("SPEAKER_DEVICE", "hw:2,0")  # BUTTER_SPEAKER
PIPER_BIN = os.environ.get("PIPER_BIN", "piper")
PIPER_MODEL_PATH = os.environ.get("PIPER_MODEL_PATH", "models/piper/en_US-lessac-medium.onnx")
PIPER_SAMPLE_RATE = int(os.environ.get("PIPER_SAMPLE_RATE", "22050"))
PIPER_VOLUME = float(os.environ.get("PIPER_VOLUME", "1.0"))


def speak(text, volume=None):
    """Synthesizes text via Piper and plays it on BUTTER_SPEAKER."""
    if volume is None:
        volume = PIPER_VOLUME

    piper = subprocess.Popen(
        [
            PIPER_BIN,
            "--model", PIPER_MODEL_PATH,
            "--output_raw",
            "--volume", str(volume),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    piper.stdin.write(text.encode())
    piper.stdin.close()

    sox = subprocess.Popen(
        [
            "sox",
            "-t", "raw", "-r", str(PIPER_SAMPLE_RATE), "-e", "signed", "-b", "16", "-c", "1", "-",
            "-t", "wav", "-r", "44100", "-c", "2", "-",
        ],
        stdin=piper.stdout,
        stdout=subprocess.PIPE,
    )
    aplay = subprocess.Popen(
        ["aplay", "-D", SPEAKER_DEVICE],
        stdin=sox.stdout,
    )
    aplay.wait()


if __name__ == "__main__":
    speak("Hello, I'm Butter, your home robot assistant.")
