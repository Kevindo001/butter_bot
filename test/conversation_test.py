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
from collections import deque

import numpy as np
from dotenv import load_dotenv
from faster_whisper import WhisperModel
from openai import OpenAI
from openwakeword.model import Model as WakeWordModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from butter_audio import speak
import butter_audio

load_dotenv()

MIC_DEVICE = "hw:0,0"  # BUTTER_MIC
CAPTURE_RATE = 44100
MODEL_RATE = 16000
CHUNK_SAMPLES = 1280  # 80ms at 16kHz, openwakeword's expected chunk size
CHUNK_SECONDS = CHUNK_SAMPLES / MODEL_RATE

WAKE_MODEL_PATH = "models/hey_butter.onnx"
WAKE_THRESHOLD = 0.5

WHISPER_MODEL_SIZE = "tiny.en"

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
SILENCE_RMS_THRESHOLD = 2500
# The wake word already confirms speech is happening, so there's no random
# noise spike to filter out at recording start - one loud chunk is enough.
MIN_SPEECH_CHUNKS = 1
SILENCE_CHUNKS_TO_STOP = 7  # ~960ms of silence ends the utterance
MAX_UTTERANCE_CHUNKS = 100   # ~8s hard cap after wake fires

# Rolling pre-wake buffer: openwakeword only fires once "hey butter" is
# already spoken, and restarting a fresh arecord|sox pipeline afterward has
# real startup lag - both together were eating the first 1-3s of the actual
# command. Instead we keep ONE mic pipeline running for the whole session
# and continuously keep the trailing N seconds of audio around; when wake
# fires, that buffer (which already contains "hey butter" plus whatever
# followed it while detection was catching up) seeds the utterance capture
# instead of starting from silence.
ROLLING_BUFFER_SECONDS = 1.5
ROLLING_BUFFER_CHUNKS = int(round(ROLLING_BUFFER_SECONDS / CHUNK_SECONDS))

SENTENCE_END_RE = re.compile(r"[.!?]+(?:\s|$)")


def _split_partial_tag_suffix(s, tag):
    """Splits s into (safe, held) where held is the longest suffix of s that
    is also a prefix of tag - i.e. text that might be the start of tag but
    hasn't been confirmed yet since more stream data could complete it.
    held must never be flushed or tag-searched until more data arrives."""
    max_len = min(len(tag) - 1, len(s))
    for length in range(max_len, 0, -1):
        if tag.startswith(s[-length:]):
            return s[:-length], s[-length:]
    return s, ""


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


def wait_for_wake(sox, wake_model, rolling_buffer):
    """Reads from the (already running) mic pipeline until "hey butter" is
    detected, continuously maintaining rolling_buffer as the trailing
    ROLLING_BUFFER_SECONDS of audio."""
    wake_model.reset()
    while True:
        chunk = read_chunk(sox)
        if chunk is None:
            raise RuntimeError("mic pipeline died")
        rolling_buffer.append(chunk)
        predictions = wake_model.predict(chunk)
        for name, score in predictions.items():
            if score >= WAKE_THRESHOLD:
                print(f"  wake detected: {name} confidence={score:.3f}")
                return


def capture_utterance(sox, rolling_buffer):
    """Seeds the utterance buffer with whatever was just in rolling_buffer
    (the carried-over pre-wake audio) and keeps reading from the same live
    pipeline until ~1s of silence follows detected speech, or
    MAX_UTTERANCE_CHUNKS new chunks is hit. Returns a float32 array
    normalized to [-1, 1] at 16kHz mono."""
    chunks = list(rolling_buffer)
    rolling_buffer.clear()

    speech_chunks = 0
    silence_chunks = 0
    speech_started = False
    rms_values = []  # diagnostic only, to help tune SILENCE_RMS_THRESHOLD
    for _ in range(MAX_UTTERANCE_CHUNKS):
        chunk = read_chunk(sox)
        if chunk is None:
            break
        chunks.append(chunk)

        rms = np.sqrt(np.mean(chunk.astype(np.float64) ** 2))
        rms_values.append(rms)
        if rms >= SILENCE_RMS_THRESHOLD:
            speech_chunks += 1
            silence_chunks = 0
            if speech_chunks >= MIN_SPEECH_CHUNKS:
                speech_started = True
        elif speech_started:
            silence_chunks += 1
            if silence_chunks >= SILENCE_CHUNKS_TO_STOP:
                break

    if rms_values:
        above = sum(1 for v in rms_values if v >= SILENCE_RMS_THRESHOLD)
        print(f"  vad: {len(rms_values)} new chunks, rms min={min(rms_values):.0f} "
              f"max={max(rms_values):.0f} mean={sum(rms_values)/len(rms_values):.0f} "
              f"(threshold={SILENCE_RMS_THRESHOLD}, {above}/{len(rms_values)} above)")

    pcm16 = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.int16)
    return pcm16.astype(np.float32) / 32768.0


def stream_and_speak(client, transcript):
    """Streams the Brain's response (per project convention: always stream
    LLM API calls) and speaks each completed sentence as soon as it's
    available, instead of waiting for the full response before saying
    anything. Returns (full_text, finish_reason, spoke_anything, timing)
    where timing holds zero-overhead time.monotonic() checkpoints only -
    no added sleeps/blocking beyond the TTS playback that would happen
    anyway, so instrumenting this doesn't change the conversation's actual
    behavior or pacing.

    deepseek-v4-pro is a reasoning model: by default it streams
    reasoning_content before content, and reasoning tokens count against
    max_tokens - a long reasoning trace can exhaust the budget before any
    <speak> content is emitted. Disabled here via extra_body (confirmed:
    drops completion_tokens from ~40-60 to ~9 and skips reasoning_content
    entirely), so the full MAX_SPEAK_TOKENS budget goes to visible text.
    finish_reason is still checked as a safety net in case that changes.
    """
    t_start = time.monotonic()
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
    spoke_anything = False
    time_to_first_token = None
    time_to_first_audio = None
    tts_total = 0.0

    raw_tail = ""      # unprocessed raw text (may contain partial tags)
    inside_speak = False
    pending = ""        # text inside the current <speak> block not yet spoken

    def flush(text):
        nonlocal spoke_anything, time_to_first_audio, tts_total
        text = text.strip()
        if not text:
            return
        if time_to_first_audio is None:
            time_to_first_audio = time.monotonic() - t_start
        print(f"  butter says: {text}")
        t0 = time.monotonic()
        speak(text)
        tts_total += time.monotonic() - t0
        spoke_anything = True

    for event in stream:
        delta = event.choices[0].delta.content
        if event.choices[0].finish_reason:
            finish_reason = event.choices[0].finish_reason
        if not delta:
            continue
        if time_to_first_token is None:
            time_to_first_token = time.monotonic() - t_start
        full_text += delta
        raw_tail += delta

        while True:
            if not inside_speak:
                idx = raw_tail.find("<speak>")
                if idx == -1:
                    break
                raw_tail = raw_tail[idx + len("<speak>"):]
                inside_speak = True
            else:
                # Search the closing tag across pending+raw_tail combined,
                # not raw_tail alone - the tag can be split across stream
                # chunks (e.g. one delta ends in "<", the next starts with
                # "/speak>"), and searching raw_tail in isolation would
                # miss it entirely once a partial prefix leaks into pending.
                combined = pending + raw_tail
                raw_tail = ""
                end_idx = combined.find("</speak>")
                if end_idx == -1:
                    safe, held = _split_partial_tag_suffix(combined, "</speak>")
                    split_at = 0
                    for m in SENTENCE_END_RE.finditer(safe):
                        split_at = m.end()
                    if split_at > 0:
                        flush(safe[:split_at])
                        pending = safe[split_at:] + held
                    else:
                        pending = safe + held
                    break
                else:
                    spoken_part = combined[:end_idx]
                    raw_tail = combined[end_idx + len("</speak>"):]
                    inside_speak = False
                    flush(spoken_part)
                    pending = ""

    response_total = time.monotonic() - t_start  # includes interleaved TTS playback
    timing = {
        "brain_first_token": time_to_first_token,
        "tts_first_audio": time_to_first_audio,
        "tts_total": tts_total,
        "response_total": response_total,
    }
    return full_text, finish_reason, spoke_anything, timing


def main():
    print("Butter conversation pipeline test")
    print("Loading models...")

    wake_model = WakeWordModel(wakeword_models=[WAKE_MODEL_PATH], inference_framework="onnx")
    whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    brain = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    butter_audio._get_voice()  # forces Piper's model to warm-load now (~1.5s),
                                # not silently inside the first turn's first sentence

    print("Say \"hey butter\", then speak. Ctrl+C to quit.\n")

    history = {
        "wake": [], "stt": [],
        "brain_first_token": [], "tts_first_audio": [], "response_total": [],
        "total": [],
    }

    rolling_buffer = deque(maxlen=ROLLING_BUFFER_CHUNKS)
    arecord, sox = start_mic_pipeline()
    try:
        while True:
            print("Listening for \"hey butter\"...")
            t_wake_start = time.monotonic()
            wait_for_wake(sox, wake_model, rolling_buffer)
            wake_latency = time.monotonic() - t_wake_start

            print("Listening...")
            t_record_start = time.monotonic()
            audio = capture_utterance(sox, rolling_buffer)
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

            response_text, finish_reason, spoke_anything, timing = stream_and_speak(brain, transcript)
            if not spoke_anything:
                if finish_reason == "length":
                    print(f"  (hit MAX_SPEAK_TOKENS={MAX_SPEAK_TOKENS} before any <speak> content - "
                          "reasoning consumed the budget, try again)\n")
                else:
                    print(f"  (brain returned nothing to say - raw: {response_text!r})\n")
                continue

            total_latency = stt_latency + timing["response_total"]

            history["wake"].append(wake_latency)
            history["stt"].append(stt_latency)
            history["brain_first_token"].append(timing["brain_first_token"] or 0.0)
            history["tts_first_audio"].append(timing["tts_first_audio"] or 0.0)
            history["response_total"].append(timing["response_total"])
            history["total"].append(total_latency)

            def avg(key):
                vals = history[key]
                return sum(vals) / len(vals)

            print(f"  latency: wake={wake_latency:.2f}s  recording={recording_duration:.2f}s  "
                  f"stt={stt_latency:.2f}s  brain_first_token={timing['brain_first_token']:.2f}s  "
                  f"tts_first_audio={timing['tts_first_audio']:.2f}s  "
                  f"response(brain+tts)={timing['response_total']:.2f}s  "
                  f"total(stt+response)={total_latency:.2f}s")
            print(f"  running avg over {len(history['total'])} turn(s): "
                  f"stt={avg('stt'):.2f}s  brain_first_token={avg('brain_first_token'):.2f}s  "
                  f"tts_first_audio={avg('tts_first_audio'):.2f}s  "
                  f"response={avg('response_total'):.2f}s  total={avg('total'):.2f}s\n")
    finally:
        stop_mic_pipeline(arecord, sox)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
