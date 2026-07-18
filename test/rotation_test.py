#!/usr/bin/env python3
"""
Tests whether Butter can move forward and rotate at the same time using the
current L298N setup: each wheel's H-bridge is driven by two plain digital
pins (IN1/IN2, no PWM enable line), so a wheel can only be commanded fully
forward, fully backward, or stopped - never a blended/partial speed.

rotate_left  = left wheels backward, right wheels forward (pivot in place)
rotate_right = left wheels forward,  right wheels backward (pivot in place)
move_forward = all wheels forward

Three cases: rotate only, move only, and both at the same time. The "both"
case combines move_forward with rotate_left wheel-by-wheel and prints
whether each wheel's two commands agree or conflict, since that's what
actually determines whether simultaneous movement is physically possible
with this hardware.
"""
import time

import Jetson.GPIO as GPIO

WHEELS = {
    "left_front": (11, 13),
    "left_rear": (16, 15),
    "right_front": (33, 31),
    "right_rear": (29, 18),
}
LEFT_WHEELS = ["left_front", "left_rear"]
RIGHT_WHEELS = ["right_front", "right_rear"]

DURATION = 2.0  # seconds per case

GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)
for _in1, _in2 in WHEELS.values():
    GPIO.setup(_in1, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(_in2, GPIO.OUT, initial=GPIO.LOW)


def stop(pins):
    in1, in2 = pins
    GPIO.output(in1, GPIO.LOW)
    GPIO.output(in2, GPIO.LOW)


def forward(pins):
    in1, in2 = pins
    GPIO.output(in1, GPIO.LOW)
    GPIO.output(in2, GPIO.HIGH)


def backward(pins):
    in1, in2 = pins
    GPIO.output(in1, GPIO.HIGH)
    GPIO.output(in2, GPIO.LOW)


def stop_all():
    for pins in WHEELS.values():
        stop(pins)


def set_wheel(name, direction):
    pins = WHEELS[name]
    if direction == "forward":
        forward(pins)
    elif direction == "backward":
        backward(pins)
    else:
        stop(pins)


def apply_commands(commands):
    for name, direction in commands.items():
        set_wheel(name, direction)


def move_forward_commands():
    return {name: "forward" for name in WHEELS}


def rotate_left_commands():
    commands = {name: "backward" for name in LEFT_WHEELS}
    commands.update({name: "forward" for name in RIGHT_WHEELS})
    return commands


def rotate_right_commands():
    commands = {name: "forward" for name in LEFT_WHEELS}
    commands.update({name: "backward" for name in RIGHT_WHEELS})
    return commands


def print_commands(commands):
    for name in WHEELS:
        print(f"    {name}: {commands[name]}")


def run_case(label, commands, duration=DURATION):
    print(f"\n=== {label} ===")
    print_commands(commands)
    apply_commands(commands)
    time.sleep(duration)
    stop_all()
    print("  stopped")


def combine_commands(cmd_a, label_a, cmd_b, label_b):
    """Combines two per-wheel command sets, printing whether each wheel's
    two desired directions agree (both can genuinely happen) or conflict
    (a single digital pin pair can't be forward and backward at once - that
    needs PWM speed blending, which this setup doesn't have). On conflict,
    the second command's direction is what actually ends up applied, since
    that's the last GPIO.output() call to touch that wheel's pins - it is
    NOT a blend of the two, just whichever was written last."""
    combined = {}
    print(f"\n=== both at the same time: {label_a} + {label_b} ===")
    for name in WHEELS:
        a = cmd_a[name]
        b = cmd_b[name]
        if a == b:
            combined[name] = a
            print(f"    {name}: {label_a}={a}  {label_b}={b}  -> agree, wheel does {a}")
        else:
            combined[name] = b
            print(f"    {name}: {label_a}={a}  {label_b}={b}  -> CONFLICT (no PWM to blend) "
                  f"- last command applied wins: {b}")
    return combined


def main():
    print("Butter rotation + movement simultaneity test")
    print("Checks whether move_forward and rotate can truly run at once on")
    print("this on/off (no PWM) L298N direction control, or whether one")
    print("command just overrides the other on conflicting wheels.\n")

    run_case("rotate_left only", rotate_left_commands())
    time.sleep(0.5)

    run_case("move_forward only", move_forward_commands())
    time.sleep(0.5)

    combined = combine_commands(
        move_forward_commands(), "move_forward",
        rotate_left_commands(), "rotate_left",
    )
    print("  applying combined result:")
    apply_commands(combined)
    time.sleep(DURATION)
    stop_all()
    print("  stopped")

    print("\n=== conclusion ===")
    print("Right wheels agreed (forward) under both commands - that side can")
    print("genuinely do both at once. Left wheels conflicted (forward vs")
    print("backward) - a single IN1/IN2 pin pair can only hold one direction,")
    print("so true simultaneous move+rotate isn't physically possible with")
    print("this binary on/off L298N setup. Blending forward translation with")
    print("rotation needs PWM speed control (ENA/ENB duty cycle) to run one")
    print("side faster than the other, instead of full-on directional")
    print("switching. (Same conflict, mirrored, applies to move_forward +")
    print("rotate_right - right wheels would conflict instead of left.)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        stop_all()
        print("\nstopped")
    finally:
        stop_all()
        GPIO.cleanup()
