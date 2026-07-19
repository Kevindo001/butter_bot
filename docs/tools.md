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

## follow_me (implemented, NOT yet reachable by voice — see status below)

- **What it does:** (1) Checks the current frame for the enrolled face. (2) If not found, rotates right in `SCAN_STEP_DEGREES` (30°) steps up to `SCAN_MAX_STEPS` (12, i.e. a full 360°), re-checking `find_person()` after each step. (3) If still not found, speaks "Can't find you, come to me" and returns. (4) Once found, locks a ReID signature — an HSV color histogram (`REID_HIST_BINS`=8/channel) of the **upper `REID_UPPER_BODY_FRACTION`=60%** of whichever SSD person-detector box contains the enrolled face (not the face crop itself — a face-only signature correlated poorly, 0.26–0.54, against full-body candidate boxes; upper-body-vs-upper-body correlates 0.85–0.99, verified live) — and speaks "On my way". (5) Runs a `FOLLOW_LOOP_HZ`=5 loop using `_reid_match()` (not `find_person()` — face recognition takes ~2s/frame at 1080p, far too slow for continuous tracking) to stay centered within `CENTER_DEADZONE`=50px and hold `TARGET_DISTANCE_BB_HEIGHT`=200px bounding-box height, taking small corrective steps (`ROTATE_STEP_DEGREES`=10°, `APPROACH_STEP_MM`=100mm) per iteration. (6) Stops and speaks "I lost you, say follow me again" if `_reid_match` returns nothing for more than `LOST_TIMEOUT_S`=3.0s.
- **Input:** `verbose` (bool, default False) — prints every decision (scan steps, matches, offsets, which motor call is issuing). `on_frame` (callable, default None) — called once per follow-loop iteration as `on_frame(preview_frame, match, offset, bb_height, action)` for a caller to visualize the loop's state (e.g. draw the match box on a debug stream) without `follow_me()` needing to know about streaming.
- **Output:** none
- **Person detection:** `_detect_person_boxes()` uses an SSD MobileNetV1 ONNX model (COCO-trained, class id 1 = person) at `models/ssd_mobilenet/ssd_mobilenet_v1_12.onnx` (gitignored via the existing `models/**/*.onnx` pattern) via `cv2.dnn.readNetFromONNX`. **Not** `cv2.HOGDescriptor`/`cv2.CascadeClassifier` as originally planned — this OpenCV build (`opencv-python-headless` 5.0.0) doesn't have either (OpenCV 5.x's headless wheel dropped the classic objdetect detectors entirely), and `cv2.dnn.readNetFromCaffe` isn't available either (this build's `dnn` module only loads ONNX/TFLite/TensorFlow/OpenVINO-IR) — hence sourcing an ONNX model from the official ONNX Model Zoo instead of the originally-planned Caffe MobileNet-SSD.
- **Status — what's missing to make this voice-triggered:** `follow_me` is **not** in `TOOL_REGISTRY` (`src/butter_tools.py`), and `parse_action()`/`dispatch()` in that same file are still `raise NotImplementedError` — there is no code yet that turns *any* Brain `<action>` tag into an actual function call. `prompts/system_prompt.txt` doesn't list `follow_me` as a tool. `test/conversation_test.py` (the one real conversation-pipeline test) explicitly disables `<action>` tags entirely. So: the vision/tracking logic is built and verified, but "hey butter, follow me" does nothing today — someone still needs to (1) implement `parse_action`/`dispatch`, (2) add `follow_me` to `TOOL_REGISTRY` and `prompts/system_prompt.txt`, (3) wire `conversation_test.py` (or its successor) to actually call `dispatch()` on parsed actions.
- **Stopping it:** `request_follow_stop()` sets a module-level `threading.Event` that the follow loop checks each iteration — but **nothing calls it yet** (it's a hook for the state-machine/interrupt layer needed for "stop" to work as a voice command mid-action, which doesn't exist in this codebase). Until that exists, the only ways to stop a running `follow_me()` are: losing the person for >3s (auto-stops + speaks), killing the process, or `test/kill_motors.py` (below).
- **Manual test tooling (no voice/dispatcher involved):**
  - `test/test_follow_me_motors.py` — calls `follow_me(verbose=True, on_frame=...)` directly, drives the real motors. Starts a debug MJPEG stream (via `test/_live_preview.py`'s `frame_source` hook, reusing `stream_start()`'s already-open camera rather than a conflicting second capture) with the current match box/action drawn on it. Ctrl+C calls `motor_stop()` immediately, then `request_follow_stop()`.
  - `test/kill_motors.py` — standalone emergency kill switch, run from any other terminal: `sudo /home/anhdo001/Projects/butter/butter_env/bin/python3 test/kill_motors.py`. Writes all motor pins LOW directly via GPIO, independent of whatever else is running (GPIO writes aren't exclusive to one process) — but doesn't stop a still-running `follow_me()` from driving them again a moment later; it's the instant "pins off now" tool, not a process-kill.
  - Neither of the above has been run yet with real motors — `follow_me()`'s vision/ReID components are verified live; its motor-driving path is written but untested.

## TBD / planned

Tools not yet implemented — add a section above and remove from here once built. Stub signatures exist in `src/` but every one below currently raises `NotImplementedError`:

- `find_object(label)` (`src/butter_camera.py`) — locate a named object in the current camera view
- `get_calendar_events()` (`src/butter_calendar.py`) — not wired to a calendar provider; `prompts/system_prompt.txt` should keep declining calendar requests until this exists
- `create_calendar_event(title, start_time)` (`src/butter_calendar.py`)
- `read_memory()` / `save_memory(content)` (`src/butter_memory.py`)
- `search_query(query)` (`src/butter_search.py`)
- Speaker verification (SpeechBrain) — identify who is speaking before acting on a command (no stub yet)
