# Humandroid Project


## Giới thiệu (Introduction)
Dự án **Humandroid** là một hệ thống robot hình người tích hợp Trí tuệ Nhân tạo (AI). Dự án bao gồm các thành phần về nhận diện hình ảnh (Vision), giao tiếp ngôn ngữ tự nhiên (AI Assistant), điều khiển động học ngược (Inverse Kinematics - IK), và kiểm soát các module phần cứng như cánh tay, đầu, và đèn LED.

Dự án này là minh chứng cho việc kết hợp giữa phần cứng và phần mềm để tạo ra một hệ thống robot có khả năng tương tác.

## Tính năng nổi bật (Key Features)
- 🧠 **AI Assistant:** Trợ lý ảo tích hợp LLM (OpenAI) để giao tiếp và lập kế hoạch (Planner).
- 👁️ **Robot Vision:** Khả năng nhận diện hình ảnh và môi trường xung quanh.
- 🦾 **Điều khiển Động học (Kinematics):** Sử dụng thuật toán Inverse Kinematics (IK.py) để điều khiển cánh tay robot mượt mà.
- 🗣️ **Giao tiếp Âm thanh:** Khả năng nghe (AI_Listen) và nói (AI_speak).
- 🎮 **Module phần cứng:** Kiểm soát linh hoạt Đầu (Head), Tay (Hand), và hệ thống Đèn (Light).
- 🖥️ **Giao diện Debug/Monitor:** Màn hình LCD và phần mềm để theo dõi trạng thái hệ thống.

## Cấu trúc thư mục (Directory Structure)
```text
humandroid/
├── AI/                     # Các script liên quan đến AI (Planner, Chatbot, Call API)
├── Manager/                # Quản lý các task và state của robot
├── Prompt/                 # Chứa các prompt text cho AI
├── Source/                 # Mã nguồn phụ trợ (Audio, Model...)
├── Vision/                 # Xử lý hình ảnh và computer vision
├── config.yaml             # Cấu hình hệ thống (paths, thiết bị âm thanh)
├── AI_assisstant.py        # Code chính của trợ lý AI
├── IK.py                   # Inverse Kinematics cho cánh tay robot
├── Robot_Vision.py         # Code thị giác máy tính của robot
├── Robot_handcontrol.py    # Điều khiển cánh tay
├── Robot_headcontrol.py    # Điều khiển đầu
├── Robot_lightcontrol.py   # Điều khiển đèn LED
└── main.py                 # File thực thi chính của dự án
```

## Yêu cầu hệ thống (Requirements)
- **Phần cứng:**
  - Micro (USB PnP Sound Device)
  - Loa (plughw:CARD=MAX98357A,DEV=0)
  - Màn hình LCD 3.5 inch (tuỳ chọn)
  - Các module Servo cho tay, đầu, miệng...
- **Phần mềm:**
  - Python 3.x
  - OpenAI API Key (cấu hình qua biến môi trường `OPENAI_API_KEY`)
  - Các thư viện Python (liệt kê trong `requirements.txt` nếu có)

## Cài đặt (Installation)
1. Clone repository này:
   ```bash
   git clone https://github.com/your-username/humandroid.git
   cd humandroid
   ```
2. Tạo môi trường ảo (Virtual Environment):
   ```bash
   python -m venv venv
   source venv/bin/activate  # Trên Windows: venv\Scripts\activate
   ```
3. Cài đặt các thư viện cần thiết:
   ```bash
   # Nếu có requirements.txt
   pip install -r requirements.txt 
   ```
4. Thiết lập API Key:
   Tạo file `.env` ở thư mục gốc và thêm:
   ```env
   OPENAI_API_KEY=your_api_key_here
   ```

## Hướng dẫn sử dụng (Usage)
Chạy file thực thi chính:
```bash
python main.py
```

## Đóng góp (Contributing)
Mọi đóng góp cho dự án đều được hoan nghênh. Vui lòng tạo Pull Request hoặc mở Issue nếu bạn gặp bất kỳ vấn đề gì.

## Tác giả (Author)
- **[Tên của bạn]** - *Project Lead / Developer* - [Link GitHub của bạn/LinkedIn]

## Giấy phép (License)
Dự án được phân phối dưới giấy phép [MIT](LICENSE). Xem file `LICENSE` để biết thêm chi tiết.
