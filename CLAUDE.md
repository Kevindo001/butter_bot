# Butter — Project Context

Home robot built on NVIDIA Jetson Orin Nano Super. Python project.
Repo: https://github.com/Kevindo001/butter_bot
venv: butter_env (always activate before running anything)

## Architecture

Wake word (OpenWakeWord) -> STT (Whisper) -> Brain (DeepSeek V4 Pro) -> TTS (Piper)
Vision: Jetson Inference + TensorRT + OpenCV

Brain -> tool execution is NOT wired yet: `src/butter_tools.py`'s `parse_action()`/`dispatch()` are still stubs, so no `<action>` tag actually calls anything regardless of what's in `TOOL_REGISTRY` or `prompts/system_prompt.txt`. `test/conversation_test.py` (the one real conversation-pipeline test) disables `<action>` tags entirely. See `docs/tools.md` for what's built vs. reachable per tool.

## GPU acceleration

- dlib 20.0.99: compiled from source with CUDA support (sm_87, Orin Nano Super's compute capability), installed into butter_env. Replaces the CPU-only PyPI wheel — find_person()/face_recognition now run on GPU. Verify: `python3 -c "import dlib; print(dlib.DLIB_USE_CUDA, dlib.cuda.get_num_devices())"` -> True 1
- ctranslate2 4.8.1: compiled from source with CUDA+cuDNN support (CUDA 12.6, sm_87), installed system-wide via `sudo make install` + `ldconfig` (libctranslate2.so under /usr/local/lib, not bundled in butter_env), Python bindings installed into butter_env on top. faster-whisper can now run on GPU via device="cuda". Verify: `python3 -c "import ctranslate2; print(ctranslate2.get_cuda_device_count())"` -> 1
- Full detail: config/specs.md (STT, Face Recognition sections). GPU vs CPU benchmark: test/whisper_gpu_benchmark.py

## Audio constraints

- BUTTER_MIC (SABRENT): capture only, 44100 or 48000 Hz. Downsample to 16000 via sox for Whisper/OpenWakeWord.
- BUTTER_SPEAKER (C-Media): playback only, stereo S16_LE, 44100 or 48000 Hz only. Always pipe Piper through sox.
- TTS command: piper --model models/piper/en_US-lessac-medium.onnx --output_raw | sox -t raw -r 22050 -e signed -b 16 -c 1 - -t wav -r 44100 -c 2 - | aplay -D hw:2,0
- TTS module: src/butter_audio.py (speak(text, volume=None))

## Piper voice config

Model: models/piper/en_US-lessac-medium.onnx (gitignored, see config/voice.md for download steps)
Native output: 22050 Hz mono S16LE raw PCM
Volume: multiplier via --volume, default 1.0 (see PIPER_VOLUME in .env)

espeak was removed (2026-07-17) — Piper sounds more natural and espeak is no longer used anywhere in this repo. See config/voice.md for the removal note.

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
DEEPSEEK_API_KEY, PIPER_BIN, PIPER_MODEL_PATH, PIPER_SAMPLE_RATE, PIPER_VOLUME
