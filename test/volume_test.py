#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from butter_audio import speak

HELP = "Enter a volume multiplier (e.g. 0.5, 1.0, 2.0). Other: help, quit"


def main():
    print("Butter volume test")
    print(HELP)
    while True:
        try:
            line = input("> ").strip().lower()
        except EOFError:
            break
        if not line:
            continue
        if line in ("quit", "exit", "q"):
            break
        if line in ("help", "h", "?"):
            print(HELP)
            continue

        try:
            volume = float(line)
        except ValueError:
            print("volume must be a number")
            continue
        if volume < 0:
            print("volume must be >= 0")
            continue

        phrase = f"This is Butter, speaking at volume {volume}."
        print(f"Speaking: {phrase}")
        speak(phrase, volume=volume)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
