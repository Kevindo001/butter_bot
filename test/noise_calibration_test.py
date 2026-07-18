#!/usr/bin/env python3
"""
Records a few seconds of room background noise and suggests a
SILENCE_RMS_THRESHOLD value for conversation_test.py's end-of-utterance
detection - stay quiet (don't talk over it) while it records.
"""
import subprocess

import numpy as np

MIC_DEVICE = "hw:0,0"  # BUTTER_MIC
CAPTURE_RATE = 44100
MODEL_RATE = 16000
CHUNK_SAMPLES = 1280  # 80ms at 16kHz, same chunking as conversation_test.py

RECORD_SECONDS = 4.0
MARGIN = 1.5  # suggested threshold = peak background RMS * MARGIN


def start_mic_pipeline():
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
        stderr=subprocess.DEVNULL,
    )
    sox = subprocess.Popen(
        [
            "sox",
            "-t", "raw", "-r", str(CAPTURE_RATE), "-e", "signed", "-b", "16", "-c", "1", "-",
            "-t", "raw", "-r", str(MODEL_RATE), "-e", "signed", "-b", "16", "-c", "1", "-",
        ],
        stdin=arecord.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return arecord, sox


def stop_mic_pipeline(arecord, sox):
    sox.terminate()
    arecord.terminate()
    sox.wait(timeout=2)
    arecord.wait(timeout=2)


def read_chunk(sox):
    raw = sox.stdout.read(CHUNK_SAMPLES * 2)  # int16 = 2 bytes/sample
    if len(raw) < CHUNK_SAMPLES * 2:
        return None
    return np.frombuffer(raw, dtype=np.int16)


def record_background_rms(seconds):
    num_chunks = int(round(seconds * MODEL_RATE / CHUNK_SAMPLES))
    arecord, sox = start_mic_pipeline()
    rms_values = []
    try:
        for _ in range(num_chunks):
            chunk = read_chunk(sox)
            if chunk is None:
                break
            rms = np.sqrt(np.mean(chunk.astype(np.float64) ** 2))
            rms_values.append(rms)
    finally:
        stop_mic_pipeline(arecord, sox)
    return rms_values


def main():
    print("Butter background noise calibration")
    print(f"Stay quiet - on Enter, records {RECORD_SECONDS:.0f}s of room noise.\n")
    input("Press Enter to start...")
    print("Recording...")

    rms_values = record_background_rms(RECORD_SECONDS)
    if not rms_values:
        print("(no audio captured)")
        return

    rms_min = min(rms_values)
    rms_max = max(rms_values)
    rms_mean = sum(rms_values) / len(rms_values)
    rms_std = (sum((v - rms_mean) ** 2 for v in rms_values) / len(rms_values)) ** 0.5
    suggested = round(rms_max * MARGIN)

    print(f"\n{len(rms_values)} chunks captured")
    print(f"background rms: min={rms_min:.0f}  max={rms_max:.0f}  mean={rms_mean:.0f}  std={rms_std:.0f}")
    print(f"\nsuggested SILENCE_RMS_THRESHOLD = {suggested}  (peak background rms x {MARGIN})")
    print("Set this in test/conversation_test.py's SILENCE_RMS_THRESHOLD constant.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
