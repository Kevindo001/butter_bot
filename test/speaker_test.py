#!/usr/bin/env python3
import os
import subprocess

from dotenv import load_dotenv

load_dotenv()

SPEAKER_DEVICE = "hw:2,0"  # BUTTER_SPEAKER
INTRO = "Hello, I'm Butter, your home robot assistant."

ESPEAK_VOICE = os.environ.get("ESPEAK_VOICE", "en-us+m5")
ESPEAK_SPEED = os.environ.get("ESPEAK_SPEED", "210")
ESPEAK_PITCH = os.environ.get("ESPEAK_PITCH", "75")
ESPEAK_CAPITALS = os.environ.get("ESPEAK_CAPITALS", "10")
ESPEAK_AMPLITUDE = os.environ.get("ESPEAK_AMPLITUDE", "200")


def main():
    print(f"Speaking: {INTRO}")

    espeak = subprocess.Popen(
        [
            "espeak",
            "-v", ESPEAK_VOICE,
            "-s", ESPEAK_SPEED,
            "-p", ESPEAK_PITCH,
            "-k", ESPEAK_CAPITALS,
            "-a", ESPEAK_AMPLITUDE,
            "--stdout",
            INTRO,
        ],
        stdout=subprocess.PIPE,
    )
    sox = subprocess.Popen(
        ["sox", "-t", "wav", "-", "-t", "wav", "-r", "44100", "-c", "2", "-"],
        stdin=espeak.stdout,
        stdout=subprocess.PIPE,
    )
    aplay = subprocess.Popen(
        ["aplay", "-D", SPEAKER_DEVICE],
        stdin=sox.stdout,
    )
    aplay.wait()


if __name__ == "__main__":
    main()
