import os
import time
import threading
import requests
import random
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# 全局变量与记忆库
config = {
    "is_running": False,
    "cinemas": [],
    "movie": "",
    "date": ""
}
logs = []
seen_tickets = set() # 用来记录“已经见过的票”

def add_log(msg):
    """记录日志并保留最近50条，供Mac端拉取"""
    now = datetime.now().strftime("%H:%M:%S")
    log_msg = f"[{now}] {msg}"
    print(log_msg)
    logs.append(log_msg)
    if len(logs) > 50:
        logs.pop(0)

def send_bark(title, body):
    """发送 Bark 推送"""
    bark_key = os.environ.get("BARK_KEY")
    if not bark_key:
        add_log("⚠️ 环境变量 BARK_KEY 未配置，无法发送推送！")
        return
    
    try:
        url = f"https://api.day.app/{bark_key}/{title}/{body}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            add_log(f"🔔 推送成功: {title}")
        else:
            add_log(f"⚠️ Bark推送失败，状态码: {resp.status_code}")
    except Exception as e:
        add_log(f"❌ 发送推送时出错: {str(e)}")

def check_cinema(cid):
    """请求猫眼接口并对比数据"""
    # 随机设备指纹库，每次请求伪装成不同手机/电脑
    user_agents = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15",
        "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 12; Pixel 6 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15"
    ]
    
    headers = {
        "User-Agent": random.choice(user_agents),
        "Accept": "application/json"
    }
    url = f"https://m.maoyan.com/ajax/cinemaDetail?cinemaId={cid}"
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
    except Exception as e:
        add_log(f"❌ 网络请求异常: {str(e)}")
        return

    if resp.status_code != 200:
        add_log(f"❌ 访问猫眼失败 (HTTP {resp.status_code})，可能IP被拦截")
        return
        
    try:
        data = resp.json()
    except Exception as e:
        add_log(f"❌ 解析猫眼数据失败: {str(e)}")
        return
        
    show_data = data.get("showData")
    if not show_data:
        add_log("⚠️ 猫眼返回成功，但没有排片数据(showData)，可能无票或被风控。")
        return

    movies = show_data.get("movies", [])
    target_movie = config.get("movie", "").strip()
    target_date = config.get("date", "").strip()
    
    found_count = 0
    new_tickets = [] # 专门记录本次巡检发现的【新票】
    
    for m in movies:
        movie_name = m.get("nm", "")
        if target_movie and target_movie not in movie_name:
            continue
            
        for show in m.get("shows", []):
            show_date = show.get("showDate", "")
            if target_date and target_date != show_date:
                continue
                
            for p in show.get("plist", []):
                found_count += 1
                tm = p.get("tm", "")
                ticket_id = f"{cid}_{movie_name}_{show_date}_{tm}"
                
                # 如果这张票不在记忆库里，说明是新票
                if ticket_id not in seen_tickets:
                    seen_tickets.add(ticket_id)
                    new_tickets.append(f"{movie_name} {show_date} {tm}")
                    
    add_log(f"✅ 影院 {cid} 巡检完毕: 满足条件 {found_count} 场，其中新场 {len(new_tickets)} 个")
    
    # 智能合并推送，防止首次运行消息轰炸
    if new_tickets:
        if len(new_tickets) > 5:
            send_bark("发现大量场次！", f"共检索到 {len(new_tickets)} 个新场次，请直接打开APP查看。")
        else:
            msg_body = " | ".join(new_tickets)
            send_bark("发现新场次！", msg_body)

def monitor_task():
    """后台死循环巡检"""
    add_log("云端监控线程已启动，等待 Mac 端下发指令...")
    while True:
        try:
            if config["is_running"] and config["cinemas"]:
                for cid in config["cinemas"]:
                    check_cinema(cid)
                # 随机休眠 20 到 40 秒
                wait_time = random.randint(20, 40)
                add_log(f"--- 巡检结束，模拟人类随机休眠 {wait_time} 秒 ---")
                time.sleep(wait_time)
            else:
                # 如果未启动监控，每5秒检查一次指令状态即可
                time.sleep(5)
        except Exception as e:
            add_log(f"🔴 监控主线程发生严重崩溃: {str(e)}")
            time.sleep(30)

# 启动后台线程
threading.Thread(target=monitor_task, daemon=True).start()

@app.route('/')
def index():
    return "Monitor Server is alive!"

@app.route('/api/config', methods=['POST'])
def update_config():
    global config
    data = request.json
    config.update(data)
    add_log(f"🚀 接收到新指令: 监控状态={'启动' if config['is_running'] else '停止'}")
    return jsonify({"status": "ok"})

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({
        "is_running": config["is_running"],
        "logs": logs
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
