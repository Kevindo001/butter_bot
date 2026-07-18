# Butter

A home robot built on the NVIDIA Jetson Orin Nano Super. Butter listens, thinks, sees, and moves.

> Status: Under active construction. Not production ready.

---

## Hardware

- NVIDIA Jetson Orin Nano Super (8GB)
- Mecanum wheels x 4
- 2x L298N motor drivers
- 3S LiPo with EC5 Y-harness
- USB camera
- BUTTER_MIC (SABRENT USB PnP Sound Device) — microphone input
- BUTTER_SPEAKER (C-Media USB Audio Device) — speaker output

## Audio Constraints

- BUTTER_MIC captures at 44100 or 48000 Hz only. OpenWakeWord and Whisper require 16000 Hz input, so all mic audio is downsampled via sox before processing.
- BUTTER_SPEAKER only accepts 44100 or 48000 Hz stereo S16_LE. All TTS output must be resampled via sox before playback or it will not work.

## Stack

- Wake word: OpenWakeWord (hey_butter.onnx)
- STT: Whisper
- Brain: DeepSeek V4 Pro
- Speaker verification: SpeechBrain
- Vision: Jetson Inference + TensorRT + OpenCV
- TTS: Piper -> sox -> aplay

## Repo Structure

butter/
├── config/         hardware specs, voice config, motor wiring
├── docs/           tool definitions and architecture notes
├── prompts/        system prompt
├── src/            all Python source
│   ├── butter_audio.py     Piper TTS (speak)
│   ├── butter_motors.py    movement tools: move_forward, move_backward, rotate_left, rotate_right, stop
│   ├── butter_camera.py    vision tools: capture_image + stubs (find_person, find_object, get_world_state, stream_start)
│   ├── butter_calendar.py  calendar tools (stub, not wired to a provider yet)
│   ├── butter_memory.py    memory tools (stub)
│   ├── butter_search.py    web search tools (stub)
│   └── butter_tools.py     central dispatcher — parses <action> tags, routes to the modules above
├── models/         ONNX wake word model
├── test/           hardware test scripts
└── cache/          runtime cache (gitignored)

## Setup

git clone https://github.com/Kevindo001/butter_bot.git butter
cd butter
python3 -m venv butter_env
source butter_env/bin/activate
pip install -r requirements.txt
cp .env.example .env

## Environment Variables

See .env.example for required keys. Never commit .env.

---

Built by Anh Do and Carter Pade
