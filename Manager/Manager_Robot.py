import time
import json
import serial
import sys
import threading
from typing import Optional, Dict, Any, List


class RobotController:
    """UART controller for Raspberry Pi <-> ESP32 robot"""

    VALID_LED_MODES = [
        "IDLE", "THINK", "LISTEN",
        "HAPPY", "INFO", "RIGHT", "ERROR"
    ]

    VALID_EFFECTS = [
        "breathing",
        "rotating",
        "wave",
        "blink",
        "radar"
    ]

    def __init__(
        self,
        port: str = "/dev/serial0",
        baudrate: int = 115200,
        timeout: float = 0.5,
        outlog = False,
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None
        self.lock = threading.Lock()
        self.outlog = outlog
        self._connect()

    # ==================================================
    # UART CONNECTION
    # ==================================================
    def _connect(self):
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=1
            )

            time.sleep(2)  # wait ESP32 boot

            print(
                f"[OK] Connected to ESP32 "
                f"via {self.port} @ {self.baudrate}"
            )

            self.clear_buffer()

        except Exception as e:
            print(f"[ERROR] Failed to open UART {self.port}: {e}")
            sys.exit(1)

    # ==================================================
    # LOW LEVEL UART
    # ==================================================
    def send_command(self, cmd_dict: Dict[str, Any]) -> bool:
        """Send JSON command without waiting response"""

        if not self.ser or not self.ser.is_open:
            print("[ERROR] Serial port not open")
            return False

        try:
            with self.lock:
                json_str = (
                    json.dumps(
                        cmd_dict,
                        ensure_ascii=False
                    ) + "\n"
                )

                self.ser.write(json_str.encode("utf-8"))
                self.ser.flush()
            
            if self.outlog == True: print(f"[SENT] {json_str.strip()}")
            return True

        except Exception as e:
            print(f"[ERROR] Send error: {e}")
            return False

    def read_response(self) -> Optional[Dict]:
        """Read JSON response from ESP32"""

        if not self.ser or not self.ser.is_open:
            return None

        try:
            if self.ser.in_waiting > 0:
                line = (
                    self.ser.readline()
                    .decode("utf-8", errors="ignore")
                    .strip()
                )

                if not line:
                    return None

                if self.outlog == True: print(f"[RECEIVED] ESP32: {line}")

                try:
                    return json.loads(line)

                except json.JSONDecodeError:
                    return {
                        "status": "raw",
                        "message": line
                    }

        except Exception as e:
            print(f"[ERROR] Read error: {e}")

        return None

    def send_command_and_wait(
        self,
        cmd_dict: Dict[str, Any],
        timeout: float = 3.0
    ) -> Optional[Dict]:
        """
        Send command and wait for ESP32 response
        """

        self.clear_buffer()

        if not self.send_command(cmd_dict):
            return None

        start_time = time.time()

        while time.time() - start_time < timeout:

            response = self.read_response()

            if response:
                if "status" in response:
                    return response

            time.sleep(0.02)

        print("[WARNING] Timeout waiting ESP32")
        return None

    def clear_buffer(self):
        """Clear UART RX buffer"""

        if self.ser and self.ser.is_open:

            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            time.sleep(0.05)

    # ==================================================
    # LED
    # ==================================================
    def set_led_mode(self, mode: str):

        mode = mode.upper()

        if mode not in self.VALID_LED_MODES:
            print(
                f"[ERROR] Invalid LED mode: {mode}"
            )
            return None

        return self.send_command_and_wait({
            "type": "led",
            "mode": mode
        })

    def set_custom_led(
        self,
        effect: str,
        r: int = 0,
        g: int = 80,
        b: int = 200
    ):

        effect = effect.lower()

        if effect not in self.VALID_EFFECTS:
            print(
                f"[ERROR] Invalid effect: {effect}"
            )
            return None

        return self.send_command_and_wait({
            "type": "led",
            "effect": effect,
            "r": int(r),
            "g": int(g),
            "b": int(b)
        })

    # ==================================================
    # SERVO
    # ==================================================
    def move_servo(
        self,
        servo_id: int,
        angle: int
    ):
        """
        Move one servo

        Example:
        move_servo(0, 120)
        """

        servo_id = int(servo_id)
        angle = int(angle)

        return self.send_command_and_wait({
            "type": "servo",
            "id": servo_id,
            "angle": angle
        })

    def move_multi_servo(
        self,
        moves: List[Dict]
    ):
        """
        Move multiple servos synchronously

        Example:
        [
            {"id":0,"angle":120},
            {"id":1,"angle":90}
        ]
        """

        cleaned_moves = []

        for move in moves:
            cleaned_moves.append({
                "id": int(move["id"]),
                "angle": int(move["angle"])
            })

        return self.send_command_and_wait({
            "type": "multi_servo",
            "moves": cleaned_moves
        })

    # ==================================================
    # CLOSE
    # ==================================================
    def close(self):

        if self.ser and self.ser.is_open:
            self.ser.close()
            print("[INFO] UART closed")
# ================== MAIN PROGRAM ==================
if __name__ == "__main__":
    controller = RobotController()
    controller.clear_buffer()

    print("\n=== Raspberry Pi 5 - ESP32 Robot Controller (with response wait) ===")
    
    try:
        while True:
            print("\n" + "="*60)
            print("1. IDLE     2. LISTEN    3. THINK     4. HAPPY")
            print("5. INFO     6. RIGHT     7. ERROR     8. Custom LED")
            print("s. Test Servo     m. Multi Servo     q. Quit")
            print("="*60)

            choice = input("\nEnter choice: ").strip().lower()

            if choice in ['1','2','3','4','5','6','7']:
                modes = ["IDLE","LISTEN","THINK","HAPPY","INFO","RIGHT","ERROR"]
                controller.set_led_mode(modes[int(choice)-1])

            elif choice == '8':
                effect = input("Effect (breathing/rotating/wave/blink/radar): ").strip().lower()
                r = int(input("Red (0-255): ") or 0)
                g = int(input("Green (0-255): ") or 80)
                b = int(input("Blue (0-255): ") or 200)
                controller.set_custom_led(effect, r, g, b)

            elif choice == 's':
                servo_id = int(input("Servo ID: ") or 0)
                angle = int(input("Angle (0-180): ") or 90)
                controller.move_servo(servo_id, angle)

            elif choice == 'm':
                print("Enter servos (example: 0 90, 1 120, 3 45)")
                moves = []
                while True:
                    line = input("Servo ID Angle (or press Enter to finish): ").strip()
                    if not line:
                        break
                    try:
                        sid, sang = map(int, line.split())
                        moves.append({"id": sid, "angle": sang})
                    except:
                        print("Wrong format!")
                if moves:
                    controller.move_multi_servo(moves)

            elif choice == 'q':
                break

            else:
                print(" Invalid choice!")

            time.sleep(0.2)  # small to prevent spam

    except KeyboardInterrupt:
        print("\n\n Program stopped by user.")
    except Exception as e:
        print(f"\n Error: {e}")
    finally:
        controller.close()
