# Architecture

Butter is organized as a 5-layer stack. Audio and vision are independent input paths that both feed the Brain layer, which is the only layer that decides what happens next.

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. WAKE WORD                                                     │
│    OpenWakeWord, model: models/hey_butter.onnx, threshold 0.5    │
│    Listens continuously on BUTTER_MIC (downsampled to 16000 Hz)  │
└───────────────────────────────┬───────────────────────────────────┘
                                 │ wake event
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. STT (Speech-to-Text)                                          │
│    Whisper                                                       │
│    Transcribes the utterance following the wake word              │
└───────────────────────────────┬───────────────────────────────────┘
                                 │ text
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. BRAIN                                                          │
│    DeepSeek V4 Pro                                                │
│    Reasons over transcript + tool results, decides what to say    │
│    and/or do, emits <speak> and <action> blocks                   │
└───────────┬─────────────────────────────────────┬─────────────────┘
            │ <speak>                             │ <action>
            ▼                                      ▼
┌───────────────────────────┐        ┌───────────────────────────────┐
│ 4. TTS (Text-to-Speech)    │        │ 5. VISION / ACTUATION          │
│    Piper -> sox -> aplay   │        │    Jetson Inference + TensorRT │
│    Speaks on BUTTER_SPEAKER│        │    + OpenCV for perception;    │
│                             │        │    GPIO/L298N for movement     │
└───────────────────────────┘        └───────────────────────────────┘
```

## Layer notes

1. **Wake word** — always-on, lightweight, runs locally. Only job is to trigger STT; never touches the Brain directly.
2. **STT** — one-shot per wake event. Converts the post-wake utterance to text for the Brain.
3. **Brain** — the only decision-making layer. Consumes transcript and any tool/vision output, produces a response constrained to `<speak>`/`<action>` tags (see `prompts/system_prompt.txt`). Calls tools as needed (see `docs/tools.md`).
4. **TTS** — renders `<speak>` content to audio. Every utterance goes through the sox resample step, no exceptions (see `config/voice.md`).
5. **Vision / Actuation** — handles `<action>` content: camera perception (OpenCV/TensorRT) and physical movement (GPIO → L298N → motors, see `config/motor.md`).

## Action dispatch

`<action>` blocks emitted by the Brain are parsed and routed by `src/butter_tools.py`, the central dispatcher. It imports every tool function from the category modules — `src/butter_motors.py` (movement), `src/butter_camera.py` (vision), `src/butter_calendar.py`, `src/butter_memory.py`, `src/butter_search.py` — into a single `TOOL_REGISTRY`, and calls the matching function for each parsed action. `<speak>` blocks bypass this entirely and go straight to layer 4 (TTS).

## Data flow constraints

- All mic audio is 44100 Hz at capture, downsampled to 16000 Hz before it reaches Wake Word or STT.
- All speaker audio is resampled to 44100 Hz stereo before it reaches BUTTER_SPEAKER.
- The Brain never talks to hardware directly — it only emits `<speak>`/`<action>` intents that layers 4 and 5 execute.
