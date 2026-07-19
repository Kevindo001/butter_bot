#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from butter_camera import capture_image


if __name__ == "__main__":
    print("Capturing frame, sending to Telegram, describing via OpenAI vision...")
    description = capture_image(send_to_telegram=True, analyze=True)
    print(f"Description: {description}")
