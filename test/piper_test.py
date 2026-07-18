#!/usr/bin/env python3
import subprocess

SPEAKER_DEVICE = "hw:2,0"  # BUTTER_SPEAKER
INTRO = "Hey, I am Butter. Your personal home robot. How can I help you today?"

PIPER_BIN = "butter_env/bin/piper"
MODEL_PATH = "models/piper/en_US-lessac-medium.onnx"
MODEL_SAMPLE_RATE = 22050  # from en_US-lessac-medium.onnx.json audio.sample_rate


def main():
    print(f"Speaking: {INTRO}")

    piper = subprocess.Popen(
        [PIPER_BIN, "--model", MODEL_PATH, "--output_raw"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    piper.stdin.write(INTRO.encode())
    piper.stdin.close()

    sox = subprocess.Popen(
        [
            "sox",
            "-t", "raw", "-r", str(MODEL_SAMPLE_RATE), "-e", "signed", "-b", "16", "-c", "1", "-",
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
    main()
