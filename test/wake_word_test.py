#!/usr/bin/env python3
import subprocess
import time

import numpy as np
from openwakeword.model import Model

MODEL_PATH = "models/hey_butter.onnx"
THRESHOLD = 0.5
COOLDOWN_SECONDS = 1.5  # suppress repeat detections from the same utterance
MIC_DEVICE = "hw:0,0"  # BUTTER_MIC
CAPTURE_RATE = 44100
MODEL_RATE = 16000
CHUNK_SAMPLES = 1280  # 80ms at 16000 Hz, openwakeword's expected chunk size


def mic_stream():
    """Yields 16kHz mono int16 PCM chunks captured from BUTTER_MIC and
    downsampled via sox, matching the audio pipeline documented in CLAUDE.md."""
    arecord = subprocess.Popen(
        [
            "arecord",
            "-D", MIC_DEVICE,
            "-f", "S16_LE",
            "-r", str(CAPTURE_RATE),
            "-c", "1",
            "-t", "raw",
        ],
        stdout=subprocess.PIPE,
    )
    sox = subprocess.Popen(
        [
            "sox",
            "-t", "raw", "-r", str(CAPTURE_RATE), "-e", "signed", "-b", "16", "-c", "1", "-",
            "-t", "raw", "-r", str(MODEL_RATE), "-e", "signed", "-b", "16", "-c", "1", "-",
        ],
        stdin=arecord.stdout,
        stdout=subprocess.PIPE,
    )

    bytes_per_chunk = CHUNK_SAMPLES * 2  # int16 = 2 bytes/sample
    try:
        while True:
            raw = sox.stdout.read(bytes_per_chunk)
            if len(raw) < bytes_per_chunk:
                break
            yield np.frombuffer(raw, dtype=np.int16)
    finally:
        sox.terminate()
        arecord.terminate()


def main():
    model = Model(wakeword_models=[MODEL_PATH], inference_framework="onnx")

    print("Butter wake word test")
    print(f"Say \"hey butter\" (threshold {THRESHOLD})")
    print("Ctrl+C to quit\n")

    last_detection = {}  # name -> monotonic time of last reported detection
    for chunk in mic_stream():
        predictions = model.predict(chunk)
        now = time.monotonic()
        for name, score in predictions.items():
            if score < THRESHOLD:
                continue
            if now - last_detection.get(name, -COOLDOWN_SECONDS) < COOLDOWN_SECONDS:
                continue
            last_detection[name] = now
            print(f"detected: {name}  confidence={score:.3f}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
