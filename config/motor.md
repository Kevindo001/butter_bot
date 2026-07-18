# Motor Config

Drivetrain: 4x mecanum wheels, driven by 2x L298N motor drivers.

## GPIO pin map (BOARD numbering, confirmed working)

| Wheel       | Pins   |
|-------------|--------|
| Left Front  | 11, 13 |
| Left Rear   | 16, 15 |
| Right Front | 33, 31 |
| Right Rear  | 29, 18 |

Each wheel is driven by an IN1/IN2 pair on its L298N channel:

- Forward = IN2 HIGH, IN1 LOW
- Reverse = IN1 HIGH, IN2 LOW
- Stop = both LOW

Left Rear is wired reversed relative to the other three wheels — its pins are listed (IN1, IN2) = (16, 15), opposite order from the others, to compensate in software rather than re-wiring the harness. Confirmed via `test/06_test_motors.py` numbered commands 5/6.

## Pinmux persistence

Jetson's pinmux configuration does not survive a reboot by default. It is made permanent via the `butter-pinmux.service` systemd unit — if motors stop responding after a reboot, check `systemctl status butter-pinmux.service` before re-wiring anything.

## Verification

Motor wiring is exercised by `test/06_test_motors.py`. Run this after any wiring change or reboot to confirm all four wheels still respond correctly before trusting higher-level movement code.

Run command (must use the venv Python under sudo — see [[specs.md]] GPIO section for why):

```
sudo /home/anhdo001/Projects/butter/butter_env/bin/python3 test/06_test_motors.py
```

## Motor math

Constants derived empirically for this drivetrain (mm/s effective speed = 712).

**Linear movement (forward/backward):**

```
duration_s = distance_mm / 712
```

**Rotation in place:**

```
arc_length_mm = pi * 125 * (degrees / 360)
duration_s = arc_length_mm / 712
```

125 is the effective turning radius (mm) for in-place rotation on this chassis. If wheel spacing or wheel diameter changes, re-derive both constants (712 and 125) empirically rather than assuming they still hold.
