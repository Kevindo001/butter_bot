# Hardware Specs

## Platform

- NVIDIA Jetson Orin Nano Super (8GB)
- Mecanum wheels x4
- 2x L298N motor drivers
- 3S LiPo battery, EC5 Y-harness
- USB camera

## Audio

### BUTTER_MIC (SABRENT USB PnP Sound Device)

- Capture only
- Native rate: 44100 or 48000 Hz (device does not support 16000 Hz capture)
- OpenWakeWord and Whisper require 16000 Hz mono input
- Always downsample via sox before feeding audio to either model
- Capture with arecord at 44100 Hz, pipe through sox to convert to 16000 Hz

### BUTTER_SPEAKER (C-Media USB Audio Device)

- Playback only
- Accepts stereo S16_LE at 44100 or 48000 Hz only (no other rates, no mono)
- All TTS output (Piper) must be piped through sox to match this format before aplay
- See [[voice.md]] for the exact pipeline command and the espeak removal note

## GPIO

- Physical (BOARD) pin numbering used throughout, not BCM
- Pinmux configuration is not persistent across reboots by default on Jetson — made permanent via the `butter-pinmux.service` systemd unit
- Full pin map and motor wiring: see [[motor.md]]
- Any script that imports `Jetson.GPIO` must be run with the venv Python, never bare `sudo python3`. The system-wide `python3-jetson-gpio` apt package (2.1.7) does not recognize this board's device-tree compatible string `nvidia,p3768-0000+p3767-0005-super` (the `-super` suffix from Super mode) and raises `Could not determine Jetson model`. The venv's `Jetson.GPIO` (2.1.12, in `butter_env`) already includes `-super` in its compat list.
  - Run as: `sudo /home/anhdo001/Projects/butter/butter_env/bin/python3 script.py`
  - If native extensions need shared libs from the venv, preserve env: `sudo -E LD_LIBRARY_PATH=/home/anhdo001/Projects/butter/butter_env/lib/python3.10/site-packages/nvidia/cusparselt/lib:$LD_LIBRARY_PATH /home/anhdo001/Projects/butter/butter_env/bin/python3 script.py`

## STT

- Backend: `faster-whisper` (ctranslate2), model size `base`, running on **CPU** (`device="cpu", compute_type="int8"`) — not GPU yet.
- PyPI's `ctranslate2` wheel for aarch64/Jetson has no CUDA support: the aarch64 manylinux wheel is 16.6MB vs. 39.2MB for the CUDA-bundled x86_64 wheel, and neither lists bundled CUDA runtime deps. `device="cuda"` will not work with the pip-installed package.
- Getting real GPU execution requires building `ctranslate2` from source with `-DWITH_CUDA=ON -DWITH_CUDNN=ON -DCMAKE_CUDA_ARCHITECTURES=87` (Orin's compute capability). Build tools (cmake, g++, git) and cuDNN 9.3/CUDA 12.6 are already installed on this machine; expect roughly 30-90 min to build on 6 cores. Deferred — revisit when GPU STT is actually needed.
- Latency/accuracy test: `test/whisper_latency_test.py`

## Camera

- USB camera, consumed via OpenCV / Jetson Inference + TensorRT for vision
- No fixed resolution/fps constraint documented yet — confirm and update here once vision pipeline is built
