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

## What we use

- Wake word: OpenWakeWord (hey_butter.onnx)
- STT: Whisper
- Brain: DeepSeek V4 Pro
- Speaker verification: SpeechBrain
- Vision: Jetson Inference + TensorRT + OpenCV
- TTS: espeak -> sox -> aplay


---

Built by Anh Do and Carter Pade
