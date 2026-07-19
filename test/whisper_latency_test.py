#!/usr/bin/env python3
import subprocess
import threading
import time

import numpy as np
from faster_whisper import WhisperModel

MIC_DEVICE = "hw:0,0"  # BUTTER_MIC
CAPTURE_RATE = 44100
MODEL_RATE = 16000
MODEL_SIZE = "base"
NUM_QUERIES = 10

# GPU: ctranslate2 was rebuilt from source with CUDA+cuDNN for sm_87 (see
# config/specs.md, STT section) - base/GPU is now the standard STT config.
DEVICE = "cuda"
COMPUTE_TYPE = "float16"


def record_utterance():
    """Records from BUTTER_MIC until the user presses Enter, downsampling to
    16kHz mono via sox (same pipeline as test/wake_word_test.py), and returns
    a float32 numpy array normalized to [-1, 1]."""
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


def word_error_rate(reference, hypothesis):
    """Word-level Levenshtein distance / len(reference words)."""
    ref = reference.lower().split()
    hyp = hypothesis.lower().split()
    if not ref:
        return 0.0 if not hyp else 1.0

    dp = list(range(len(hyp) + 1))
    for i in range(1, len(ref) + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, len(hyp) + 1):
            tmp = dp[j]
            if ref[i - 1] == hyp[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = tmp
    return dp[len(hyp)] / len(ref)


def main():
    print("Butter Whisper latency + accuracy test")
    print(f"Loading faster-whisper model={MODEL_SIZE} device={DEVICE} compute_type={COMPUTE_TYPE} ...")
    model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    print(f"Model loaded on device={DEVICE}\n")

    latencies = []
    error_rates = []

    for i in range(1, NUM_QUERIES + 1):
        input(f"[{i}/{NUM_QUERIES}] Press Enter, then speak. Press Enter again to stop recording.")
        audio = record_utterance()

        start = time.monotonic()
        segments, _ = model.transcribe(audio, language="en")
        transcript = " ".join(seg.text.strip() for seg in segments)
        latency = time.monotonic() - start

        print(f"  transcript: {transcript}")
        print(f"  latency: {latency:.3f}s")

        reference = input("  what did you actually say? (Enter if the transcript is exact): ").strip()
        if not reference:
            reference = transcript
        wer = word_error_rate(reference, transcript)
        print(f"  word error rate: {wer:.2%}\n")

        latencies.append(latency)
        error_rates.append(wer)

    avg_latency = sum(latencies) / len(latencies)
    avg_wer = sum(error_rates) / len(error_rates)
    print(f"--- {NUM_QUERIES} queries on device={DEVICE} ---")
    print(f"average latency: {avg_latency:.3f}s")
    print(f"average word error rate: {avg_wer:.2%}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
