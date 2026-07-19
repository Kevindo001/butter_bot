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

- Backend: `faster-whisper` (ctranslate2), model size `base` by default.
- `ctranslate2` 4.8.1 compiled from source with CUDA+cuDNN support (`-DWITH_CUDA=ON -DWITH_CUDNN=ON -DCMAKE_CUDA_ARCHITECTURES=87`, Orin's compute capability, CUDA 12.6), then installed system-wide via `sudo make install` + `ldconfig` (`libctranslate2.so` lives under `/usr/local/lib`, not bundled in `butter_env`) with the Python bindings installed into `butter_env` on top. Replaces the CPU-only PyPI aarch64 wheel — `device="cuda"` now works.
- Verify: `python3 -c "import ctranslate2; print(ctranslate2.get_cuda_device_count())"` → `1`
- GPU vs CPU latency comparison across tiny.en/base/small: `test/whisper_gpu_benchmark.py`
- Original CPU-only latency/accuracy test: `test/whisper_latency_test.py` (note: its "no CUDA support" comment predates the from-source rebuild above and is now stale)

## Face Recognition

- Backend: `dlib` (via the `face-recognition` PyPI package), used by `find_person()` in `src/butter_camera.py`.
- `dlib` 20.0.99 compiled from source with CUDA support (`DLIB_USE_CUDA=True`, targeting sm_87) and installed into `butter_env` — replaces the CPU-only PyPI wheel.
- Verify: `python3 -c "import dlib; print(dlib.DLIB_USE_CUDA, dlib.cuda.get_num_devices())"` → `True 1`

## Camera

- USB camera, consumed via OpenCV / Jetson Inference + TensorRT for vision
- No fixed resolution/fps constraint documented yet — confirm and update here once vision pipeline is built
