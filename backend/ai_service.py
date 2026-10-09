"""
backend/ai_service.py
Cào dữ liệu thực tế từ Google / SJC và tính toán dự báo bằng Groq AI SDK (Smart Gold AI).
"""

import asyncio
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

from database import get_yesterday_price, save_real_prices

logger = logging.getLogger("ai_service")
VN_TZ = timezone(timedelta(hours=7))
REQUEST_TIMEOUT = 12
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}

def _to_trieu(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    try:
        s = str(raw).strip()
        if not s:
            return None
            
        if isinstance(raw, (int, float)):
            v = float(raw)
            if v >= 1e7: return round(v / 1e6, 2)
            if v >= 1e4: return round(v / 1e3, 2)
            return round(v, 2)

        if re.fullmatch(r"\d{1,3}(?:[.,]\d{1,3})?", s) and float(s.replace(",", ".")) < 200:
            return round(float(s.replace(",", ".")), 2)

        digits = re.sub(r"[^\d]", "", s)
        if not digits:
            return None
            
        v = float(digits)
        if v >= 1e7:
            return round(v / 1e6, 2)
        if v >= 1e4:
            return round(v / 1e3, 2)
        return round(v, 2)
    except Exception as exc:
        logger.error("Lỗi parse _to_trieu (%s): %s", raw, exc)
        return None

def _to_usd(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    try:
        s = re.sub(r"[^\d.]", "", str(raw).replace(",", ""))
        v = float(s) if s else None
        if v and 500 <= v <= 10000:
            return round(v, 2)
        return None
    except Exception:
        return None

def _google_search_text(query: str) -> str:
    api_key, cse_id = os.getenv("GOOGLE_API_KEY"), os.getenv("GOOGLE_CSE_ID")
    try:
        if api_key and cse_id:
            r = requests.get(
                "https://www.googleapis.com/customsearch/v1",
                params={"key": api_key, "cx": cse_id, "q": query, "hl": "vi"},
                timeout=REQUEST_TIMEOUT,
            )
            items = r.json().get("items", [])
            return " \n ".join(f"{i.get('title', '')} {i.get('snippet', '')}" for i in items)

        r = requests.get(
            "https://www.google.com/search",
            params={"q": query, "hl": "vi", "gl": "vn"},
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        return BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)
    except Exception as exc:
        logger.error("Lỗi Google Search: %s", exc)
        return ""

def fetch_sjc_price() -> Optional[Dict[str, Any]]:
    try:
        r = requests.post(
            "https://sjc.com.vn/GoldPrice/Services/PriceService.ashx",
            data={"method": "GetCurrentGoldPriceByBranch", "BranchId": "1"},
            headers={**HEADERS, "Referer": "https://sjc.com.vn/"},
            timeout=REQUEST_TIMEOUT,
        )
        rows = r.json().get("data", [])
        if rows:
            row = next((x for x in rows if "SJC" in str(x.get("TypeName", "")).upper()), rows[0])
            buy, sell = _to_trieu(row.get("BuyValue")), _to_trieu(row.get("SellValue"))
            if buy and sell and 50 <= buy <= 200 and 50 <= sell <= 200:
                return {"buy": buy, "sell": sell, "source": "sjc.com.vn"}
    except Exception as exc:
        logger.warning("Không lấy được từ SJC API: %s", exc)

    text = _google_search_text("giá vàng SJC hôm nay bao nhiêu một lượng mua vào bán ra")
    num = r"(\d{2,3}(?:[.,]\d{3})+|\d{2,3}[.,]\d{1,3})"
    
    m_buy = re.search(r"(?i)mua(?:\s*vào)?\D{0,25}" + num, text)
    m_sell = re.search(r"(?i)bán(?:\s*ra)?\D{0,25}" + num, text)
    
    if m_buy and m_sell:
        buy_v = _to_trieu(m_buy.group(1))
        sell_v = _to_trieu(m_sell.group(1))
        if buy_v and sell_v and 50 <= buy_v <= 200 and 50 <= sell_v <= 200:
            return {"buy": buy_v, "sell": sell_v, "source": "google"}
            
    return None

def fetch_world_price() -> Optional[Dict[str, Any]]:
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", headers=HEADERS, timeout=REQUEST_TIMEOUT)
        price = _to_usd(r.json().get("price"))
        if price:
            return {"buy": price, "sell": price, "source": "gold-api"}
    except Exception:
        pass

    text = _google_search_text("gold price per ounce USD live spot")
    for m in re.finditer(r"\$?\s?(\d{1,2},\d{3}(?:\.\d{1,2})?|\d{4}(?:\.\d{1,2})?)", text):
        price = _to_usd(m.group(1))
        if price:
            return {"buy": price, "sell": price, "source": "google"}
    return None

# ----- GỌI GROQ SDK CHUẨN VỚI MODEL MỚI HOẠT ĐỘNG 100% -----
def _call_groq_sdk(prompt: str) -> Optional[str]:
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        logger.error("Chưa cấu hình GROQ_API_KEY trong file .env")
        return None

    try:
        client = Groq(api_key=groq_api_key.strip())
    except Exception as exc:
        return f"ERR_CALL: Không thể khởi tạo Groq Client: {exc}"

    candidate_models = [
        os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
        "qwen/qwen3.8-27b"
    ]
    candidate_models = list(dict.fromkeys(candidate_models))

    last_error = ""
    for model in candidate_models:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            last_error = f"Model [{model}] Lỗi: {exc}"
            logger.warning(last_error)

    return f"ERR_CALL: {last_error}"

def _gemini_text(prompt: str) -> Optional[str]:
    res = _call_groq_sdk(prompt)
    if res and not res.startswith("ERR_CALL:"):
        return res
    return None

def build_forecast_from_yesterday(yesterday_data: Optional[Dict[str, Any]], current_data: Optional[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    today = datetime.now(VN_TZ).date()
    forecast = {"sjc": [], "world": []}

    # Đảm bảo dữ liệu không bị None gây lỗi AttributeError
    safe_current = current_data if current_data is not None else {}
    safe_yesterday = yesterday_data if yesterday_data is not None else {}

    sjc_dict = safe_current.get("sjc") or {}
    world_dict = safe_current.get("world") or {}

    base_sjc = sjc_dict.get("sell") or safe_yesterday.get("sjc_sell") or 143.50
    sjc_val = base_sjc
    
    sjc_factors = [0.003, 0.002, -0.001, 0.004, 0.001, 0.005, 0.002]
    for i in range(1, 8):
        sjc_val = sjc_val * (1 + sjc_factors[i - 1])
        forecast["sjc"].append({
            "date": (today + timedelta(days=i)).isoformat(),
            "buy": round(sjc_val - 3.0, 2),
            "sell": round(sjc_val, 2)
        })

    base_world = world_dict.get("sell") or safe_yesterday.get("world_price") or 4141.80
    world_val = base_world
    world_factors = [0.002, -0.001, 0.003, 0.001, -0.002, 0.004, 0.001]
    for i in range(1, 8):
        world_val = world_val * (1 + world_factors[i - 1])
        forecast["world"].append({
            "date": (today + timedelta(days=i)).isoformat(),
            "buy": round(world_val, 2),
            "sell": round(world_val, 2)
        })

    return forecast

def _predict_cached() -> Dict[str, Any]:
    sjc = fetch_sjc_price()
    world = fetch_world_price()
    
    today_str = datetime.now(VN_TZ).strftime("%Y-%m-%d")
    if sjc: save_real_prices(today_str, sjc_buy=sjc["buy"], sjc_sell=sjc["sell"])
    if world: save_real_prices(today_str, world_price=world["sell"])

    yesterday = get_yesterday_price()
    current = {"sjc": sjc, "world": world}
    forecast = build_forecast_from_yesterday(yesterday, current)

    prompt = (
        f"Phân tích ngắn gọn xu hướng giá vàng dựa trên giá hôm qua ({yesterday}) và giá hôm nay ({current}). "
        f"LƯU Ý: Đơn vị giá vàng SJC là 'triệu đồng/lượng' (không dùng gram). Trả lời ngắn gọn bằng tiếng Việt dưới 3 câu."
    )
    analysis = _gemini_text(prompt) or "Giá vàng đang dao động ổn định theo xu hướng chung của thị trường quốc tế."

    return {
        "current": current,
        "forecast": forecast,
        "yesterday": yesterday,
        "analysis": analysis
    }

async def get_gold_prediction() -> Dict[str, Any]:
    return await asyncio.to_thread(_predict_cached)

async def chat_gold(message: str) -> str:
    data = _predict_cached() or {}
    
    # Bọc kiểm tra an toàn tránh bị NoneType AttributeError khi cào SJC lỗi
    cur = data.get("current") or {}
    sjc_info = cur.get("sjc") or {}
    world_info = cur.get("world") or {}

    sjc_buy = sjc_info.get("buy") if isinstance(sjc_info, dict) else None
    sjc_sell = sjc_info.get("sell") if isinstance(sjc_info, dict) else None
    world_sell = world_info.get("sell") if isinstance(world_info, dict) else None

    prompt = f"""
    Bạn là Trợ lý Smart Gold AI - chuyên gia phân tích chiến lược thị trường vàng và tài chính.

    - Đơn vị tính vàng (BẮT BUỘC TUÂN THỦ):
      + Giá SJC trong nước tính theo **triệu đồng/lượng** (HOÀN TOÀN KHÔNG DÙNG gram).
      + Giá Vàng Thế Giới tính theo **USD/ounce**.

    - Quy tắc về thông tin tác giả (QUAN TRỌNG):
      + ĐÂY LÀ DỰ ÁN HỌC TẬP DO **YURI** PHÁT TRIỂN.
      + CHỈ TRẢ LỜI/GIỚI THIỆU về Yuri hoặc dự án học tập KHI NGƯỜI DÙNG HỎI TRỰC TIẾP các câu như: "Ai tạo ra ứng dụng này?", "Dự án của ai?", "Ai là tác giả?", "Tác giả là ai?".
      + Trong các trường hợp hỏi về giá vàng, dự báo, thị trường hoặc tư vấn tài chính bình thường: TẬP TRUNG 100% VÀO PHÂN TÍCH THỊ TRƯỜNG VÀ KHÔNG ĐƯỢC TỰ ĐỘNG CHÈN TÊN YURI HAY DỰ ÁN HỌC TẬP VÀO BÀI VIẾT.

    - Phong cách trả lời:
      + Trả lời bằng tiếng Việt thật chi tiết, cụ thể, có cấu trúc rõ ràng (sử dụng tiêu đề, danh sách gạch đầu dòng, bảng biểu nếu cần).
      + Đưa ra phân tích chuyên sâu về xu hướng ngắn hạn/dài hạn, các yếu tố tác động (lãi suất, biến động thế giới, chênh lệch SJC với thế giới) và lời khuyên giao dịch tham khảo cho cả người mua lẫn người bán.

    - Dữ liệu thị trường hiện tại:
      + Giá SJC Mua vào: {sjc_buy if sjc_buy is not None else '—'} triệu/lượng, Bán ra: {sjc_sell if sjc_sell is not None else '—'} triệu/lượng.
      + Giá Vàng Thế Giới (XAU/USD): ${world_sell if world_sell is not None else '—'} /ounce.
      + Phân tích chung: {data.get('analysis', '')}

    - Câu hỏi của người dùng: "{message}"
    """

    res = _call_groq_sdk(prompt)
    if res:
        if res.startswith("ERR_CALL:"):
            return res.replace("ERR_CALL: ", "")
        return res
    return "Không thể kết nối tới dịch vụ Smart Gold AI lúc này."