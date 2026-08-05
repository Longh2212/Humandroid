import spidev
import RPi.GPIO as GPIO
import time

# Define the control commands for XPT1040 (refer to the chip datasheet for specific commands)
COMMAND_X = 0x90  # Command to read X coordinate
COMMAND_Y = 0xD0  # Command to read Y coordinate

MAX_X   = 480
MAX_Y   = 320

# Suggested calibration steps
# Properly define calibration parameters in hr2046.py (replace with actual measured values)

# INT pin
INT_PIN         = 4
RST_PIN         = 1

class hr2046():
    def __init__(self) -> None:
        # Set up GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(17, GPIO.IN)  # Touch interrupt pin, assuming connected to GPIO17
        
        # Initialize SPI communication
        self.SPI = spidev.SpiDev()
        self.SPI.open(0, 1)  # SPI bus 0, device 0
        self.SPI.max_speed_hz = 50000  # Set SPI speed (specific speed depends on the situation)

    def read_touch_data(self):
        # Read X coordinate
        x_response = self.SPI.xfer2([COMMAND_X, 0x00])
        x_raw = ((x_response[0] & 0x0F) << 8) | x_response[1]  # Combine high 4 bits and low 8 bits to get a 12-bit ADC value (range 0-4095)
        x = x_raw * 4  # Directly multiplying by 3 here causes coordinates to exceed screen range

        # Read Y coordinate raw ADC value (implicitly y_raw)
        y_response = self.SPI.xfer2([COMMAND_Y, 0x00])
        y_raw = ((y_response[0] & 0x0F) << 8) | y_response[1]  # Same as above
        y = 320 - (y_raw * 3)  # Directly multiplying by 2 and flipping the coordinate axis
        return int(x), int(y)
