import os
import yaml
import json
import time
from AI.OpenAI_call import Chatbot
from typing import Dict, Any


class Planner:
    def __init__(self, config_path: str = "/home/hhl/humandroid/config.yaml"):
        self.config_path = config_path
        
        # Load config với error handling
        try:
            with open(self.config_path, "r", encoding="utf-8") as file:
                self.config = yaml.safe_load(file)
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file not found: {config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML config: {e}")

        # Prompt paths
        prompt_dir = self.config["location"]["prompt_path"]
        plan_prompt_path = os.path.join(prompt_dir, "plan.md")

        # Khởi tạo Chatbot đúng cách
        self.openAI = Chatbot(
            prompt_path=plan_prompt_path,   # Truyền luôn prompt cho planner
            model=self.config.get("model", "gpt-5.4-nano-2026-03-17"),
            max_history_turns=5
        )

        print(f"Planner initialized with prompt: {plan_prompt_path}")

    def get_plan(self, text: str) -> Dict[str, Any]:
        """
        Generate planning result from user task.
        """
        start_time = time.time()
        
        try:
            response = self.openAI.generate(
                user_input=text,
                system_prompt=None,           # Sử dụng prompt đã load trong Chatbot
                use_history=False,
                stream_output=False
            )

            if not response:
                raise ValueError("Empty response from model")

            # Clean markdown code block
            cleaned_response = (
                response
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )

            plan_json = json.loads(cleaned_response)

            print(f"[Planner] Time: {time.time() - start_time:.3f}s")
            return plan_json

        except json.JSONDecodeError as e:
            print("[Planner] JSON Decode Error")
            print("Raw response:\n", response)
            return {
                "success": False,
                "error": "Invalid JSON format",
                "raw_response": response,
                "message": str(e)
            }
        except Exception as e:
            print(f"[Planner] Error: {e}")
            return {
                "success": False,
                "error": str(e),
                "raw_response": response if 'response' in locals() else None
            }


if __name__ == "__main__":
    try:
        planner = Planner()
        result = planner.get_plan("xin chao ban, ban ten la gi")
        print("\n=== RESULT ===")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print("Initialization Error:", e)
