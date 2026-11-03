import random
import subprocess
import time
from pathlib import Path

from gpiozero import LED
from rpi_hardware_pwm import HardwarePWM

# ---------------- Settings ----------------
LED_PIN = 13 # From 17 due to seeed only exposing GPIO12, 13 - Grove port signal 2 
SOUND_DIR = Path(__file__).parent / "sounds"
NUM_SOUNDS = 14

BEAK_CLOSED_ANGLE = 0       # adjust to suit your linkage
BEAK_OPEN_ANGLE = 15        # degrees opened while squawking

BLINK_MIN, BLINK_MAX = 4, 8         # seconds between blinks
BLINK_DURATION = 0.20               # seconds eye is off
SQUAWK_MIN, SQUAWK_MAX = 12, 24      # seconds between squawks

# ---------------- Hardware ----------------
led = LED(LED_PIN)
servo = HardwarePWM(pwm_channel=0, hz=50, chip=0)   # GPIO12


def angle_to_duty(angle):
    pulse_ms = 0.5 + (angle / 180) * 2.0        # 0.5-2.5 ms pulse
    return pulse_ms / 20.0 * 100                # percent of 20 ms period


def set_angle(angle):
    servo.change_duty_cycle(angle_to_duty(angle))


def random_delay(lo, hi):
    return time.monotonic() + random.uniform(lo, hi)


# ---------------- Main ----------------
def main():
    servo.start(angle_to_duty(BEAK_CLOSED_ANGLE))
    led.on()

    next_blink = random_delay(BLINK_MIN, BLINK_MAX)
    blink_end = None
    next_squawk = random_delay(SQUAWK_MIN, SQUAWK_MAX)
    player = None
    last_sound = 0

    while True:
        now = time.monotonic()

        # ---- LED blink ----
        if blink_end is None:
            if now >= next_blink:
                print("Blink off")
                led.off()
                blink_end = now + BLINK_DURATION
        elif now >= blink_end:
            print("Blink on")
            led.on()
            blink_end = None
            next_blink = random_delay(BLINK_MIN, BLINK_MAX)

        # ---- Squawk ----
        if player is None:
            if now >= next_squawk:
                n = random.randint(1, NUM_SOUNDS)
                while n == last_sound:
                    n = random.randint(1, NUM_SOUNDS)
                last_sound = n
                print("Sqwark")
                path = SOUND_DIR / f"{n:04d}.mp3"
                player = subprocess.Popen(
                    ["mpg123", "-q", str(path)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                set_angle(BEAK_CLOSED_ANGLE + BEAK_OPEN_ANGLE)
        elif player.poll() is not None:         # mp3 has finished
            player = None
            print("Close Beak")
            set_angle(BEAK_CLOSED_ANGLE)
            next_squawk = random_delay(SQUAWK_MIN, SQUAWK_MAX)

        time.sleep(0.01)


try:
    main()
except KeyboardInterrupt:
    pass
finally:
    set_angle(BEAK_CLOSED_ANGLE)
    time.sleep(0.3)
    servo.stop()
    led.off()
