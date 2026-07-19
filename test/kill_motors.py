#!/usr/bin/env python3
"""Emergency motor kill switch.

Run this from ANY terminal - a separate SSH session from whatever is
driving the wheels (e.g. test_follow_me_motors.py) - to immediately set
every motor GPIO pin LOW, independent of whatever that other process is
doing. GPIO pin writes aren't exclusive to one process, so this works even
if the other process is hung or unresponsive.

This only zeroes the pins for as long as nothing else writes to them again
right after - it does NOT stop the other process. If a follow_me() loop is
still running, it can drive the motors again on its next iteration. For a
real stop: Ctrl+C the process actually running follow_me() (or
`pkill -f test_follow_me_motors.py` from here), and use this script for the
immediate "pins off right now" case - e.g. that other terminal is
unreachable, or you want the wheels off while you go find it.

Run: sudo /home/anhdo001/Projects/butter/butter_env/bin/python3 test/kill_motors.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from butter_motors import stop

if __name__ == "__main__":
    stop()
    print("All motor pins set LOW.")
