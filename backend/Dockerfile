# 1. Sử dụng Python 3.11-slim để tăng hiệu năng xử lý async/FastAPI
FROM python:3.11-slim

# Biến môi trường giúp Python chạy tối ưu trong container (không ghi pyc, output không buffered)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 2. Cài đặt các thư viện hệ thống cần thiết (nếu có thư viện mã hóa/C mở rộng)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 3. Copy requirements.txt trước để tận dụng Docker Layer Caching (giúp build lại cực nhanh)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 4. Copy mã nguồn ứng dụng
COPY . .

EXPOSE 8000

# 5. Khởi chạy Uvicorn với httptools/uvloop nếu cần (hoặc dùng mặc định chuẩn FastAPI)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]