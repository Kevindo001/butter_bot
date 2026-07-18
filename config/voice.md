# Voice Config

## Audio devices

| Role     | Device                          | ALSA card | Direction |
|----------|----------------------------------|-----------|-----------|
| Mic      | BUTTER_MIC (SABRENT USB PnP)     | confirm via `arecord -l` | capture only |
| Speaker  | BUTTER_SPEAKER (C-Media USB)     | hw:2,0    | playback only |

Card indices are not guaranteed stable across reboots on Jetson — verify with `aplay -l` / `arecord -l` if audio breaks after a reboot or USB replug, and update the hw:X,Y references here and in code if they shift.

## espeak voice

```
-v en-us+m5 -s 210 -p 75 -k 10 -a 200
```

| Flag | Meaning        | Value   |
|------|----------------|---------|
| -v   | voice          | en-us+m5 |
| -s   | speed (wpm)    | 210     |
| -p   | pitch          | 75      |
| -k   | capitals emphasis | 10   |
| -a   | amplitude      | 200     |

Configurable via `.env`: `ESPEAK_VOICE`, `ESPEAK_SPEED`, `ESPEAK_PITCH`, `ESPEAK_CAPITALS`, `ESPEAK_AMPLITUDE`.

## TTS pipeline

BUTTER_SPEAKER only accepts 44100/48000 Hz stereo S16_LE, so espeak's raw output is always resampled through sox before playback:

```
espeak --stdout | sox -t wav - -t wav -r 44100 -c 2 - | aplay -D hw:2,0
```

- `espeak --stdout` — synthesize to WAV on stdout
- `sox -t wav - -t wav -r 44100 -c 2 -` — resample to 44100 Hz, force stereo
- `aplay -D hw:2,0` — play directly to BUTTER_SPEAKER

## TTS candidate: Piper

Evaluated as a more natural-sounding alternative to espeak. Not yet wired into the app — verified standalone via `test/piper_test.py`.

Setup (model files are gitignored, `.onnx`/`.onnx.json` under `models/**`):

```
pip install piper-tts
mkdir -p models/piper
cd models/piper
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
```

Native output is 22050 Hz mono S16LE raw PCM (per the model's `.onnx.json` `audio.sample_rate`), resampled to BUTTER_SPEAKER's 44100 Hz stereo the same way as espeak:

```
piper --model models/piper/en_US-lessac-medium.onnx --output_raw | \
  sox -t raw -r 22050 -e signed -b 16 -c 1 - -t wav -r 44100 -c 2 - | \
  aplay -D hw:2,0
```

If this sounds good, the plan is to replace espeak with Piper in `butter_audio.py` and point `.env` at the model path.

## STT capture pipeline

BUTTER_MIC only captures at 44100/48000 Hz, but Whisper and OpenWakeWord need 16000 Hz mono:

```
arecord -D <mic_device> -f S16_LE -r 44100 -c 1 | sox -t wav - -t wav -r 16000 -c 1 -
```

Confirm `<mic_device>` with `arecord -l` and record it in the table above once known.
