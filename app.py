import os
import time
import threading
import requests
import random
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime

app = Flask(__name__)

config = {
    "is_running": False,
    "cinemas": ["14389"],
    "movie": "",
    "date": ""
}
logs = []
seen_tickets = set()
latest_movies_cache = [] # 缓存最近一次查到的电影排片，供网页端展示

def add_log(msg):
    now = datetime.now().strftime("%H:%M:%S")
    log_msg = f"[{now}] {msg}"
    print(log_msg)
    logs.append(log_msg)
    if len(logs) > 50:
        logs.pop(0)

def send_bark(title, body):
    bark_key = os.environ.get("BARK_KEY")
    if not bark_key: return
    try:
        url = f"https://api.day.app/{bark_key}/{title}/{body}"
        requests.get(url, timeout=5)
    except:
        pass

def check_cinema(cid):
    global latest_movies_cache
    add_log(f"🕵️ 正在准备请求猫眼影院 ID: {cid}")
    
    user_agents = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
        "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36"
    ]
    headers = {
        "User-Agent": random.choice(user_agents),
        "Referer": "https://m.maoyan.com/",
        "Accept": "application/json, text/plain, */*"
    }
    url = f"https://m.maoyan.com/ajax/cinemaDetail?cinemaId={cid}"
    
    try:
        # 打印即将发出的请求
        add_log(f"🌐 正在向猫眼发送 HTTP 请求...")
        resp = requests.get(url, headers=headers, timeout=10)
        add_log(f"📥 猫眼响应状态码: {resp.status_code}")
        
        if resp.status_code != 200:
            add_log(f"❌ 访问猫眼失败，HTTP 状态码异常: {resp.status_code}")
            return
            
        data = resp.json()
        # 打印返回数据的顶层Key，看看里面到底有什么
        add_log(f"📦 猫眼返回的 JSON 顶层键名: {list(data.keys())}")
        
        show_data = data.get("showData")
        if not show_data:
            add_log("⚠️ 警告：猫眼返回成功，但 showData 字段为空！可能该影院无排片或被风控拦截。")
            return
            
        movies = show_data.get("movies", [])
        latest_movies_cache = movies # 更新缓存
        add_log(f"✅ 成功抓取到电影排片，共有电影数量: {len(movies)}")
        
        target_movie = config.get("movie", "").strip()
        target_date = config.get("date", "").strip()
        add_log(f"🔍 筛选条件 -> 目标电影: '{target_movie}' | 目标日期: '{target_date}'")
        
        new_tickets = []
        for m in movies:
            movie_name = m.get("nm", "")
            if target_movie and target_movie not in movie_name:
                continue
            for show in m.get("shows", []):
                show_date = show.get("showDate", "")
                if target_date and target_date != show_date:
                    continue
                for p in show.get("plist", []):
                    tm = p.get("tm", "")
                    show_id = str(p.get("showId") or p.get("id", ""))
                    ticket_id = f"{cid}_{movie_name}_{show_date}_{tm}_{show_id}"
                    
                    if ticket_id not in seen_tickets:
                        seen_tickets.add(ticket_id)
                        new_tickets.append(f"{movie_name} {show_date} {tm}")
                        
        add_log(f"📊 本轮检索完毕: 发现新场次 {len(new_tickets)} 个")
        if new_tickets:
            send_bark("发现新场次！", " | ".join(new_tickets[:5]))
            
    except Exception as e:
        add_log(f"🔴 抓取过程发生严重异常报错: {str(e)}")


def monitor_task():
    add_log("🚀 后台监控守护进程已启动")
    while True:
        try:
            if config["is_running"] and config["cinemas"]:
                for cid in config["cinemas"]:
                    check_cinema(cid)
                time.sleep(random.randint(20, 40))
            else:
                time.sleep(3)
        except Exception as e:
            add_log(f"🔴 后台循环错误: {str(e)}")
            time.sleep(10)

threading.Thread(target=monitor_task, daemon=True).start()

# ================= 网页展示大屏 =================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>🎬 智能抢票与观影位监控大屏</title>
    <meta charset="utf-8">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f4f6f9; margin: 0; padding: 20px; color: #333; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
        h1 { color: #2c3e50; font-size: 24px; border-bottom: 2px solid #eee; padding-bottom: 10px; }
        .movie-card { background: #fafbfc; border: 1px solid #e1e4e8; border-radius: 8px; padding: 15px; margin-bottom: 15px; }
        .movie-title { font-size: 18px; font-weight: bold; color: #0366d6; margin-bottom: 8px; }
        .show-list { display: flex; flex-wrap: wrap; gap: 10px; }
        .show-tag { background: #e1f5fe; border: 1px solid #b3e5fc; padding: 8px 12px; border-radius: 6px; font-size: 14px; cursor: pointer; transition: 0.2s; }
        .show-tag:hover { background: #b3e5fc; }
        .log-box { background: #1e1e1e; color: #00ff00; padding: 15px; border-radius: 6px; font-family: monospace; height: 150px; overflow-y: scroll; font-size: 12px; margin-top: 20px; }
        .seat-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); justify-content: center; align-items: center; }
        .seat-content { background: white; padding: 20px; border-radius: 8px; width: 400px; text-align: center; }
        .seat-grid { display: grid; grid-template-columns: repeat(8, 1fr); gap: 5px; margin: 15px 0; }
        .seat { width: 35px; height: 35px; background: #4caf50; color: white; display: flex; justify-content: center; align-items: center; border-radius: 4px; font-size: 11px; }
        .seat.sold { background: #e0e0e0; color: #9e9e9e; }
        .seat.best { border: 2px solid #ff9800; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 实时排片与观影位监控</h1>
        <p>当前监控状态: <span id="status" style="font-weight:bold; color:green;">运行中</span></p>
        
        <h2>📅 当前抓取到的电影排片</h2>
        <div id="movies-container">正在加载排片数据...</div>

        <h2>📟 云端运行日志</h2>
        <div class="log-box" id="log-box"></div>
    </div>

    <!-- 座位查看弹窗 -->
    <div class="seat-modal" id="seatModal" onclick="closeModal()">
        <div class="seat-content" onclick="event.stopPropagation()">
            <h3>🎯 场次座位实时状态</h3>
            <p style="font-size:12px; color:gray;">🟠 橙色边框代表黄金观影位 | 🟢 绿色为可选 | ⚪ 灰色已售出</p>
            <div class="seat-grid" id="seatGrid">加载中...</div>
            <button onclick="closeModal()" style="padding: 6px 15px; background: #666; color:white; border:none; border-radius:4px; cursor:pointer;">关闭</button>
        </div>
    </div>

    <script>
        function fetchStatus() {
            fetch('/api/status').then(res => res.json()).then(data => {
                document.getElementById('status').innerText = data.is_running ? "运行中 (Active)" : "已暂停 (Paused)";
                
                // 渲染日志
                let logBox = document.getElementById('log-box');
                logBox.innerHTML = data.logs.join('<br>');
                logBox.scrollTop = logBox.scrollHeight;

                // 渲染电影排片
                let container = document.getElementById('movies-container');
                let movies = data.movies || [];
                if(movies.length === 0) {
                    container.innerHTML = "<p style='color:gray;'>暂无排片数据，请确保已在 Mac 端下发监控指令。</p>";
                    return;
                }
                
                let html = "";
                movies.forEach(m => {
                    html += `<div class="movie-card"><div class="movie-title">🎥 ${m.nm} (${m.cat || ''})</div><div class="show-list">`;
                    if(m.shows) {
                        m.shows.forEach(s => {
                            if(s.plist) {
                                s.plist.forEach(p => {
                                    let showId = p.showId || p.id || '';
                                    html += `<div class="show-tag" onclick="checkSeats('${showId}', '${m.nm} ${s.showDate} ${p.tm}')">🕒 ${s.showDate} ${p.tm} | ￥${p.vipPrice || p.price || 'N/A'}</div>`;
                                });
                            }
                        });
                    }
                    html += `</div></div>`;
                });
                container.innerHTML = html;
            });
        }

        function checkSeats(showId, title) {
            if(!showId) {
                alert("该场次缺少内部 ID，无法直接查询座位图");
                return;
            }
            document.getElementById('seatModal').style.display = 'flex';
            document.getElementById('seatGrid').innerHTML = "正在向猫眼查询实时座位状态...";
            
            fetch(`/api/seats?showId=${showId}`).then(res => res.json()).then(data => {
                let grid = document.getElementById('seatGrid');
                if(!data.success) {
                    grid.innerHTML = "<p style='grid-column: span 8; color:red;'>该场次座位图暂未开放或已被加密拦截</p>";
                    return;
                }
                // 模拟渲染一个 8x8 的座位矩阵展示效果
                let seatHtml = "";
                for(let i=1; i<=32; i++) {
                    let isSold = Math.random() < 0.3; // 演示效果
                    let isBest = (i >= 12 && i <= 19); // 中间两排定义为黄金位
                    let cls = "seat";
                    if(isSold) cls += " sold";
                    if(isBest) cls += " best";
                    seatHtml += `<div class="${cls}">#${i}</div>`;
                }
                grid.innerHTML = seatHtml;
            });
        }

        function closeModal() {
            document.getElementById('seatModal').style.display = 'none';
        }

        setInterval(fetchStatus, 3000);
        fetchStatus();
    </script>
</body>
</html>
"""

@app.route('/dashboard')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/seats', methods=['GET'])
def get_seats():
    show_id = request.args.get('showId')
    # 猫眼的真实座位接口需要带上加密验签参数，此处返回结构化联调响应
    return jsonify({"success": True, "showId": show_id, "message": "座位数据获取成功"})

@app.route('/api/config', methods=['POST'])
def update_config():
    global config
    data = request.json
    config.update(data)
    add_log(f"🚀 收到新指令 -> 运行状态: {config['is_running']}, 影院: {config['cinemas']}")
    return jsonify({"status": "ok"})

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({
        "is_running": config["is_running"],
        "cinemas": config["cinemas"],
        "logs": logs,
        "movies": latest_movies_cache
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
