import os
import yaml
import time
from typing import Dict, Any, List, Optional

from AI.OpenAI_call import Chatbot


class Answer:
    def __init__(self, config_path="/home/hhl/humandroid/config.yaml"):
        self.config_path = config_path

        # =========================
        # Load config
        # =========================
        try:
            with open(self.config_path, "r", encoding="utf-8") as file:
                self.config = yaml.safe_load(file)
        except Exception as e:
            raise Exception(f"Không thể load config: {e}")

        # =========================
        # Prompt path
        # =========================
        prompt_dir = self.config["location"]["prompt_path"]
        chat_prompt_path = os.path.join(
            prompt_dir,
            "RAI_system_prompt.md"
        )

        # =========================
        # Init Chatbot with memory
        # =========================
        self.openAI = Chatbot(
            prompt_path=chat_prompt_path,
            model=self.config.get(
                "model",
                "gpt-5.4-nano-2026-03-17"
            ),
            max_history_turns=20
        )

        print("✅ Answer Bot đã sẵn sàng (có nhớ lịch sử)")

    # ==================================================
    # 1. Main answer function
    # ==================================================

    def get_answer(
        self,
        text: str,
        stream_output: bool = True
    ) -> str:
        """
        Trả lời câu hỏi của người dùng.
        Lịch sử hội thoại được quản lý trong self.openAI.history.
        """

        start_time = time.time()

        if not text or text.strip() == "":
            return "Tôi chưa nghe rõ câu hỏi của bạn."

        try:
            response = self.openAI.generate_chat(
                user_input=text
            )

            if not response or response.strip() == "":
                response = "Xin lỗi, tôi không thể trả lời lúc này."

            print(f"[Answer Time]: {time.time() - start_time:.3f}s")

            return response

        except Exception as e:
            print(f"[Answer Error]: {e}")
            return "Đã xảy ra lỗi khi xử lý. Bạn thử hỏi lại nhé."

    # ==================================================
    # 2. Add context manually
    # ==================================================
    
    def add_context(
        self,
        role: str,
        content: str
    ):
        """
        Thêm context trực tiếp vào lịch sử của LLM.

        Dùng cho các thông tin không đến trực tiếp từ người dùng,
        ví dụ:
        - robot vừa lấy vật thành công
        - robot không tìm thấy vật
        - robot thấy vật nhưng ngoài tầm với
        """

        if role not in ["system", "user", "assistant"]:
            role = "system"

        if not content or content.strip() == "":
            return

        if not hasattr(self.openAI, "history"):
            print("[WARN] Chatbot không có thuộc tính history.")
            return

        self.openAI.history.append({
            "role": role,
            "content": content.strip()
        })

        self._trim_history()

    # ==================================================
    # 3. Add robot task result
    # ==================================================
    
    def add_task_result(
        self,
        task_name: str,
        user_text: str,
        result: Optional[Dict[str, Any]]
    ):
        """
        Lưu kết quả task vật lý của robot vào context LLM.

        Sau đó nếu người dùng hỏi:
        - có lấy được không?
        - sao không lấy được?
        - vừa làm gì?
        - vật ở đâu?
        thì LLM sẽ biết trạng thái trước đó.
        """

        if result is None:
            content = f"""
Robot vừa thực hiện một nhiệm vụ nhưng không có kết quả trả về.

Câu nói của người dùng:
{user_text}

Tên nhiệm vụ:
{task_name}

Kết quả:
- success: False
- status: unknown_error
- message: Robot không xử lý được nhiệm vụ này.

Nếu người dùng hỏi tiếp, hãy giải thích rằng robot chưa xử lý được nhiệm vụ vừa rồi.
"""
        else:
            success = result.get("success", False)
            status = result.get("status", "unknown")
            message = result.get("message", "")
            data = result.get("data", None)

            content = f"""
Robot vừa thực hiện một nhiệm vụ.

Câu nói của người dùng:
{user_text}

Tên nhiệm vụ:
{task_name}

Kết quả nhiệm vụ:
- success: {success}
- status: {status}
- message: {message}

Dữ liệu phụ:
{data}

Gợi ý diễn giải trạng thái:
- not_found: robot không tìm thấy vật.
- ik_failed: robot thấy vật nhưng lỗi tính toán động học ngược.
- unreachable: robot thấy vật nhưng vật nằm ngoài tầm với.
- grabbed: robot đã cầm được vật.
- recognized: robot đã nhận diện được vật.
- missing_obj_type: robot chưa biết người dùng muốn lấy vật gì.
- unknown_error: robot gặp lỗi không xác định.

Nếu người dùng hỏi tiếp như:
- có lấy được không?
- sao không lấy được?
- vừa làm gì?
- vật đó ở đâu?
- có thấy vật không?
hãy dựa vào kết quả nhiệm vụ trên để trả lời ngắn gọn, tự nhiên bằng tiếng Việt.
"""

        self.add_context(
            role="system",
            content=content
        )

    # ==================================================
    # 4. Build task response by LLM
    # ==================================================
    
    def get_task_response(
        self,
        task_name: str,
        user_text: str,
        result: Optional[Dict[str, Any]],
        stream_output: bool = True
    ) -> str:
        """
        Dùng khi muốn LLM tự tạo câu phản hồi sau khi robot làm task.

        Ví dụ:
        Robot lấy vật thất bại.
        Thay vì nói cứng result["message"],
        có thể gọi hàm này để LLM nói tự nhiên hơn.

        Tuy nhiên hàm này sẽ gọi LLM thêm một lần,
        nên có thể chậm hơn.
        """

        self.add_task_result(
            task_name=task_name,
            user_text=user_text,
            result=result
        )

        if result is None:
            prompt = f"""
Robot vừa thực hiện nhiệm vụ {task_name} nhưng không có kết quả.
Hãy nói với người dùng thật ngắn gọn rằng robot chưa xử lý được nhiệm vụ này.
"""
        else:
            prompt = f"""
Người dùng vừa yêu cầu:
{user_text}

Robot đã thực hiện nhiệm vụ:
{task_name}

Kết quả:
- success: {result.get("success")}
- status: {result.get("status")}
- message: {result.get("message")}
- data: {result.get("data")}

Hãy trả lời người dùng ngắn gọn, tự nhiên, giống robot đang báo cáo kết quả.
Không cần giải thích dài.
Tuyệt đối không nói confidence, độ tự tin dạng số, bbox, area_ratio, tọa độ ảnh,
JSON, status, raw data, tên model hoặc tên thuật toán.
Nếu object_name là tiếng Anh, hãy dịch sang tiếng Việt trước khi trả lời.
Ví dụ: bottle -> cái chai, cup -> cái cốc, book -> quyển sách.
"""

        return self.get_answer(
            text=prompt,
            stream_output=stream_output
        )
    def get_recognize_response(user_text, recognize_result):
        """
        Gửi kết quả YOLO cho LLM để tạo câu trả lời tự nhiên.
        Không gửi ảnh, chỉ gửi thông tin object.
        """

        try:
            obj_name = recognize_result.get("data", {}).get("object_name")
            obj = recognize_result.get("data", {}).get("object", {})
            all_objects = recognize_result.get("data", {}).get("all_valid_objects", [])

            context = {
                "user_text": user_text,
                "task": "recognize",
                "status": recognize_result.get("status"),
                "object_name": obj_name,
                "best_object": obj,
                "all_objects": all_objects
            }

            prompt = f"""
    Bạn là robot Humandroid.

    Người dùng vừa hỏi:
    "{user_text}"

    YOLO đã nhận diện được thông tin sau:
    {context}

    Hãy trả lời người dùng bằng tiếng Việt.

    Yêu cầu:
    - Trả lời ngắn gọn, tự nhiên, giống robot đang nói.
    - Không nói theo kiểu máy móc như JSON.
    - Nếu nhận diện được vật, hãy nói tự nhiên như:
      "Mình thấy đây có vẻ là một cái chai."
      hoặc "Tôi nghĩ đây là một chiếc cốc."
    - Nếu confidence thấp, hãy nói không chắc chắn.
    - Nếu không có vật phù hợp, hãy nói rằng bạn chưa nhận ra vật nào rõ ràng.
    - Không bịa thêm thông tin ngoài dữ liệu YOLO.
    """

            response = answer.get_answer(
                prompt,
                stream_output=True
            )

            return response

        except Exception as e:
            print("[RECOGNIZE LLM RESPONSE ERROR]", e)

            return recognize_result.get(
                "message",
                "Tôi chưa nhận diện được vật này."
            )
    # ==================================================
    # 5. History control
    # ==================================================

    def clear_history(self):
        """
        Xóa toàn bộ lịch sử hội thoại.
        """

        if hasattr(self.openAI, "clear_history"):
            self.openAI.clear_history()
        elif hasattr(self.openAI, "history"):
            self.openAI.history = []

        print("Đã xóa lịch sử hội thoại.")

    def get_history(self) -> List[Dict[str, str]]:
        """
        Lấy lịch sử hiện tại.
        """

        if not hasattr(self.openAI, "history"):
            return []

        return self.openAI.history

    def print_history(self):
        """
        In lịch sử hội thoại ra terminal.
        """

        history = self.get_history()

        print()
        print(f"📜 Lịch sử hội thoại ({len(history)} messages):")

        for i, msg in enumerate(history):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if role == "user":
                role_name = "👤 User"
            elif role == "assistant":
                role_name = "🤖 Bot"
            elif role == "system":
                role_name = "⚙️ System"
            else:
                role_name = role

            short_content = content[:150]
            if len(content) > 150:
                short_content += "..."

            print(f"{i + 1}. {role_name}: {short_content}")

    def _trim_history(self):
        """
        Cắt bớt history nếu quá dài.

        Lưu ý:
        Chatbot của bạn có max_history_turns=20.
        Tuy nhiên vì mình thêm system context thủ công,
        nên cắt thêm ở đây để tránh history quá dài.
        """

        if not hasattr(self.openAI, "history"):
            return

        max_messages = 40

        if len(self.openAI.history) > max_messages:
            self.openAI.history = self.openAI.history[-max_messages:]

    # ==================================================
    # 6. Helper format result
    # ==================================================

    @staticmethod
    def make_result(
        success: bool,
        status: str,
        message: str,
        data: Any = None
    ) -> Dict[str, Any]:
        """
        Tạo format result chuẩn cho các task.

        Ví dụ:
        result = Answer.make_result(
            success=True,
            status="grabbed",
            message="Tôi đã cầm được chai.",
            data={"obj": "bottle"}
        )
        """

        return {
            "success": success,
            "status": status,
            "message": message,
            "data": data
        }


# ======================
# Test terminal
# ======================

if __name__ == "__main__":
    bot = Answer()

    print()
    print("Chatbot sẵn sàng.")
    print("Gõ 'exit' để thoát.")
    print("Gõ 'clear' để xóa lịch sử.")
    print("Gõ 'history' để xem lịch sử.")
    print("Gõ 'fake_take' để test context lấy vật.")
    print()

    while True:
        user_input = input("You: ")

        if user_input.lower() in ["exit", "quit"]:
            break

        if user_input.lower() == "clear":
            bot.clear_history()
            continue

        if user_input.lower() == "history":
            bot.print_history()
            continue

        if user_input.lower() == "fake_take":
            fake_result = {
                "success": False,
                "status": "not_found",
                "message": "Tôi không tìm thấy bottle.",
                "data": {
                    "obj_type": "bottle",
                    "scan": None,
                    "ik": None
                }
            }

            bot.add_task_result(
                task_name="take_obj",
                user_text="Lấy chai nước cho tôi",
                result=fake_result
            )

            print("Đã thêm context giả: robot không tìm thấy bottle.")
            continue

        response = bot.get_answer(
            user_input,
            stream_output=True
        )

        print()
        print(f"Bot: {response}")
        print()