#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from butter_audio import speak

INTRO = "Hey, I am Butter. Your personal home robot. How can I help you today?"


if __name__ == "__main__":
    print(f"Speaking: {INTRO}")
    speak(INTRO)
