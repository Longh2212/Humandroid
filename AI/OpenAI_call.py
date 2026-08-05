import os
import time
from dotenv import load_dotenv
from openai import OpenAI


class Chatbot:
    def __init__(
        self,
        prompt_path: str,
        model: str = "gpt-5-nano",
        max_history_turns: int = 10
    ):

        load_dotenv()

        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )

        self.model = model
        self.max_history_turns = max_history_turns

        # Default prompt
        self.system_prompt = self._load_prompt(prompt_path)

        # Chat memory
        self.history = []

    def _load_prompt(self, path: str) -> str:
        print(f"Loading prompt: {path}")

        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def load_prompt(self, path: str) -> str:
        """
        Public function to load another prompt.
        Example:
            planner_prompt = bot.load_prompt("planner.txt")
        """
        return self._load_prompt(path)

    def clear_history(self):
        """Reset chat memory"""
        self.history = []

    def _trim_history(self):
        """
        Keep only last N turns
        Each turn = user + assistant
        """

        max_messages = self.max_history_turns * 2

        if len(self.history) > max_messages:
            self.history = self.history[-max_messages:]

    def generate(
        self,
        user_input: str,
        system_prompt: str = None,
        use_history: bool = False,
        stream_output: bool = True
    ) -> str:

        start_time = time.time()
        first_token_time = None
        response_parts = []

        # Use default prompt if not provided
        if system_prompt is None:
            system_prompt = self.system_prompt

        # ===== Build input =====
        if use_history:

            self.history.append({
                "role": "user",
                "content": user_input
            })

            self._trim_history()

            input_messages = self.history

        else:
            input_messages = [
                {
                    "role": "user",
                    "content": user_input
                }
            ]

        try:

            with self.client.responses.stream(
                model=self.model,
                instructions=system_prompt,
                input=input_messages
            ) as stream:

                for event in stream:

                    if event.type == "response.output_text.delta":

                        if first_token_time is None:
                            first_token_time = time.time()

                            print(
                                f"\n[TTFT]: "
                                f"{first_token_time - start_time:.3f}s\n"
                            )

                        if stream_output:
                            print(
                                event.delta,
                                end="",
                                flush=True
                            )

                        response_parts.append(
                            event.delta
                        )

            full_response = "".join(
                response_parts
            )

            # Save assistant memory only in chat mode
            if use_history:

                self.history.append({
                    "role": "assistant",
                    "content": full_response
                })

                self._trim_history()

            print(
                f"\n\n[Total time]: "
                f"{time.time() - start_time:.3f}s"
            )

            return full_response

        except Exception as e:
            print("\nError:", e)
            return ""

    def generate_chat(
        self,
        user_input: str
    ) -> str:
        """
        Chat mode with memory
        """
        return self.generate(
            user_input=user_input,
            use_history=True
        )


if __name__ == "__main__":

    bot = Chatbot(
        "/home/hhl/humandroid/Prompt/chat_prompt.txt"
    )


    print(
        "Chatbot ready "
        "(type 'exit' to quit)\n"
    )

    while True:

        user_input = input(
            "\nUser: "
        )

        if user_input.lower() in [
            "exit",
            "quit"
        ]:
            break

        try:
            response = bot.generate_chat(user_input)
            print("\n\nFinal output:\n",response)

        except Exception as e:
            print("Error:", e)