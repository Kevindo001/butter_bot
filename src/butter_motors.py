"""Movement tools for Butter.

Covers everything that drives the mecanum drivetrain via GPIO -> L298N
motor drivers: straight-line movement, in-place rotation, and stop. GPIO
setup and pin map mirror test/06_test_motors.py (confirmed working).
Timing math and the confirmed GPIO pin map live in config/motor.md.
"""
import math
import time

import Jetson.GPIO as GPIO

WHEELS = {
    "left_front": (11, 13),
    "left_rear": (16, 15),
    "right_front": (33, 31),
    "right_rear": (29, 18),
}

LEFT_WHEELS = ("left_front", "left_rear")
RIGHT_WHEELS = ("right_front", "right_rear")

MM_PER_SECOND = 712  # empirical effective linear speed, see config/motor.md
TURN_RADIUS_MM = 125  # empirical effective turning radius, see config/motor.md

GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)
for _in1, _in2 in WHEELS.values():
    GPIO.setup(_in1, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(_in2, GPIO.OUT, initial=GPIO.LOW)


def _stop(pins):
    in1, in2 = pins
    GPIO.output(in1, GPIO.LOW)
    GPIO.output(in2, GPIO.LOW)


def _forward(pins):
    in1, in2 = pins
    GPIO.output(in1, GPIO.LOW)
    GPIO.output(in2, GPIO.HIGH)


def _backward(pins):
    in1, in2 = pins
    GPIO.output(in1, GPIO.HIGH)
    GPIO.output(in2, GPIO.LOW)


def move_forward(distance_mm):
    """Drive all four wheels forward in a straight line for a computed duration.

    Input: distance_mm (number)
    Output: none (blocks until movement completes)
    """
    duration = distance_mm / MM_PER_SECOND
    for pins in WHEELS.values():
        _forward(pins)
    time.sleep(duration)
    stop()


def move_backward(distance_mm):
    """Drive all four wheels backward for a computed duration.

    Input: distance_mm (number)
    Output: none (blocks until movement completes)
    """
    duration = distance_mm / MM_PER_SECOND
    for pins in WHEELS.values():
        _backward(pins)
    time.sleep(duration)
    stop()


def rotate_left(degrees):
    """Rotate the robot in place counterclockwise by a given angle.

    Left wheels drive backward, right wheels drive forward.

    Input: degrees (number, positive)
    Output: none (blocks until movement completes)
    """
    arc_length_mm = math.pi * TURN_RADIUS_MM * (degrees / 360)
    duration = arc_length_mm / MM_PER_SECOND
    for name in LEFT_WHEELS:
        _backward(WHEELS[name])
    for name in RIGHT_WHEELS:
        _forward(WHEELS[name])
    time.sleep(duration)
    stop()


def rotate_right(degrees):
    """Rotate the robot in place clockwise by a given angle.

    Right wheels drive backward, left wheels drive forward.

    Input: degrees (number, positive)
    Output: none (blocks until movement completes)
    """
    arc_length_mm = math.pi * TURN_RADIUS_MM * (degrees / 360)
    duration = arc_length_mm / MM_PER_SECOND
    for name in RIGHT_WHEELS:
        _backward(WHEELS[name])
    for name in LEFT_WHEELS:
        _forward(WHEELS[name])
    time.sleep(duration)
    stop()


def stop():
    """Immediately set all motor pins LOW, halting movement.

    Input: none
    Output: none
    """
    for pins in WHEELS.values():
        _stop(pins)
