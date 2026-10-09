"""
backend/main.py
FastAPI Server + CronJob tự động cào mỗi ngày.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import VN_TZ, get_history_by_week, init_db, save_real_prices, save_predicted_prices
from ai_service import fetch_sjc_price, fetch_world_price, get_gold_prediction, chat_gold

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")
scheduler = AsyncIOScheduler(timezone=VN_TZ)

def daily_crawl_job():
    """Chạy tự động cào giá thật mỗi ngày để duy trì chuỗi lịch sử."""
    logger.info("[CronJob] Cập nhật giá vàng thực tế mới nhất...")
    today_str = datetime.now(VN_TZ).strftime("%Y-%m-%d")
    sjc = fetch_sjc_price()
    world = fetch_world_price()
    if sjc:
        save_real_prices(today_str, sjc_buy=sjc["buy"], sjc_sell=sjc["sell"])
    if world:
        save_real_prices(today_str, world_price=world["sell"])

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Chạy tự động 3 lần/ngày (9h sáng, 14h chiều, 17h chiều)
    scheduler.add_job(daily_crawl_job, "cron", hour="9,14,17", minute=0)
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="Gold AI Predictor", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/gold-data")
@app.get("/api/predict")
async def get_gold_data(week: int = Query(1, ge=1, le=4)):
    # Lấy dữ liệu cào giá mới nhất & tính dự báo
    data = await get_gold_prediction() or {}
    
    # Lấy lịch sử theo tuần được chọn (1, 2, 3, 4)
    selected_week_history = get_history_by_week(week)

    # Bọc kiểm tra an toàn để tránh bị NoneType AttributeError
    cur = data.get("current") or {}
    sjc_cur = cur.get("sjc") or {}
    world_cur = cur.get("world") or {}

    current_data = {
        "date": datetime.now(VN_TZ).strftime("%Y-%m-%d"),
        "sjc_buy": sjc_cur.get("buy"),
        "sjc_sell": sjc_cur.get("sell"),
        "world_price": world_cur.get("sell"),
    }

    # CHỈ LƯU VÀ TRẢ VỀ DỰ BÁO TƯƠNG LAI KHI Ở TUẦN 1
    predictions_list = []
    if week == 1:
        forecast = data.get("forecast") or {}
        forecast_sjc = forecast.get("sjc") or []
        forecast_world = forecast.get("world") or []
        
        # Lưu vết giá dự đoán mới nhất vào DB
        save_predicted_prices(forecast_sjc, forecast_world)

        by_date = {}
        for f in forecast_sjc:
            by_date.setdefault(f["date"], {"date": f["date"]})["sjc_predict_sell"] = f.get("sell")
        for f in forecast_world:
            by_date.setdefault(f["date"], {"date": f["date"]})["world_predict"] = f.get("sell")
        predictions_list = [by_date[d] for d in sorted(by_date)]

    return {
        "selected_week": week,
        "historical_data": selected_week_history,
        "current_data": current_data,
        "predictions": predictions_list,
        "ai_analysis": data.get("analysis"),
    }

class ChatIn(BaseModel):
    message: str

@app.post("/api/chat")
async def chat(body: ChatIn):
    return {"reply": await chat_gold(body.message)}