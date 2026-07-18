#!/usr/bin/env python3
"""
End-to-end pipeline test: wake word -> STT -> Brain -> TTS.
No <action> tags are exercised here - Brain is told to only speak.
"""
import os
import re
import subprocess
import sys
import time

import numpy as np
from dotenv import load_dotenv
from faster_whisper import WhisperModel
from openai import OpenAI
from openwakeword.model import Model as WakeWordModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from butter_audio import speak

load_dotenv()

MIC_DEVICE = "hw:0,0"  # BUTTER_MIC
CAPTURE_RATE = 44100
MODEL_RATE = 16000
CHUNK_SAMPLES = 1280  # 80ms at 16kHz, openwakeword's expected chunk size

WAKE_MODEL_PATH = "models/hey_butter.onnx"
WAKE_THRESHOLD = 0.5

WHISPER_MODEL_SIZE = "base"

DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MAX_SPEAK_TOKENS = 100

SYSTEM_PROMPT = """You are Butter, a home robot, currently in a conversational pipeline test.

Actions are disabled for this test - no hardware is being exercised. Respond using ONLY:

<speak>...</speak>
  Natural, spoken-language text to say aloud. No markdown, no lists, no emoji.

Rules:
- Never emit <action> blocks or any other tags.
- Never emit text outside <speak> tags.
- Keep it short: one or two sentences. You have room for up to 100 tokens but should rarely need it - don't ramble."""

# Simple energy-based end-of-utterance detection (no manual button press).
SILENCE_RMS_THRESHOLD = 400
MIN_SPEECH_CHUNKS = 3        # ~240ms of speech before we consider it started
SILENCE_CHUNKS_TO_STOP = 12  # ~960ms of silence ends the utterance
MAX_UTTERANCE_CHUNKS = 100   # ~8s hard cap


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


def listen_for_wake(wake_model):
    """Blocks until "hey butter" is detected on BUTTER_MIC."""
    arecord, sox = start_mic_pipeline()
    try:
        while True:
            chunk = read_chunk(sox)
            if chunk is None:
                continue
            predictions = wake_model.predict(chunk)
            for name, score in predictions.items():
                if score >= WAKE_THRESHOLD:
                    print(f"  wake detected: {name} confidence={score:.3f}")
                    return
    finally:
        stop_mic_pipeline(arecord, sox)
        wake_model.reset()


def record_utterance():
    """Records from BUTTER_MIC until ~1s of silence follows detected speech,
    or MAX_UTTERANCE_CHUNKS is hit. Returns a float32 array normalized to
    [-1, 1] at 16kHz mono."""
    arecord, sox = start_mic_pipeline()
    chunks = []
    speech_chunks = 0
    silence_chunks = 0
    speech_started = False
    try:
        for _ in range(MAX_UTTERANCE_CHUNKS):
            chunk = read_chunk(sox)
            if chunk is None:
                break
            chunks.append(chunk)

            rms = np.sqrt(np.mean(chunk.astype(np.float64) ** 2))
            if rms >= SILENCE_RMS_THRESHOLD:
                speech_chunks += 1
                silence_chunks = 0
                if speech_chunks >= MIN_SPEECH_CHUNKS:
                    speech_started = True
            elif speech_started:
                silence_chunks += 1
                if silence_chunks >= SILENCE_CHUNKS_TO_STOP:
                    break
    finally:
        stop_mic_pipeline(arecord, sox)

    pcm16 = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.int16)
    return pcm16.astype(np.float32) / 32768.0


def extract_speak_text(response_text):
    matches = re.findall(r"<speak>(.*?)</speak>", response_text, re.DOTALL)
    return " ".join(m.strip() for m in matches).strip()


def ask_brain(client, transcript):
    """Streams the Brain's response (per project convention: always stream
    LLM API calls) and returns (assembled content text, finish_reason).

    deepseek-v4-pro is a reasoning model: by default it streams
    reasoning_content before content, and reasoning tokens count against
    max_tokens - a long reasoning trace can exhaust the budget before any
    <speak> content is emitted. Disabled here via extra_body (confirmed:
    drops completion_tokens from ~40-60 to ~9 and skips reasoning_content
    entirely), so the full MAX_SPEAK_TOKENS budget goes to visible text.
    finish_reason is still checked as a safety net in case that changes.
    """
    stream = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
        max_tokens=MAX_SPEAK_TOKENS,
        stream=True,
        extra_body={"thinking": {"type": "disabled"}},
    )
    full_text = ""
    finish_reason = None
    for event in stream:
        delta = event.choices[0].delta.content
        if delta:
            full_text += delta
        if event.choices[0].finish_reason:
            finish_reason = event.choices[0].finish_reason
    return full_text, finish_reason


def main():
    print("Butter conversation pipeline test")
    print("Say \"hey butter\", then speak. Ctrl+C to quit.\n")

    wake_model = WakeWordModel(wakeword_models=[WAKE_MODEL_PATH], inference_framework="onnx")
    whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    brain = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

    history = {"wake": [], "stt": [], "brain": [], "tts": [], "total": []}

    while True:
        print("Listening for \"hey butter\"...")
        t_wake_start = time.monotonic()
        listen_for_wake(wake_model)
        wake_latency = time.monotonic() - t_wake_start

        print("Listening...")
        t_record_start = time.monotonic()
        audio = record_utterance()
        recording_duration = time.monotonic() - t_record_start
        if audio.size == 0:
            print("  (no audio captured)\n")
            continue

        t_stt_start = time.monotonic()
        segments, _ = whisper_model.transcribe(audio, language="en")
        transcript = " ".join(seg.text.strip() for seg in segments).strip()
        stt_latency = time.monotonic() - t_stt_start
        print(f"  you said: {transcript}")
        if not transcript:
            print("  (empty transcript)\n")
            continue

        t_brain_start = time.monotonic()
        response_text, finish_reason = ask_brain(brain, transcript)
        brain_latency = time.monotonic() - t_brain_start
        spoken = extract_speak_text(response_text)
        if not spoken:
            if finish_reason == "length":
                print(f"  (hit MAX_SPEAK_TOKENS={MAX_SPEAK_TOKENS} before any <speak> content - "
                      "reasoning consumed the budget, try again)\n")
            else:
                print(f"  (brain returned nothing to say - raw: {response_text!r})\n")
            continue

        print(f"  butter says: {spoken}")
        t_tts_start = time.monotonic()
        speak(spoken)
        tts_latency = time.monotonic() - t_tts_start
        total_latency = stt_latency + brain_latency + tts_latency

        history["wake"].append(wake_latency)
        history["stt"].append(stt_latency)
        history["brain"].append(brain_latency)
        history["tts"].append(tts_latency)
        history["total"].append(total_latency)

        def avg(key):
            vals = history[key]
            return sum(vals) / len(vals)

        print(f"  latency: wake={wake_latency:.2f}s  recording={recording_duration:.2f}s  "
              f"stt={stt_latency:.2f}s  brain={brain_latency:.2f}s  tts={tts_latency:.2f}s  "
              f"total(stt+brain+tts)={total_latency:.2f}s")
        print(f"  running avg over {len(history['total'])} turn(s): "
              f"stt={avg('stt'):.2f}s  brain={avg('brain'):.2f}s  tts={avg('tts'):.2f}s  "
              f"total={avg('total'):.2f}s\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
