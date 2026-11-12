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

# Head movement
HEAD_PINS = (10, 11, 12, 13)     # IN1..IN4
HEAD_MAX_DEG = 20                # +/- degrees from centre
HEAD_MIN_MOVE_DEG = 6            # skip tiny movements
HEAD_MIN_MS = 6000               # random delay between head moves
HEAD_MAX_MS = 15000
STEP_INTERVAL_US = 3000          # time per half-step (raise if it stalls)
HOLD_COILS = False               # False = power off coils when stopped (cooler, quieter)

STEPS_PER_REV = 4096             # 28BYJ-48 in half-step mode
HEAD_MAX_STEPS = int(STEPS_PER_REV * HEAD_MAX_DEG / 360)
HEAD_MIN_MOVE_STEPS = int(STEPS_PER_REV * HEAD_MIN_MOVE_DEG / 360)

# ---------------- Hardware ----------------
led = Pin(LED_PIN, Pin.OUT)
busy = Pin(BUSY_PIN, Pin.IN, Pin.PULL_UP)   # LOW while playing
uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))

servo = PWM(Pin(SERVO_PIN))
servo.freq(50)

# Head movement
head_pins = [Pin(p, Pin.OUT, value=0) for p in HEAD_PINS]
HALF_STEP = (
    (1, 0, 0, 0), (1, 1, 0, 0), (0, 1, 0, 0), (0, 1, 1, 0),
    (0, 0, 1, 0), (0, 0, 1, 1), (0, 0, 0, 1), (1, 0, 0, 1),
)
head_phase = 0       # position in the half-step sequence
head_pos = 0         # current position in steps (0 = centre)
head_target = 0      # where we are heading
head_next_us = 0     # when the next step is due

def set_angle(angle):
    """Move servo to angle (0-180). Pulse 0.5ms-2.5ms in a 20ms period."""
    pulse_us = 500 + (angle / 180) * 2000
    servo.duty_u16(int(pulse_us / 20000 * 65535))

# ---------------- Head movement ----------------
def head_write(phase):
    for pin, v in zip(head_pins, HALF_STEP[phase]):
        pin.value(v)


def head_release():
    for pin in head_pins:
        pin.value(0)


def head_new_target():
    """Pick a random angle within +/- HEAD_MAX_DEG, at least a minimum move away."""
    global head_target
    while True:
        t = random.randint(-HEAD_MAX_STEPS, HEAD_MAX_STEPS)
        if abs(t - head_pos) >= HEAD_MIN_MOVE_STEPS:
            head_target = t
            return


def head_service():
    """Take one step toward the target if one is due. Call every loop."""
    global head_pos, head_phase, head_next_us
    if head_pos == head_target:
        return
    if time.ticks_diff(time.ticks_us(), head_next_us) < 0:
        return
    if head_target > head_pos:
        head_phase = (head_phase + 1) % 8
        head_pos += 1
    else:
        head_phase = (head_phase - 1) % 8
        head_pos -= 1
    head_write(head_phase)
    head_next_us = time.ticks_add(time.ticks_us(), STEP_INTERVAL_US)
    if head_pos == head_target and not HOLD_COILS:
        head_release()


def head_centre():
    """Blocking return to centre (used when stopping)."""
    global head_target
    head_target = 0
    while head_pos != 0:
        head_service()
        time.sleep_us(200)
    head_release()

# ---------------- DFPlayer Mini ----------------
def df_send(cmd, param=0):
    print("DF Send")
    data = bytearray([0xFF, 0x06, cmd, 0x00, (param >> 8) & 0xFF, param & 0xFF])
    checksum = -sum(data) & 0xFFFF
    packet = bytearray([0x7E]) + data + bytearray(
        [(checksum >> 8) & 0xFF, checksum & 0xFF, 0xEF])
    uart.write(packet)


def df_init():
    print("DF Init")
    time.sleep_ms(1000)         # let the module boot
    df_send(0x09, 2)            # select SD card
    time.sleep_ms(300)
    df_send(0x06, VOLUME)       # set volume
    time.sleep_ms(100)


def df_play_mp3_folder(n):
    print("DF Play")
    df_send(0x12, n)            # plays /MP3/000n.mp3


def df_stop():
    print("DF Stop")
    df_send(0x16)


# ---------------- Scheduling helpers ----------------
def next_time(min_ms, max_ms):
    return time.ticks_add(time.ticks_ms(), random.randint(min_ms, max_ms))


def due(t):
    return time.ticks_diff(time.ticks_ms(), t) >= 0


# ---------------- Main ----------------
def main():
    print("Start")
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

    next_head = next_time(HEAD_MIN_MS, HEAD_MAX_MS)
    
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

        # ---- Head turn (non-blocking) ----
        head_service()
        if head_pos == head_target and due(next_head):
            head_new_target()
            next_head = next_time(HEAD_MIN_MS, HEAD_MAX_MS)
            
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

        time.sleep_ms(1)


try:
    main()

except KeyboardInterrupt:
    df_stop()
    set_angle(BEAK_CLOSED_ANGLE)
    head_centre()
    led.value(0)
    servo.deinit()
    print("Stopped")
