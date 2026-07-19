#!/usr/bin/env python3
"""GPU vs CPU faster-whisper latency benchmark.

Compares tiny.en/base/small on device="cpu" (compute_type="int8") against
device="cuda" (compute_type="float16"), now that ctranslate2 has been
rebuilt from source with CUDA+cuDNN support for sm_87 (see config/specs.md,
STT section). Records one fixed 3-second clip from BUTTER_MIC and reuses it
for every combination so the comparison is apples-to-apples.
"""
import subprocess
import time
import wave

import numpy as np
from faster_whisper import WhisperModel

MIC_DEVICE = "hw:0,0"  # BUTTER_MIC
CAPTURE_RATE = 44100
MODEL_RATE = 16000
CLIP_SECONDS = 3
RAW_WAV_PATH = "/tmp/test_audio.wav"
RESAMPLED_WAV_PATH = "/tmp/test_audio_16k.wav"

MODEL_SIZES = ["tiny.en", "base", "small"]
DEVICE_CONFIGS = [("cuda", "float16")]
NUM_RUNS = 3


def record_test_clip():
    """Records one fixed clip from BUTTER_MIC and downsamples it to 16kHz,
    returning a float32 numpy array normalized to [-1, 1]."""
    print(f"Recording a fixed {CLIP_SECONDS}s test clip from BUTTER_MIC...")
    subprocess.run(
        [
            "arecord",
            "-D", MIC_DEVICE,
            "-f", "S16_LE",
            "-r", str(CAPTURE_RATE),
            "-c", "1",
            "-d", str(CLIP_SECONDS),
            "-t", "wav",
            RAW_WAV_PATH,
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["sox", RAW_WAV_PATH, "-r", str(MODEL_RATE), RESAMPLED_WAV_PATH],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    with wave.open(RESAMPLED_WAV_PATH, "rb") as wf:
        frames = wf.readframes(wf.getnframes())
    pcm16 = np.frombuffer(frames, dtype=np.int16)
    return pcm16.astype(np.float32) / 32768.0


def benchmark(model_size, device, compute_type, audio):
    print(f"Loading {model_size} on device={device} compute_type={compute_type}...")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    latencies = []
    for i in range(1, NUM_RUNS + 1):
        start = time.monotonic()
        segments, _ = model.transcribe(audio, language="en")
        transcript = " ".join(seg.text.strip() for seg in segments)
        latency = time.monotonic() - start
        latencies.append(latency)
        print(f"  run {i}/{NUM_RUNS}: {latency:.3f}s  ({transcript!r})")

    return latencies


def main():
    audio = record_test_clip()
    print("Clip captured — same input used for every combination.\n")

    results = []
    for model_size in MODEL_SIZES:
        for device, compute_type in DEVICE_CONFIGS:
            latencies = benchmark(model_size, device, compute_type, audio)
            results.append({
                "model": model_size,
                "device": device,
                "compute_type": compute_type,
                "avg": sum(latencies) / len(latencies),
                "min": min(latencies),
                "max": max(latencies),
            })
            print()

    header = f"{'model':<10}{'device':<8}{'avg_latency':<14}{'min':<10}{'max':<10}"
    print("--- Results ---")
    print(header)
    print("-" * len(header))
    for r in results:
        print(f"{r['model']:<10}{r['device']:<8}{r['avg']:<14.3f}{r['min']:<10.3f}{r['max']:<10.3f}")

    winner = min(results, key=lambda r: r["avg"])
    print(f"\nFastest: {winner['model']} on device={winner['device']} compute_type={winner['compute_type']} "
          f"(avg {winner['avg']:.3f}s)")


if __name__ == "__main__":
    main()
