#!/usr/bin/env python3
"""One-time enrollment for find_person(). Serves a live MJPEG preview so you
can see what the camera sees, then captures a handful of photos and saves
the face embeddings that find_person() later compares against.
"""
import os
import pickle
import sys

import cv2
import face_recognition

sys.path.insert(0, os.path.dirname(__file__))
from _live_preview import LivePreview

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "anh_face.pkl")
CAMERA_INDEX = 0
NUM_PHOTOS = 5


def main():
    preview = LivePreview(camera_index=CAMERA_INDEX)
    preview.start()

    embeddings = []
    try:
        print("Look at the camera. Capturing 5 photos...")
        for i in range(NUM_PHOTOS):
            input(f"Press Enter for photo {i + 1}/{NUM_PHOTOS}...")
            frame = preview.get_frame()
            if frame is None:
                print("  No frame available yet, try again")
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            locations = face_recognition.face_locations(rgb)
            encodings = face_recognition.face_encodings(rgb, locations)
            if encodings:
                embeddings.append(encodings[0])
                print(f"  Got it ({len(locations)} face found)")
            else:
                print("  No face detected, try again")
    finally:
        preview.stop()

    if not embeddings:
        print("No faces captured, nothing saved.")
        return

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(embeddings, f)

    print(f"Enrolled {len(embeddings)} embeddings saved to {MODEL_PATH}")


if __name__ == "__main__":
    main()
