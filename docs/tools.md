# Tools

Tools the Brain (DeepSeek V4 Pro) can call via `<action>` blocks. Each tool below is grounded in a capability that already exists in `config/` — as `src/` is built out, keep this file in sync with the actual tool implementations and their exact function signatures.

Format: what it does, input, output.

## move_forward

- **What it does:** Drives all four wheels forward in a straight line for a computed duration.
- **Input:** `distance_mm` (number)
- **Output:** none (blocks until movement completes) — see `config/motor.md` for the `distance_mm / 712` timing formula.

## move_backward

- **What it does:** Drives all four wheels backward (IN1 HIGH / IN2 LOW) for a computed duration.
- **Input:** `distance_mm` (number)
- **Output:** none (blocks until movement completes)

## rotate_left

- **What it does:** Rotates the robot in place counterclockwise by a given angle (left wheels backward, right wheels forward).
- **Input:** `degrees` (number, positive)
- **Output:** none (blocks until movement completes) — see `config/motor.md` for the arc-length timing formula.

## rotate_right

- **What it does:** Rotates the robot in place clockwise by a given angle (right wheels backward, left wheels forward).
- **Input:** `degrees` (number, positive)
- **Output:** none (blocks until movement completes) — see `config/motor.md` for the arc-length timing formula.

## stop

- **What it does:** Immediately sets all motor pins LOW, halting movement.
- **Input:** none
- **Output:** none

## stream_start

- **What it does:** Starts a background daemon thread that continuously reads the USB camera (camera index 0, MJPG at 1920x1080 — raw YUYV at that resolution overruns USB2 bandwidth and crashes when read continuously, so the capture is forced to MJPG) and publishes frames to `world_state` at two resolutions: `"full"` (native 1080p, for `capture_image`/`find_person`) and `"preview"` (320x240, for fast per-frame tracking). Idempotent — calling it again while already running is a no-op. Never blocks or raises on a dropped frame, it just skips it.
- **Input:** none
- **Output:** none

## get_world_state

- **What it does:** Returns a snapshot dict of the latest frames published by `stream_start` (thread-safe copy). May be missing keys if `stream_start` hasn't produced a frame yet.
- **Input:** none
- **Output:** `{"full": ndarray, "preview": ndarray}` (keys may be absent early on)

## capture_image

- **What it does:** Starts the camera stream if not already running, then grabs the latest `"full"` frame from `world_state`. Three modes based on the flags:
  - Default (`send_to_telegram=False`): describes the frame via OpenAI vision (`gpt-4o-mini`) and returns the description to be spoken.
  - `send_to_telegram=True, analyze=False`: sends the raw photo to Telegram (`TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` from `.env`), no analysis.
  - `send_to_telegram=True, analyze=True`: describes via OpenAI vision, sends the photo to Telegram with the description as the caption.
- **Input:** `send_to_telegram` (bool, default False), `analyze` (bool, default False)
- **Output:** the OpenAI vision description (string), or `None` when only posting a raw photo to Telegram
- **Requires:** `OPENAI_API_KEY` in `.env` for the description path (already set, see `.env.example`)

## find_person

- **What it does:** Checks the latest `"full"` frame in `world_state` for a single enrolled face (`face-recognition` PyPI package, local dlib model — no LLM call), starting the camera stream if not already running.
- **Input:** none
- **Output:** `{"found": False}`, or `{"found": True, "confidence": float, "location": {"top", "right", "bottom", "left"}}` for the closest match under `FACE_MATCH_TOLERANCE` (0.5)
- **Requires:** `face-recognition` + `dlib` (in `requirements.txt`) and an enrolled face — run `test/enroll_face.py` once to create `models/anh_face.pkl` (gitignored, biometric data). Raises `RuntimeError` if that file doesn't exist yet.

## TBD / planned

Tools not yet implemented — add a section above and remove from here once built. Stub signatures exist in `src/` but every one below currently raises `NotImplementedError`:

- `find_object(label)` (`src/butter_camera.py`) — locate a named object in the current camera view
- `get_calendar_events()` (`src/butter_calendar.py`) — not wired to a calendar provider; `prompts/system_prompt.txt` should keep declining calendar requests until this exists
- `create_calendar_event(title, start_time)` (`src/butter_calendar.py`)
- `read_memory()` / `save_memory(content)` (`src/butter_memory.py`)
- `search_query(query)` (`src/butter_search.py`)
- Speaker verification (SpeechBrain) — identify who is speaking before acting on a command (no stub yet)
