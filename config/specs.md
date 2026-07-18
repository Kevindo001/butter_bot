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
- All TTS output (espeak) must be piped through sox to match this format before aplay
- See [[voice.md]] for the exact pipeline command

## GPIO

- Physical (BOARD) pin numbering used throughout, not BCM
- Pinmux configuration is not persistent across reboots by default on Jetson — made permanent via the `butter-pinmux.service` systemd unit
- Full pin map and motor wiring: see [[motor.md]]
- Any script that imports `Jetson.GPIO` must be run with the venv Python, never bare `sudo python3`. The system-wide `python3-jetson-gpio` apt package (2.1.7) does not recognize this board's device-tree compatible string `nvidia,p3768-0000+p3767-0005-super` (the `-super` suffix from Super mode) and raises `Could not determine Jetson model`. The venv's `Jetson.GPIO` (2.1.12, in `butter_env`) already includes `-super` in its compat list.
  - Run as: `sudo /home/anhdo001/Projects/butter/butter_env/bin/python3 script.py`
  - If native extensions need shared libs from the venv, preserve env: `sudo -E LD_LIBRARY_PATH=/home/anhdo001/Projects/butter/butter_env/lib/python3.10/site-packages/nvidia/cusparselt/lib:$LD_LIBRARY_PATH /home/anhdo001/Projects/butter/butter_env/bin/python3 script.py`

## Camera

- USB camera, consumed via OpenCV / Jetson Inference + TensorRT for vision
- No fixed resolution/fps constraint documented yet — confirm and update here once vision pipeline is built
