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

import cv2
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Bot

load_dotenv()

CAMERA_INDEX = 0
VISION_MODEL = "gpt-4o-mini"
ENROLLED_FACE_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "anh_face.pkl")
FACE_MATCH_TOLERANCE = 0.5

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

_openai_client = None


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def _grab_raw_frame():
    """Grabs a single raw BGR frame from the USB camera."""
    cap = cv2.VideoCapture(CAMERA_INDEX)
    try:
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError(f"failed to read a frame from camera index {CAMERA_INDEX}")
    finally:
        cap.release()
    return frame


def _grab_frame():
    """Grabs a single frame from the USB camera and JPEG-encodes it."""
    frame = _grab_raw_frame()
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        raise RuntimeError("failed to JPEG-encode captured frame")
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
    """Grab a single frame from the USB camera.

    Three modes:
    - Default (send_to_telegram=False): capture, describe via OpenAI vision
      (gpt-4o-mini), and return the description to be spoken.
    - send_to_telegram=True, analyze=False: capture and send the raw photo
      to Telegram, no analysis.
    - send_to_telegram=True, analyze=True: capture, describe via OpenAI
      vision, and send the photo to Telegram with the description as the
      caption.

    Input: send_to_telegram (bool), analyze (bool)
    Output: the OpenAI vision description (string), or None when only
      posting a raw photo to Telegram (send_to_telegram=True, analyze=False)
    """
    jpeg_bytes = _grab_frame()

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
    import face_recognition  # deferred: pulls in dlib, only needed here

    if not os.path.exists(ENROLLED_FACE_PATH):
        raise RuntimeError(f"no enrolled face at {ENROLLED_FACE_PATH} — run test/enroll_face.py first")
    with open(ENROLLED_FACE_PATH, "rb") as f:
        known_encodings = pickle.load(f)

    frame = _grab_raw_frame()
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    locations = face_recognition.face_locations(rgb)
    encodings = face_recognition.face_encodings(rgb, locations)

    best_distance = None
    best_location = None
    for location, encoding in zip(locations, encodings):
        distance = min(face_recognition.face_distance(known_encodings, encoding))
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


def get_world_state():
    """Summarize what the vision pipeline currently sees for the Brain.

    Input: none
    Output: TBD — structured summary of detected people/objects
    """
    raise NotImplementedError


def stream_start():
    """Start a live video stream from the USB camera.

    Input: none
    Output: TBD — stream handle or endpoint
    """
    raise NotImplementedError
