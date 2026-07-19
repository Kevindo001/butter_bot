#!/usr/bin/env python3
"""Continuously checks the live camera feed against the enrolled face
(models/anh_face.pkl) and draws the result on the live MJPEG preview so you
can watch detection happen in real time. Ctrl+C to stop.
"""
import os
import pickle
import sys
import time

import cv2
import face_recognition

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from butter_camera import ENROLLED_FACE_PATH, FACE_MATCH_TOLERANCE

sys.path.insert(0, os.path.dirname(__file__))
from _live_preview import LivePreview

CAMERA_INDEX = 0
CHECK_INTERVAL = 0.5


def main():
    if not os.path.exists(ENROLLED_FACE_PATH):
        raise RuntimeError(f"no enrolled face at {ENROLLED_FACE_PATH} — run test/enroll_face.py first")
    with open(ENROLLED_FACE_PATH, "rb") as f:
        known_encodings = pickle.load(f)

    preview = LivePreview(camera_index=CAMERA_INDEX)
    preview.start()

    print("Watching for Anh. Ctrl+C to stop.")
    last_status = None
    try:
        while True:
            frame = preview.get_frame()
            if frame is None:
                time.sleep(0.05)
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            locations = face_recognition.face_locations(rgb)
            encodings = face_recognition.face_encodings(rgb, locations)

            display = frame.copy()
            found_anh = False
            for (top, right, bottom, left), encoding in zip(locations, encodings):
                match = any(face_recognition.compare_faces(known_encodings, encoding, tolerance=FACE_MATCH_TOLERANCE))
                found_anh = found_anh or match
                label = "ANH FOUND" if match else "Unknown"
                color = (0, 200, 0) if match else (0, 0, 220)
                cv2.rectangle(display, (left, top), (right, bottom), color, 2)
                cv2.putText(display, label, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            preview.set_display_frame(display)

            status = "ANH FOUND" if found_anh else ("Unknown person" if locations else "No face detected")
            if status != last_status:
                print(status)
                last_status = status

            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        pass
    finally:
        preview.stop()


if __name__ == "__main__":
    main()
