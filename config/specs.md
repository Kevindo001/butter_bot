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
- Background capture thread (`stream_start()` in `src/butter_camera.py`) publishes two resolutions to `world_state`: `"full"` at native 1920x1080, `"preview"` at 320x240. **Must force MJPG** (`cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))`) before setting 1080p — without it, the driver falls back to raw YUYV at that resolution, which overruns USB2 bandwidth and **segfaults the whole process** after a few frames once read continuously from a background thread (confirmed by repro: a single one-off read at 1080p works fine without MJPG; repeated reads in a thread crash within ~3 frames; MJPG fixes it). 720p/480p work fine without forcing MJPG.
- This OpenCV build (`opencv-python-headless` 5.0.0) is missing APIs a lot of tutorials assume exist: no `cv2.HOGDescriptor`, no `cv2.CascadeClassifier` (OpenCV 5.x's headless wheel dropped the classic objdetect detectors), and `cv2.dnn.readNetFromCaffe` doesn't exist either (this build's `dnn` module only loads ONNX/TFLite/TensorFlow/OpenVINO-IR). Verify any assumed cv2 API actually exists in this build before relying on it (`python3 -c "import cv2; print(hasattr(cv2, 'X'))"`) rather than trusting a tutorial or spec written against a different OpenCV version.
- Person detection (used by `follow_me()`'s ReID tracking, see `docs/tools.md`) uses an ONNX Model Zoo SSD MobileNetV1 model (COCO-trained) at `models/ssd_mobilenet/ssd_mobilenet_v1_12.onnx` via `cv2.dnn.readNetFromONNX` — chosen because of the above Caffe/HOG gaps. Loading it is slow (~20s) on first use; `src/butter_camera.py` loads it eagerly at module import time instead of lazily so that cost is paid once at process start, not on the first real detection.
