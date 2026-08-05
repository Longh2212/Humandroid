from typing import Optional, Dict, Any

from Manager.Manager_Robot import RobotController

import time

class LED:
    """
    LED controller for humanoid robot
    """

    VALID_LED_MODES = {
        "IDLE",
        "THINK",
        "LISTEN",
        "HAPPY",
        "INFO",
        "RIGHT",
        "ERROR"
    }

    VALID_EFFECTS = {
        "breathing",
        "rotating",
        "wave",
        "blink",
        "radar"
    }

    def __init__(
        self,
        uart: RobotController
    ):

        self.uart = uart

    # =====================================
    # PREDEFINED MODE
    # =====================================
    def set_mode(
        self,
        mode: str
    ) -> Optional[Dict[str, Any]]:
        """
        Set LED predefined mode

        Example:
            led.set_mode("THINK")
        """

        mode = (
            mode.upper()
            .strip()
        )

        if mode not in self.VALID_LED_MODES:
            print(
                f"[ERROR] Invalid LED mode: "
                f"{mode}"
            )

            print(
                f"Valid modes: "
                f"{sorted(self.VALID_LED_MODES)}"
            )

            return None

        return self.uart.send_command_and_wait({
            "type": "led",
            "mode": mode
        })

    # =====================================
    # CUSTOM EFFECT
    # =====================================
    def custom_effect(
        self,
        effect: str,
        r: int = 0,
        g: int = 80,
        b: int = 200
    ) -> Optional[Dict[str, Any]]:
        """
        Custom LED animation

        Example:
            led.custom_effect(
                "wave",
                r=0,
                g=150,
                b=255
            )
        """

        effect = (
            effect.lower()
            .strip()
        )

        if effect not in self.VALID_EFFECTS:

            print(
                f"[ERROR] Invalid effect: "
                f"{effect}"
            )

            print(
                f"Valid effects: "
                f"{sorted(self.VALID_EFFECTS)}"
            )

            return None

        # Clamp RGB
        r = max(
            0,
            min(255, int(r))
        )

        g = max(
            0,
            min(255, int(g))
        )

        b = max(
            0,
            min(255, int(b))
        )

        return self.uart.send_command_and_wait({
            "type": "led",
            "effect": effect,
            "r": r,
            "g": g,
            "b": b
        })

    # =====================================
    # SHORTCUTS
    # =====================================
    def loading(self):
        return self.custom_effect(
            "wave",
            r=255,
            g=255,
            b=30
        )
    
    def think(self):
        return self.set_mode(
            "THINK"
        )

    def listen(self):
        return self.set_mode(
            "LISTEN"
        )

    def happy(self):
        return self.set_mode(
            "HAPPY"
        )

    def info(self):
        return self.set_mode(
            "INFO"
        )

    def success(self):
        return self.set_mode(
            "RIGHT"
        )

    def error(self):
        return self.set_mode(
            "ERROR"
        )

    def idle(self):
        return self.set_mode(
            "IDLE"
        )

    def off(self):
        """
        LED OFF

        Uses blink black.
        """

        return self.custom_effect(
            "blink",
            0,
            0,
            0
        )


# =====================================
# RANDOM LED TEST
# =====================================
if __name__ == "__main__":

    import random
    import time

    robot = RobotController()
    led = LED(robot)

    # Các mode có sẵn
    led_modes = list(LED.VALID_LED_MODES)

    # Các hiệu ứng custom có sẵn
    led_effects = list(LED.VALID_EFFECTS)

    print("=== RANDOM LED TEST ===")
    print("Ctrl + C để dừng")
    print("=======================")

    try:
        while True:

            # Chọn ngẫu nhiên chạy mode hoặc custom effect
            test_type = random.choice([
                "mode",
                "custom"
            ])

            delay_time = random.uniform(
                1.0,
                4.0
            )

            if test_type == "mode":
                mode = random.choice(
                    led_modes
                )

                print(
                    f"[LED MODE] {mode} | "
                    f"{delay_time:.2f}s"
                )

                led.set_mode(mode)

            else:
                effect = random.choice(
                    led_effects
                )

                r = random.randint(0, 255)
                g = random.randint(0, 255)
                b = random.randint(0, 255)

                print(
                    f"[LED CUSTOM] {effect} "
                    f"RGB=({r},{g},{b}) | "
                    f"{delay_time:.2f}s"
                )

                led.custom_effect(
                    effect=effect,
                    r=r,
                    g=g,
                    b=b
                )

            time.sleep(delay_time)

    except KeyboardInterrupt:
        print("\n[STOP] Random LED test stopped.")

        try:
            led.off()
        except Exception as e:
            print("[WARN] LED off failed:", e)

    finally:
        try:
            robot.close()
        except Exception:
            pass