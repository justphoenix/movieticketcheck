import os
import time
import threading
import requests
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# 全局状态变量 (保存在云端内存中)
monitor_state = {
    "is_running": False,
    "cinemas": [],
    "movie": "",
    "date": "",
    "seen_shows": []
}
recent_logs = []

# 推送配置 (部署时在环境变量中配置)
BARK_KEY = os.environ.get("BARK_KEY", "")

def add_log(msg):
    """记录日志供 Mac 端拉取"""
    time_str = datetime.now().strftime("%H:%M:%S")
    log_msg = f"[{time_str}] {msg}"
    print(log_msg)
    recent_logs.append(log_msg)
    if len(recent_logs) > 30: # 仅保留最近30条
        recent_logs.pop(0)

def notify_phone(title, content):
    """手机推送"""
    if BARK_KEY:
        try:
            requests.get(f"https://api.day.app/{BARK_KEY}/{title}/{content}", timeout=5)
        except Exception as e:
            add_log(f"推送失败: {e}")

def background_monitor():
    """后台监控线程"""
    while True:
        if monitor_state["is_running"] and monitor_state["cinemas"]:
            try:
                for cid in monitor_state["cinemas"]:
                    url = f"https://m.maoyan.com/ajax/cinemaDetail?cinemaId={cid}"
                    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"}
                    resp = requests.get(url, headers=headers, timeout=10)
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        movies = data.get("showData", {}).get("movies", [])
                        for movie in movies:
                            movie_name = movie.get("nm", "")
                            if monitor_state["movie"] and monitor_state["movie"] not in movie_name:
                                continue
                                
                            for show_date in movie.get("shows", []):
                                date_str = show_date.get("showDate", "")
                                if monitor_state["date"] and monitor_state["date"] != date_str:
                                    continue
                                    
                                for plist in show_date.get("plist", []):
                                    show_id = str(plist.get("showId"))
                                    if show_id and show_id not in monitor_state["seen_shows"]:
                                        monitor_state["seen_shows"].append(show_id)
                                        msg = f"新场次: {movie_name} | {date_str} {plist.get('tm')} | {plist.get('th')}"
                                        add_log(f"🎟️ {msg}")
                                        notify_phone("影院放票提醒", msg)
                add_log("一轮巡检完成，等待下一次...")
            except Exception as e:
                add_log(f"监控异常: {str(e)}")
        
        # 无论是否运行，线程都在后台待命，每 30 秒检查一次
        time.sleep(30)

# 启动后台线程
threading.Thread(target=background_monitor, daemon=True).start()

# --- API 接口供 Mac 端调用 ---

@app.route("/")
def ping():
    return "Monitor Server is alive!"

@app.route("/api/config", methods=["POST"])
def update_config():
    """接收 Mac 端下发的指令"""
    data = request.json
    monitor_state["cinemas"] = data.get("cinemas", [])
    monitor_state["movie"] = data.get("movie", "")
    monitor_state["date"] = data.get("date", "")
    monitor_state["is_running"] = data.get("is_running", False)
    
    status_str = "启动" if monitor_state["is_running"] else "停止"
    add_log(f"Mac 端已下发指令: {status_str}监控。目标影院数量: {len(monitor_state['cinemas'])}")
    
    return jsonify({"status": "success", "state": monitor_state})

@app.route("/api/status", methods=["GET"])
def get_status():
    """Mac 端定时拉取状态和日志"""
    return jsonify({
        "state": monitor_state,
        "logs": recent_logs
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
