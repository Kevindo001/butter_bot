#!/usr/bin/env python3
"""GPU latency comparison: tiny.en vs base, using live recorded speech.

Both models run on device="cuda", compute_type="float16" (see
config/specs.md, STT section, for the from-source ctranslate2 CUDA build).
You speak once per round; both models transcribe the same recording so the
comparison is apples-to-apples.
"""
import subprocess
import threading
import time

import numpy as np
from faster_whisper import WhisperModel

MIC_DEVICE = "hw:0,0"  # BUTTER_MIC
CAPTURE_RATE = 44100
MODEL_RATE = 16000
DEVICE = "cuda"
COMPUTE_TYPE = "float16"
MODEL_SIZES = ["tiny.en", "base"]
NUM_ROUNDS = 5


def record_utterance():
    """Records from BUTTER_MIC until the user presses Enter, downsampling to
    16kHz mono via sox (same pipeline as test/whisper_latency_test.py), and
    returns a float32 numpy array normalized to [-1, 1]."""
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

    chunks = []

    def reader():
        while True:
            data = sox.stdout.read(4096)
            if not data:
                break
            chunks.append(data)

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    input()  # press Enter to stop

    sox.terminate()
    arecord.terminate()
    t.join(timeout=1)

    raw = b"".join(chunks)
    pcm16 = np.frombuffer(raw, dtype=np.int16)
    return pcm16.astype(np.float32) / 32768.0


def main():
    print(f"Loading {', '.join(MODEL_SIZES)} on device={DEVICE} compute_type={COMPUTE_TYPE}...")
    models = {size: WhisperModel(size, device=DEVICE, compute_type=COMPUTE_TYPE) for size in MODEL_SIZES}
    print("Models loaded.\n")

    results = {size: [] for size in MODEL_SIZES}

    for i in range(1, NUM_ROUNDS + 1):
        input(f"[{i}/{NUM_ROUNDS}] Press Enter, then speak. Press Enter again to stop recording.")
        audio = record_utterance()

        for size in MODEL_SIZES:
            start = time.monotonic()
            segments, _ = models[size].transcribe(audio, language="en")
            transcript = " ".join(seg.text.strip() for seg in segments)
            latency = time.monotonic() - start
            results[size].append(latency)
            print(f"  {size:<8} latency={latency:.3f}s  transcript: {transcript}")
        print()

    print(f"--- Results ({NUM_ROUNDS} rounds, device={DEVICE}, compute_type={COMPUTE_TYPE}) ---")
    header = f"{'model':<10}{'avg_latency':<14}{'min':<10}{'max':<10}"
    print(header)
    print("-" * len(header))
    for size in MODEL_SIZES:
        latencies = results[size]
        avg = sum(latencies) / len(latencies)
        print(f"{size:<10}{avg:<14.3f}{min(latencies):<10.3f}{max(latencies):<10.3f}")

    faster = min(MODEL_SIZES, key=lambda s: sum(results[s]) / len(results[s]))
    print(f"\nFastest: {faster}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
