from machine import Pin, PWM, UART
import time
import random

# ---------------- Settings ----------------
LED_PIN = 15
SERVO_PIN = 16
BUSY_PIN = 2

BEAK_CLOSED_ANGLE = 0      # adjust to suit your linkage
BEAK_OPEN_ANGLE = 20       # closed + 20 degrees
NUM_SOUNDS = 14
VOLUME = 25                # 0-30

BLINK_MIN_MS = 5000
BLINK_MAX_MS = 10000
BLINK_DURATION_MS = 150

SQUAWK_MIN_MS = 10000
SQUAWK_MAX_MS = 20000
BUSY_START_TIMEOUT_MS = 1500   # max wait for the player to start

# ---------------- Hardware ----------------
led = Pin(LED_PIN, Pin.OUT)
busy = Pin(BUSY_PIN, Pin.IN, Pin.PULL_UP)   # LOW while playing
uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))

servo = PWM(Pin(SERVO_PIN))
servo.freq(50)


def set_angle(angle):
    """Move servo to angle (0-180). Pulse 0.5ms-2.5ms in a 20ms period."""
    pulse_us = 500 + (angle / 180) * 2000
    servo.duty_u16(int(pulse_us / 20000 * 65535))


# ---------------- DFPlayer Mini ----------------
def df_send(cmd, param=0):
    data = bytearray([0xFF, 0x06, cmd, 0x00, (param >> 8) & 0xFF, param & 0xFF])
    checksum = -sum(data) & 0xFFFF
    packet = bytearray([0x7E]) + data + bytearray(
        [(checksum >> 8) & 0xFF, checksum & 0xFF, 0xEF])
    uart.write(packet)


def df_init():
    time.sleep_ms(1000)         # let the module boot
    df_send(0x09, 2)            # select SD card
    time.sleep_ms(300)
    df_send(0x06, VOLUME)       # set volume
    time.sleep_ms(100)


def df_play_mp3_folder(n):
    df_send(0x12, n)            # plays /MP3/000n.mp3


def df_stop():
    df_send(0x16)


# ---------------- Scheduling helpers ----------------
def next_time(min_ms, max_ms):
    return time.ticks_add(time.ticks_ms(), random.randint(min_ms, max_ms))


def due(t):
    return time.ticks_diff(time.ticks_ms(), t) >= 0


# ---------------- Main ----------------
def main():
    time.sleep(3)               # window to press Stop in Thonny at startup

    set_angle(BEAK_CLOSED_ANGLE)
    led.value(1)                # eye on
    df_init()

    next_blink = next_time(BLINK_MIN_MS, BLINK_MAX_MS)
    blink_end = None            # when to turn the eye back on
    next_squawk = next_time(SQUAWK_MIN_MS, SQUAWK_MAX_MS)

    state = "IDLE"              # IDLE -> STARTING -> PLAYING -> IDLE
    start_deadline = 0
    last_sound = 0

    while True:
        # ---- LED blink (non-blocking) ----
        if blink_end is None:
            if due(next_blink):
                led.value(0)
                blink_end = time.ticks_add(time.ticks_ms(), BLINK_DURATION_MS)
        elif due(blink_end):
            led.value(1)
            blink_end = None
            next_blink = next_time(BLINK_MIN_MS, BLINK_MAX_MS)

        # ---- Squawk state machine ----
        if state == "IDLE":
            if due(next_squawk):
                # pick a random sound, avoiding an immediate repeat
                n = random.randint(1, NUM_SOUNDS)
                while n == last_sound and NUM_SOUNDS > 1:
                    n = random.randint(1, NUM_SOUNDS)
                last_sound = n

                df_play_mp3_folder(n)
                set_angle(BEAK_CLOSED_ANGLE + BEAK_OPEN_ANGLE)
                start_deadline = time.ticks_add(time.ticks_ms(), BUSY_START_TIMEOUT_MS)
                state = "STARTING"

        elif state == "STARTING":
            # wait for BUSY to go low (playback begun)
            if busy.value() == 0:
                state = "PLAYING"
            elif due(start_deadline):
                # never started (missing file / SD problem): close beak, retry later
                set_angle(BEAK_CLOSED_ANGLE)
                next_squawk = next_time(SQUAWK_MIN_MS, SQUAWK_MAX_MS)
                state = "IDLE"

        elif state == "PLAYING":
            if busy.value() == 1:       # finished
                set_angle(BEAK_CLOSED_ANGLE)
                next_squawk = next_time(SQUAWK_MIN_MS, SQUAWK_MAX_MS)
                state = "IDLE"

        time.sleep_ms(10)


try:
    main()
except KeyboardInterrupt:
    df_stop()
    set_angle(BEAK_CLOSED_ANGLE)
    led.value(0)
    servo.deinit()
    print("Stopped")
