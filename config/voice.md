# Voice Config

## Audio devices

| Role     | Device                          | ALSA card | Direction |
|----------|----------------------------------|-----------|-----------|
| Mic      | BUTTER_MIC (SABRENT USB PnP)     | confirm via `arecord -l` | capture only |
| Speaker  | BUTTER_SPEAKER (C-Media USB)     | hw:2,0    | playback only |

Card indices are not guaranteed stable across reboots on Jetson — verify with `aplay -l` / `arecord -l` if audio breaks after a reboot or USB replug, and update the hw:X,Y references here and in code if they shift.

## TTS: Piper (active)

Wired into the app via `src/butter_audio.py` (`speak(text, volume=None)`).

Setup (model files are gitignored, `.onnx`/`.onnx.json` under `models/**`):

```
pip install piper-tts
mkdir -p models/piper
cd models/piper
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
```

Native output is 22050 Hz mono S16LE raw PCM (per the model's `.onnx.json` `audio.sample_rate`), resampled to BUTTER_SPEAKER's 44100 Hz stereo the same way espeak used to be. The CLI pipe below is illustrative of the audio format/flow, but `src/butter_audio.py` does **not** actually shell out to the `piper` CLI - see the warm-load note below:

```
piper --model models/piper/en_US-lessac-medium.onnx --output_raw --volume 1.0 | \
  sox -t raw -r 22050 -e signed -b 16 -c 1 - -t wav -r 44100 -c 2 - | \
  aplay -D hw:2,0
```

`--volume` is a multiplier (default 1.0), configurable via `PIPER_VOLUME` in `.env`. Tested with `test/volume_test.py` — enter a value, hear a phrase spoken at that volume.

Configurable via `.env`: `PIPER_MODEL_PATH`, `PIPER_VOLUME`. (`PIPER_BIN`/`PIPER_SAMPLE_RATE` are no longer read - see below.)

### Warm-loaded via the Python API, not the CLI (2026-07-17)

`test/conversation_test.py`'s streaming TTS calls `speak()` once per sentence instead of once per turn. That exposed a real cost: the original implementation spawned a fresh `piper` **subprocess** per call, and each spawn pays ONNX Runtime session init again - benchmarked at ~1.5s. For a 2-sentence response that's ~1.5s of dead air *between* sentences on top of the first sentence's load time - this was the exact "weird pause" reported when testing live.

Fixed by switching `src/butter_audio.py` to the `piper-tts` package's Python API (`from piper import PiperVoice, SynthesisConfig`) instead of the CLI: `PiperVoice.load(PIPER_MODEL_PATH)` runs once (lazily, on first `speak()` call, cached in a module global), and every subsequent `voice.synthesize(text)` is pure inference - benchmarked at ~0.1-0.25s per short sentence, no reload. `PIPER_BIN` and `PIPER_SAMPLE_RATE` are unused now (sample rate comes from the loaded model at runtime); `sox`/`aplay` are still invoked as subprocesses for resampling and playback, unchanged.

Measured effect on `test/conversation_test.py`'s 2-sentence-response `response_total` latency: **12.25s -> 4.44s** for a comparable response.

## espeak removed (2026-07-17)

Piper sounded more natural in an A/B listen test, so espeak was replaced everywhere: `src/butter_audio.py` now uses Piper exclusively, `test/speaker_test.py` (the espeak test) was deleted in favor of `test/piper_test.py`, and the `ESPEAK_*` vars are gone from `.env.example` in favor of `PIPER_*`. The `espeak`/`espeak-ng` apt packages (~13MB, package list: `espeak`, `espeak-data`, `espeak-ng-data`, `libespeak-ng1`, `libespeak1`, `speech-dispatcher-espeak-ng`) are no longer used by this project — `speech-dispatcher-espeak-ng` is a general Linux accessibility component, not butter-specific, so removing it system-wide was left as a manual step rather than done automatically.

## STT capture pipeline

BUTTER_MIC only captures at 44100/48000 Hz, but Whisper and OpenWakeWord need 16000 Hz mono:

```
arecord -D <mic_device> -f S16_LE -r 44100 -c 1 | sox -t wav - -t wav -r 16000 -c 1 -
```

Confirm `<mic_device>` with `arecord -l` and record it in the table above once known.
