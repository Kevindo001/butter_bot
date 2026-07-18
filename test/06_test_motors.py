#!/usr/bin/env python3
import time
import Jetson.GPIO as GPIO

WHEELS = {
    "left_front": (11, 13),
    "left_rear": (16, 15),
    "right_front": (33, 31),
    "right_rear": (29, 18),
}

GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)
for in1, in2 in WHEELS.values():
    GPIO.setup(in1, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(in2, GPIO.OUT, initial=GPIO.LOW)


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


def run_wheel(name, direction, duration):
    pins = WHEELS[name]
    (forward if direction == "forward" else backward)(pins)
    time.sleep(duration)
    stop(pins)


def run_all(direction, duration):
    drive = forward if direction == "forward" else backward
    for pins in WHEELS.values():
        drive(pins)
    time.sleep(duration)
    stop_all()


NUMBERED = {
    1: ("left_front", "forward"),
    2: ("left_front", "backward"),
    3: ("right_front", "forward"),
    4: ("right_front", "backward"),
    5: ("left_rear", "forward"),
    6: ("left_rear", "backward"),
    7: ("right_rear", "forward"),
    8: ("right_rear", "backward"),
}

NUMBERED_HELP = "\n".join(
    f"  {n}: {wheel} {direction}" for n, (wheel, direction) in NUMBERED.items()
)

HELP = f"""Wheels: left_front, left_rear, right_front, right_rear, all
Command: <wheel> <forward|backward> <seconds>
       | <number 1-8> <seconds>
{NUMBERED_HELP}
Other:   help, quit"""


def main():
    print("Butter motor test")
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

        parts = line.split()

        if len(parts) == 2 and parts[0].isdigit():
            num = int(parts[0])
            if num not in NUMBERED:
                print(f"number must be one of {', '.join(str(n) for n in NUMBERED)}")
                continue
            try:
                duration = float(parts[1])
            except ValueError:
                print("seconds must be a number")
                continue
            wheel, direction = NUMBERED[num]
            try:
                run_wheel(wheel, direction, duration)
            except KeyboardInterrupt:
                stop_all()
                print("\nstopped")
            continue

        if len(parts) != 3:
            print("format: <wheel> <forward|backward> <seconds>  or  <number 1-8> <seconds>")
            continue
        wheel, direction, dur = parts
        if direction not in ("forward", "backward"):
            print("direction must be forward or backward")
            continue
        try:
            duration = float(dur)
        except ValueError:
            print("seconds must be a number")
            continue

        try:
            if wheel == "all":
                run_all(direction, duration)
            elif wheel in WHEELS:
                run_wheel(wheel, direction, duration)
            else:
                print(f"unknown wheel: {wheel} (options: {', '.join(WHEELS)}, all)")
        except KeyboardInterrupt:
            stop_all()
            print("\nstopped")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        stop_all()
        GPIO.cleanup()
