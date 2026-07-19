#!/usr/bin/env python3
"""Standalone, direct test of follow_me() - no voice pipeline involved, no
dispatcher. Calls follow_me() directly and drives the real motors.

Prints every decision follow_me() makes (scan steps, ReID matches, offsets,
distances, which motor call it's issuing) via verbose=True, and starts a
live debug camera stream - reusing the already-running camera thread via
LivePreview's frame_source hook, NOT a second capture, since most USB
cameras reject a second concurrent VideoCapture - with the current match
box and action drawn on it, so you can watch what Butter sees while it
follows.

Ctrl+C stops the motors immediately and signals follow_me() to stop
cleanly via request_follow_stop() (mostly symbolic at that point - the
KeyboardInterrupt already unwinds the loop - but included since it's the
same mechanism a future voice "stop" command would use). motor_stop() also
runs as the first line of the finally block, so motors stop on ANY exit
path - a normal return, Ctrl+C, or an unexpected exception from follow_me()
itself - not just the Ctrl+C case.

Run: python3 test/test_follow_me_motors.py

Emergency stop from ANY OTHER terminal, at any time, independent of this
process (e.g. if this terminal becomes unresponsive):
  sudo /home/anhdo001/Projects/butter/butter_env/bin/python3 test/kill_motors.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import cv2

from butter_camera import follow_me, stream_start, get_world_state, request_follow_stop
from butter_motors import stop as motor_stop
from _live_preview import LivePreview

_preview = None

_ACTION_COLORS = {
    "rotate_left": (0, 200, 200),
    "rotate_right": (0, 200, 200),
    "move_forward": (0, 200, 0),
    "hold": (255, 200, 0),
    "searching": (0, 0, 220),
    "lost": (0, 0, 220),
}


def on_frame(frame, match, offset, bb_height, action):
    """follow_me()'s per-iteration debug hook: draws the current match box
    and action onto the live stream (called once per follow-loop iteration,
    not during the initial 360 scan - that phase has no preview match yet)."""
    if frame is None or _preview is None:
        return
    display = frame.copy()
    color = _ACTION_COLORS.get(action, (255, 255, 255))

    if match is not None:
        cv2.rectangle(display, (match["left"], match["top"]), (match["right"], match["bottom"]), color, 2)
    label = action if bb_height is None else f"{action} (h={bb_height})"
    cv2.putText(display, label, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    _preview.set_display_frame(display)


def main():
    global _preview

    print("Starting camera stream...")
    stream_start()
    for _ in range(40):
        if get_world_state().get("preview") is not None:
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("no preview frame after 2s - is the camera connected?")

    _preview = LivePreview(frame_source=lambda: get_world_state().get("preview"))
    _preview.start()
    print("Debug stream ready - open it in a browser to watch Butter's view.")
    print("Emergency stop from another terminal at any time:")
    print("  sudo /home/anhdo001/Projects/butter/butter_env/bin/python3 test/kill_motors.py\n")

    try:
        follow_me(verbose=True, on_frame=on_frame)
    except KeyboardInterrupt:
        print("\nCtrl+C - stopping motors immediately...")
        motor_stop()
        request_follow_stop()
        print("Motors stopped, follow_me() signaled to stop.")
    finally:
        motor_stop()
        if _preview is not None:
            _preview.stop()


if __name__ == "__main__":
    main()
