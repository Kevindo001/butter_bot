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

## capture_image

- **What it does:** Grabs a single frame from the USB camera for the vision pipeline (OpenCV / Jetson Inference + TensorRT).
- **Input:** none
- **Output:** image frame (format TBD once vision pipeline is implemented)

## TBD / planned

Tools not yet implemented — add a section above and remove from here once built. Stub signatures exist in `src/` but every one below currently raises `NotImplementedError`:

- `find_person()` (`src/butter_camera.py`) — locate a person in the current camera view
- `find_object(label)` (`src/butter_camera.py`) — locate a named object in the current camera view
- `get_world_state()` (`src/butter_camera.py`) — structured summary of detected people/objects for the Brain
- `stream_start()` (`src/butter_camera.py`) — start a live video stream
- `get_calendar_events()` (`src/butter_calendar.py`) — not wired to a calendar provider; `prompts/system_prompt.txt` should keep declining calendar requests until this exists
- `create_calendar_event(title, start_time)` (`src/butter_calendar.py`)
- `read_memory()` / `save_memory(content)` (`src/butter_memory.py`)
- `search_query(query)` (`src/butter_search.py`)
- Speaker verification (SpeechBrain) — identify who is speaking before acting on a command (no stub yet)
