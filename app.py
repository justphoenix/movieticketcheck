import os
import requests
import random
from flask import Flask, jsonify
from datetime import datetime

app = Flask(__name__)

# 写死你的目标影院ID（例如 "14389"）和 Bark 密钥
TARGET_CINEMA_ID = "14389" 

logs = []

def add_log(msg):
    now = datetime.now().strftime("%H:%M:%S")
    log_msg = f"[{now}] {msg}"
    print(log_msg)
    logs.append(log_msg)
    if len(logs) > 50:
        logs.pop(0)

@app.route('/')
def index():
    return "Monitor Server is alive!"

# 核心触发路由：只要有人（或UptimeRobot）访问这个网址，就立刻去查一次票！
@app.route('/api/check', methods=['GET'])
def run_check():
    add_log("--- 开始手动触发巡检 ---")
    url = f"https://m.maoyan.com/ajax/cinemaDetail?cinemaId={TARGET_CINEMA_ID}"
    
    user_agents = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"
    ]
    headers = {"User-Agent": random.choice(user_agents)}
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        add_log(f"猫眼响应状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            show_data = data.get("showData")
            if show_data:
                movies = show_data.get("movies", [])
                add_log(f"成功获取到电影排片，共 {len(movies)} 部影片")
                
                # 发送一笔测试推送证明通路完全打通
                bark_key = os.environ.get("BARK_KEY")
                if bark_key:
                    test_url = f"https://api.day.app/{bark_key}/抢票系统打通/云端已成功抓取猫眼数据！"
                    requests.get(test_url, timeout=5)
                    add_log("🔔 已成功发送 Bark 测试推送！")
                else:
                    add_log("⚠️ 环境变量中未找到 BARK_KEY")
            else:
                add_log("⚠️ 猫眼返回成功，但无 showData 数据")
        else:
            add_log(f"❌ 访问猫眼失败，状态码: {resp.status_code}")
            
    except Exception as e:
        add_log(f"🔴 请求发生异常: {str(e)}")
        
    return jsonify({"status": "checked", "logs": logs})

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({"logs": logs})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
