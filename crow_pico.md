Using a DFPlayer Mini (or compatible) MP3 module with an SD card. The 0001.mp3 naming matches how it works. 

Wiring (Pico GPIO numbers)

|Part	|Connection|
|----|----|
|LED	|GP15, through a ~220Ω resistor, to GND|
|MG90 servo signal (orange/yellow)	|GP16|
|Servo power (red)	|5V (VBUS, or better, a separate 5V supply)|
|Servo ground (brown)	|GND (shared with the Pico)|
|DFPlayer VCC	|5V (VBUS)|
|DFPlayer GND	|GND|
|DFPlayer RX	|GP0 (UART0 TX), through a ~1kΩ resistor|
|DFPlayer TX	|GP1 (UART0 RX)|
|DFPlayer BUSY	|GP2|
|DFPlayer SPK1 and SPK2	|Small speaker (or DAC outputs to an amplifier)|

**SD card:** FAT32, with the files in a folder named exactly MP3: /MP3/0001.mp3 to /MP3/0014.mp3.
## How it behaves

* The LED stays on, then goes off for 150 ms every 5 to 10 seconds (random).
* A squawk fires every 10 to 20 seconds, counted from the end of the previous one. It picks one of the 14 files at random, never the same one twice in a row.
* The beak opens when the sound is triggered and closes when the DFPlayer’s BUSY pin goes high again.
* Everything is non-blocking, so blinking carries on during a squawk.
* Ctrl+C in Thonny stops the sound, closes the beak and turns the LED off. The 3-second startup delay also gives you time to interrupt it, which helps with the stop problem you had earlier.

## Tuning and troubleshooting
* **Beak angles**: the servo’s 0° may be at its mechanical limit. If it buzzes or strains, set BEAK_CLOSED_ANGLE to something like 20 and keep BEAK_OPEN_ANGLE at 20 so the beak opens by 20° from there. Flip the numbers if it moves the wrong way.
* **Servo power**: if the Pico resets or the audio crackles when the servo moves, power the servo from a separate 5V supply (sharing GND) or add a 470µF capacitor across the servo’s power leads.
* **No sound**: check that the folder is named MP3 in capitals and the SD card is FAT32. If your files are directly in the root instead, change df_send(0x12, n) to df_send(0x03, n), which plays by file order, so copy them in order onto a freshly formatted card.
* **Audio noise**: the 1kΩ resistor on the DFPlayer RX line reduces hiss and corruption from the Pico’s 3.3V TX line.
