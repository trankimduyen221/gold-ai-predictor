🌟 Smart Gold AI - Real-time Gold Price Forecasting & AI Assistant

> Hệ thống Web theo dõi giá vàng thực tế, tự động cập nhật và sửa lỗi dữ liệu cuối ngày, dự báo cuốn chiếu 7 ngày và tích hợp Chatbot AI hỏi đáp thời gian thực.

---

## 🚀 Live Demo & Access
* **Frontend (Vercel):** https://gold-ai-predictor.vercel.app
* **Backend API (Render):** `https://gold-ai-predictor.onrender.com`

---

## 🏗️ 1. Kiến trúc & Công nghệ (Tech Stack)

* **Backend Framework:** FastAPI (Python 3.10+), Uvicorn ASGI Server.
* **Database:** SQLite (Sử dụng SQLAlchemy ORM) - Gọn nhẹ, lưu trữ local, dễ đem đi demo.
* **AI Chatbot & Analysis:** Groq AI / Google Generative AI qua SDK chính thức.
* **Data Fetching:** Thư viện `httpx` hoặc `requests` (Gọi API bên thứ 3 hoặc cào dữ liệu tối ưu, chống chặn IP).
* **Frontend Framework:** React, Tailwind CSS, Recharts (Vẽ biểu đồ đường trực quan).

---

## 🗄️ 2. Thiết kế Cơ sở dữ liệu (Database Schema)

Hệ thống chỉ lưu trữ dữ liệu thực tế (**Real Data**) trong Database để đảm bảo dữ liệu sạch và tối ưu dung lượng. Phần dữ liệu dự báo sẽ được tính toán trực tiếp khi gọi API (On-the-fly).

### Bảng: `gold_history`
* `date` (DATE, Primary Key): Ngày ghi nhận dữ liệu (Ví dụ: `2026-10-03`).
* `sjc_buy` (FLOAT): Giá mua thực tế chốt phiên (Triệu VNĐ/Lượng).
* `sjc_sell` (FLOAT): Giá bán thực tế chốt phiên (Triệu VNĐ/Lượng).
* `world_price` (FLOAT): Giá vàng thế giới chốt phiên (USD/Ounce).

---

## 🔄 3. Luồng xử lý dữ liệu chính (Core Pipeline)

* **API Lấy Dữ Liệu Vẽ Biểu Đồ (`GET /api/gold-data`):** Tổng hợp dữ liệu từ 3 nguồn gồm Quá khứ (từ bảng `gold_history`), Hôm nay ($T_0$ - gọi API cập nhật mới nhất), và Tương lai ($T_{+1} \rightarrow T_{+7}$ - tính toán cuốn chiếu tự động dựa trên độ lệch ngẫu nhiên kỹ thuật).
* **Cơ Chế Tự Động Sửa Dữ Liệu Cuối Ngày (Auto-Correction & Clean Data):** Kích hoạt background task tự động lúc 00:05 mỗi ngày để lấy giá đóng cửa thực tế, thực hiện lệnh `UPSERT` ghi đè dữ liệu thật vào bảng `gold_history` làm điểm tựa tính toán mới.
* **Tích Hợp Chatbot AI Hỏi Đáp (`POST /api/chat`):** Đóng gói dữ liệu giá thực tế và chuỗi dự báo thành Prompt có cấu trúc gửi lên AI Model để chuyên gia tài chính ảo phân tích và trả về câu trả lời tự nhiên.

---

## 🌐 Chi tiết cấu trúc API (API Specification)

### 1. API Lấy Dữ Liệu
* **Endpoint:** `GET /api/gold-data`
* **Response Body JSON:**
```json
{
  "historical_data": [
    { "date": "2026-09-26", "sjc_buy": 140.2, "sjc_sell": 143.2, "world_price": 4180.0 }
  ],
  "current_data": {
    "date": "2026-10-03", "sjc_buy": 141.1, "sjc_sell": 144.1, "world_price": 4196.2
  },
  "predictions": [
    { "date": "2026-10-04", "sjc_predict_sell": 144.45, "world_predict": 4199.1 }
  ]
}
```


### 2. API Chatbot AI
* **Endpoint:** `POST /api/chat`
* **Request Body:** `{ "message": "Có nên mua vàng lúc này không bạn?" }`
* **Response Body:** `{ "reply": "Dựa trên dữ liệu hệ thống, giá vàng SJC đang có xu hướng đi ngang..." }`

---

## ⚙️ Hướng dẫn cài đặt và chạy Local (Getting Started)

### 1. Clone repository
```bash
git clone https://github.com/trankimduyen221/gold-ai-predictor.git
cd gold-ai-predictor

```

### 2. Chạy Backend (FastAPI)

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Trên Windows: venv\Scripts\activate
pip install -r requirements.txt
# Tạo file .env chứa các API Key cần thiết
cat <<EOT > .env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_CSE_ID=your_google_cse_id_here
EOT
uvicorn main:app --reload --port 8000

```

### 3. Chạy Frontend (React)

```bash
cd ../frontend
npm install
npm run dev

