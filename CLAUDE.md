# Butter — Project Context

Home robot built on NVIDIA Jetson Orin Nano Super. Python project.
Repo: https://github.com/Kevindo001/butter_bot
venv: butter_env (always activate before running anything)

## Architecture

Wake word (OpenWakeWord) -> STT (Whisper) -> Brain (DeepSeek V4 Pro) -> TTS (espeak)
Vision: Jetson Inference + TensorRT + OpenCV

## Audio constraints

- BUTTER_MIC (SABRENT): capture only, 44100 or 48000 Hz. Downsample to 16000 via sox for Whisper/OpenWakeWord.
- BUTTER_SPEAKER (C-Media): playback only, stereo S16_LE, 44100 or 48000 Hz only. Always pipe espeak through sox.
- TTS command: espeak --stdout | sox -t wav - -t wav -r 44100 -c 2 - | aplay -D hw:2,0

## espeak voice config

-v en-us+m5 -s 210 -p 75 -k 10 -a 200

## GPIO pin map (confirmed working)

Left Front  -> pins 11, 13
Left Rear   -> pins 16, 15 (reversed order vs. other wheels - compensates for reversed wiring in software)
Right Front -> pins 33, 31
Right Rear  -> pins 29, 18
Forward = IN2 HIGH, IN1 LOW
Pinmux permanent via butter-pinmux.service systemd
Motor script: ~/Projects/butter/test/06_test_motors.py
Run: sudo /home/anhdo001/Projects/butter/butter_env/bin/python3 test/06_test_motors.py

## Wake word

Model: ~/Projects/butter/models/hey_butter.onnx
Framework: OpenWakeWord
Threshold: 0.5
Capture at 44100 via arecord, downsample to 16000 via sox before feeding to model

## Motor math

move_forward/backward: duration = distance_mm / 712
rotate: arc_length = pi x 125 x (degrees / 360), duration = arc_length / 712

## Git practices

- Branch for every feature: git checkout -b feat/feature-name
- Commit often with conventional commits
- Never commit .env, models/*.onnx, cache/, butter_env/
- Push to origin after every working milestone
- main branch = stable only

## Package management

- requirements.txt must always reflect exactly what's installed in butter_env, pinned to the installed version (pip freeze, one line per package).
- Update requirements.txt in the same commit whenever a package is added, upgraded, downgraded, or removed. Never let it drift from butter_env.

## Project structure

config/     hardware specs, voice config, motor wiring
docs/       tool definitions, architecture notes
prompts/    system prompt lives here
src/        all Python source files
models/     ONNX wake word model (gitignored)
test/       hardware test scripts
cache/      runtime cache (gitignored)

## Environment

All keys in .env, loaded via python-dotenv. Never hardcode.
DEEPSEEK_API_KEY, ESPEAK_VOICE, ESPEAK_SPEED, ESPEAK_PITCH, ESPEAK_CAPITALS, ESPEAK_AMPLITUDE
