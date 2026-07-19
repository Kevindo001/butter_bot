"""Camera and vision tools for Butter.

Covers everything that reads from the USB camera or the vision pipeline
(OpenCV / Jetson Inference + TensorRT): capturing frames, detecting people
or objects in view, summarizing world state for the Brain, and starting a
live video stream. See docs/tools.md and docs/architecture.md (layer 5)
for the contract each of these is expected to fulfill once implemented.
"""
import asyncio
import base64
import os
import pickle
import threading
import time

import cv2
import face_recognition
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Bot

try:
    from butter_motors import move_forward, rotate_left, rotate_right, stop as motor_stop
    from butter_audio import speak
except ImportError:
    # butter_camera is imported two different ways in this repo: test scripts
    # put src/ itself on sys.path (bare imports work), butter_tools.py imports
    # it as `src.butter_camera` (only `src.butter_motors` etc. resolve then).
    from src.butter_motors import move_forward, rotate_left, rotate_right, stop as motor_stop
    from src.butter_audio import speak

load_dotenv()

CAMERA_INDEX = 0
VISION_MODEL = "gpt-4o-mini"
ENROLLED_FACE_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "anh_face.pkl")
FACE_MATCH_TOLERANCE = 0.5
FULL_FRAME_SIZE = (1920, 1080)
PREVIEW_SIZE = (320, 240)
WORLD_STATE_TIMEOUT_S = 2.0

# Person detector for _reid_match: cv2.HOGDescriptor/CascadeClassifier don't
# exist in this OpenCV build (5.0 headless dropped the classic objdetect
# detectors), and cv2.dnn.readNetFromCaffe isn't available either (this
# build's dnn module only loads ONNX/TFLite/TensorFlow/OpenVINO-IR) - so this
# uses the ONNX Model Zoo's SSD MobileNetV1 (COCO-trained, class id 1 = person).
SSD_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "ssd_mobilenet", "ssd_mobilenet_v1_12.onnx")
SSD_INPUT_SIZE = (300, 300)
SSD_PERSON_CLASS_ID = 1
SSD_CONFIDENCE_THRESHOLD = 0.5

REID_HIST_BINS = 8
REID_MATCH_THRESHOLD = 0.5
REID_UPPER_BODY_FRACTION = 0.6  # top 60% of the person box - avoids legs/background clutter

SCAN_STEP_DEGREES = 30
SCAN_MAX_STEPS = 12  # 30 * 12 = 360 degrees
CENTER_DEADZONE = 50  # px, in the 320x240 preview frame
TARGET_DISTANCE_BB_HEIGHT = 200  # px, preview-frame bounding-box height
LOST_TIMEOUT_S = 3.0
FOLLOW_LOOP_HZ = 5
ROTATE_STEP_DEGREES = 10  # per-iteration corrective turn while off-center
APPROACH_STEP_MM = 100  # per-iteration corrective step while too far

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

_openai_client = None

_world_state = {}
_world_state_lock = threading.Lock()
_stream_thread = None
_follow_stop_event = threading.Event()

# Pre-loaded at import time so find_person()/_reid_match()'s first real call
# isn't the one paying dlib's / the ONNX loader's one-time warm-up cost.
_known_face_encodings = None
if os.path.exists(ENROLLED_FACE_PATH):
    with open(ENROLLED_FACE_PATH, "rb") as _f:
        _known_face_encodings = pickle.load(_f)

_dummy_frame = np.zeros((64, 64, 3), dtype="uint8")
face_recognition.face_locations(_dummy_frame)
face_recognition.face_encodings(_dummy_frame, known_face_locations=[(0, 64, 64, 0)])

_person_detector = cv2.dnn.readNetFromONNX(SSD_MODEL_PATH)


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def _capture_loop():
    cap = cv2.VideoCapture(CAMERA_INDEX)
    # MJPG required at 1080p: raw YUYV at this resolution overruns USB2
    # bandwidth and segfaults the process after a few frames once read
    # continuously from a background thread (confirmed by repro).
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FULL_FRAME_SIZE[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FULL_FRAME_SIZE[1])
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                continue
            preview = cv2.resize(frame, PREVIEW_SIZE)
            with _world_state_lock:
                _world_state["full"] = frame
                _world_state["preview"] = preview
    finally:
        cap.release()


def stream_start():
    """Start the background camera capture thread (idempotent).

    Continuously reads frames from the USB camera and publishes them to
    world_state at two resolutions: "full" (native 1080p, for capture_image
    and find_person) and "preview" (320x240, for follow_me tracking and any
    live stream). Never blocks callers - a failed frame read is skipped.

    Input: none
    Output: none
    """
    global _stream_thread
    if _stream_thread is not None and _stream_thread.is_alive():
        return
    _stream_thread = threading.Thread(target=_capture_loop, daemon=True)
    _stream_thread.start()


def get_world_state():
    """Return a snapshot of the latest frames published by stream_start().

    Input: none
    Output: dict, e.g. {"full": ndarray, "preview": ndarray} - may be
      missing keys (or empty) if stream_start() hasn't produced a frame yet.
    """
    with _world_state_lock:
        return dict(_world_state)


def _wait_for_frame(key, timeout=WORLD_STATE_TIMEOUT_S):
    """Ensures the stream is running and waits for world_state[key] to appear."""
    stream_start()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        frame = get_world_state().get(key)
        if frame is not None:
            return frame
        time.sleep(0.05)
    raise RuntimeError(f"no '{key}' frame available from the camera stream after {timeout}s")


def _encode_jpeg(frame):
    """JPEG-encodes a raw BGR frame."""
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        raise RuntimeError("failed to JPEG-encode frame")
    return buf.tobytes()


def _describe_with_openai(jpeg_bytes):
    """Sends a frame to OpenAI vision and returns a short spoken-language description."""
    client = _get_openai_client()
    image_b64 = base64.standard_b64encode(jpeg_bytes).decode("utf-8")
    response = client.chat.completions.create(
        model=VISION_MODEL,
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                },
                {
                    "type": "text",
                    "text": "Describe what's in this image in one or two short, natural spoken sentences.",
                },
            ],
        }],
    )
    return response.choices[0].message.content


def _send_to_telegram(jpeg_bytes, caption=None):
    """Sends a JPEG frame to the configured Telegram chat."""
    async def _send():
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        async with bot:
            await bot.send_photo(chat_id=TELEGRAM_CHAT_ID, photo=jpeg_bytes, caption=caption)
    asyncio.run(_send())


def capture_image(send_to_telegram=False, analyze=False):
    """Grab the latest full-resolution frame from the camera stream.

    Starts the camera stream if it isn't already running. Three modes:
    - Default (send_to_telegram=False): describe via OpenAI vision
      (gpt-4o-mini) and return the description to be spoken.
    - send_to_telegram=True, analyze=False: send the raw photo to Telegram,
      no analysis.
    - send_to_telegram=True, analyze=True: describe via OpenAI vision, send
      the photo to Telegram with the description as the caption.

    Input: send_to_telegram (bool), analyze (bool)
    Output: the OpenAI vision description (string), or None when only
      posting a raw photo to Telegram (send_to_telegram=True, analyze=False)
    """
    frame = _wait_for_frame("full")
    jpeg_bytes = _encode_jpeg(frame)

    if send_to_telegram and not analyze:
        _send_to_telegram(jpeg_bytes)
        return None

    description = _describe_with_openai(jpeg_bytes)

    if send_to_telegram and analyze:
        _send_to_telegram(jpeg_bytes, caption=description)

    return description


def find_person():
    """Check the current camera view for the enrolled face (single-person match).

    Input: none
    Output: dict — {"found": False}, or {"found": True, "confidence": float
      (1 - face distance), "location": {"top", "right", "bottom", "left"}
      in pixels} for the best match under FACE_MATCH_TOLERANCE.

    Raises RuntimeError if no face has been enrolled yet — run
    test/enroll_face.py once to create models/anh_face.pkl.
    """
    if _known_face_encodings is None:
        raise RuntimeError(f"no enrolled face at {ENROLLED_FACE_PATH} — run test/enroll_face.py first")

    frame = _wait_for_frame("full")
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    locations = face_recognition.face_locations(rgb)
    encodings = face_recognition.face_encodings(rgb, locations)

    best_distance = None
    best_location = None
    for location, encoding in zip(locations, encodings):
        distance = min(face_recognition.face_distance(_known_face_encodings, encoding))
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_location = location

    if best_distance is None or best_distance > FACE_MATCH_TOLERANCE:
        return {"found": False}

    top, right, bottom, left = best_location
    return {
        "found": True,
        "confidence": round(1 - best_distance, 3),
        "location": {"top": top, "right": right, "bottom": bottom, "left": left},
    }


def find_object(label):
    """Locate a named object in the current camera view.

    Input: label (string — what to look for)
    Output: TBD — structured detection result (e.g. bounding box, confidence)
    """
    raise NotImplementedError


def _detect_person_boxes(frame):
    """Runs the SSD person detector on frame, returns a list of
    (left, top, right, bottom) boxes in frame's own pixel coordinates."""
    h, w = frame.shape[:2]
    resized = cv2.resize(frame, SSD_INPUT_SIZE)
    blob = resized.reshape(1, SSD_INPUT_SIZE[1], SSD_INPUT_SIZE[0], 3).astype("uint8")
    _person_detector.setInput(blob)
    boxes, classes, scores, num = _person_detector.forward(_person_detector.getUnconnectedOutLayersNames())

    person_boxes = []
    for i in range(int(num[0])):
        if int(classes[0][i]) != SSD_PERSON_CLASS_ID or scores[0][i] < SSD_CONFIDENCE_THRESHOLD:
            continue
        ymin, xmin, ymax, xmax = boxes[0][i]
        person_boxes.append((int(xmin * w), int(ymin * h), int(xmax * w), int(ymax * h)))
    return person_boxes


def _hsv_histogram(bgr_crop):
    """Normalized joint HSV histogram (REID_HIST_BINS per channel) of a crop."""
    hsv = cv2.cvtColor(bgr_crop, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, [REID_HIST_BINS] * 3, [0, 180, 0, 256, 0, 256])
    cv2.normalize(hist, hist)
    return hist


def _reid_match(frame, signature):
    """Finds the person-shaped box in frame whose upper-body HSV color
    histogram best correlates with the locked signature histogram (also an
    upper-body crop - see _reid_signature_from_face - so both sides are
    comparing the same kind of region).

    Input: frame (BGR ndarray), signature (histogram from _hsv_histogram)
    Output: {"left", "top", "right", "bottom"} of the best match, or None
      if no detected person box scores above REID_MATCH_THRESHOLD.
    """
    best_score = None
    best_box = None
    for left, top, right, bottom in _detect_person_boxes(frame):
        upper_bottom = top + int((bottom - top) * REID_UPPER_BODY_FRACTION)
        crop = frame[top:upper_bottom, left:right]
        if crop.size == 0:
            continue
        score = cv2.compareHist(_hsv_histogram(crop), signature, cv2.HISTCMP_CORREL)
        if best_score is None or score > best_score:
            best_score = score
            best_box = (left, top, right, bottom)

    if best_box is None or best_score < REID_MATCH_THRESHOLD:
        return None

    left, top, right, bottom = best_box
    return {"left": left, "top": top, "right": right, "bottom": bottom}


def _reid_signature_from_face(face_location):
    """Builds a ReID signature from the upper body (top REID_UPPER_BODY_FRACTION)
    of whichever SSD person box contains the enrolled face, mapped from
    world_state["full"] coordinates (what find_person returns) into the
    world_state["preview"] frame. Comparing upper-body clothing histograms
    this way - instead of the face crop itself - is what _reid_match's
    candidate boxes (also SSD person boxes) are actually comparable against."""
    preview = get_world_state().get("preview")
    if preview is None:
        raise RuntimeError("no preview frame available to build a ReID signature")

    scale_x = PREVIEW_SIZE[0] / FULL_FRAME_SIZE[0]
    scale_y = PREVIEW_SIZE[1] / FULL_FRAME_SIZE[1]
    face_center_x = ((face_location["left"] + face_location["right"]) / 2) * scale_x
    face_center_y = ((face_location["top"] + face_location["bottom"]) / 2) * scale_y

    body_box = None
    for left, top, right, bottom in _detect_person_boxes(preview):
        if left <= face_center_x <= right and top <= face_center_y <= bottom:
            body_box = (left, top, right, bottom)
            break
    if body_box is None:
        raise RuntimeError("no SSD person box contains the enrolled face - can't lock a ReID signature")

    left, top, right, bottom = body_box
    upper_bottom = top + int((bottom - top) * REID_UPPER_BODY_FRACTION)
    crop = preview[top:upper_bottom, left:right]
    if crop.size == 0:
        raise RuntimeError("upper-body region maps to an empty crop in the preview frame")
    return _hsv_histogram(crop)


def request_follow_stop():
    """Signals an in-progress follow_me() loop to stop at its next check.

    Nothing calls this yet — it's a hook for the state-machine/override
    layer that would interrupt a long-running action from a new voice
    command, which doesn't exist in this codebase yet.

    Input: none
    Output: none
    """
    _follow_stop_event.set()


def _vprint(verbose, msg):
    if verbose:
        print(msg, flush=True)


def follow_me(verbose=False, on_frame=None):
    """Find the enrolled face, then approach and follow at ~TARGET_DISTANCE_BB_HEIGHT.

    (1) Checks the current frame for the enrolled face first. (2) If not
    found, rotates right in SCAN_STEP_DEGREES steps (up to SCAN_MAX_STEPS,
    i.e. a full 360) re-checking after each step, stopping the instant it's
    found. (3) If still not found after the full scan, speaks and returns.
    (4) Once found, locks a ReID signature (HSV histogram) from the face's
    bounding box and speaks. (5) Enters a ~FOLLOW_LOOP_HZ loop using
    _reid_match (not face recognition — too slow for continuous tracking)
    to stay centered within CENTER_DEADZONE and hold TARGET_DISTANCE_BB_HEIGHT.
    (6) Stops and speaks if the target is lost for more than LOST_TIMEOUT_S.

    Input: verbose (bool) - prints each decision to stdout, for debugging.
      on_frame (callable, optional) - called once per follow-loop iteration
      as on_frame(preview_frame, match, offset, bb_height, action), where
      match/offset/bb_height are None when the target wasn't found that
      iteration and action is one of "rotate_left"/"rotate_right"/
      "move_forward"/"hold"/"lost". Lets a caller (e.g. a debug stream) see
      what the loop is doing without follow_me() itself knowing about it.
    Output: none
    """
    _follow_stop_event.clear()

    _vprint(verbose, "Checking current frame for you before rotating...")
    result = find_person()
    if not result["found"]:
        _vprint(verbose, "Not in view - starting 360 scan.")
        for step in range(1, SCAN_MAX_STEPS + 1):
            _vprint(verbose, f"  scan step {step}/{SCAN_MAX_STEPS}: rotating {SCAN_STEP_DEGREES} degrees right")
            rotate_right(SCAN_STEP_DEGREES)
            result = find_person()
            _vprint(verbose, f"  find_person() -> found={result['found']}"
                             + (f" confidence={result['confidence']}" if result["found"] else ""))
            if result["found"]:
                break
        if not result["found"]:
            _vprint(verbose, "Full 360 scan complete, not found.")
            speak("Can't find you, come to me")
            return
    else:
        _vprint(verbose, f"Found you in the current frame (confidence={result['confidence']}), no scan needed.")

    signature = _reid_signature_from_face(result["location"])
    _vprint(verbose, "ReID signature locked from your upper body.")
    speak("On my way")

    frame_center_x = PREVIEW_SIZE[0] / 2
    loop_interval = 1.0 / FOLLOW_LOOP_HZ
    last_seen = time.monotonic()
    iteration = 0

    while not _follow_stop_event.is_set():
        iter_start = time.monotonic()
        iteration += 1
        preview = get_world_state().get("preview")
        match = None if preview is None else _reid_match(preview, signature)

        offset = None
        bb_height = None

        if match is None:
            lost_for = time.monotonic() - last_seen
            if lost_for > LOST_TIMEOUT_S:
                motor_stop()
                action = "lost"
                _vprint(verbose, f"[{iteration}] lost for {lost_for:.1f}s > {LOST_TIMEOUT_S}s - stopping.")
                if on_frame is not None:
                    on_frame(preview, match, offset, bb_height, action)
                speak("I lost you, say follow me again")
                return
            action = "searching"
            _vprint(verbose, f"[{iteration}] no ReID match this frame (lost for {lost_for:.1f}s/{LOST_TIMEOUT_S}s)")
        else:
            last_seen = time.monotonic()
            center_x = (match["left"] + match["right"]) / 2
            offset = center_x - frame_center_x
            bb_height = match["bottom"] - match["top"]

            if abs(offset) > CENTER_DEADZONE:
                action = "rotate_right" if offset > 0 else "rotate_left"
                _vprint(verbose, f"[{iteration}] match bb_height={bb_height} offset={offset:.0f}px "
                                 f"(>{CENTER_DEADZONE} deadzone) -> {action}({ROTATE_STEP_DEGREES} deg)")
                (rotate_right if offset > 0 else rotate_left)(ROTATE_STEP_DEGREES)
            elif bb_height < TARGET_DISTANCE_BB_HEIGHT:
                action = "move_forward"
                _vprint(verbose, f"[{iteration}] match bb_height={bb_height} < target {TARGET_DISTANCE_BB_HEIGHT} "
                                 f"offset={offset:.0f}px (centered) -> move_forward({APPROACH_STEP_MM}mm)")
                move_forward(APPROACH_STEP_MM)
            else:
                action = "hold"
                _vprint(verbose, f"[{iteration}] match bb_height={bb_height} offset={offset:.0f}px "
                                 f"- centered and at target distance, holding")
                motor_stop()

        if on_frame is not None:
            on_frame(preview, match, offset, bb_height, action)

        elapsed = time.monotonic() - iter_start
        if elapsed < loop_interval:
            time.sleep(loop_interval - elapsed)
