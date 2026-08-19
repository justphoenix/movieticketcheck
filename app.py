import os
import requests
import random
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime

app = Flask(__name__)

# 全局配置中心
config = {
    "is_running": False,
    "cinemas": ["38279"], # 默认影院 ID
    "movie": "",
    "date": ""
}
logs = []
seen_tickets = set()
latest_movies_cache = []

def add_log(msg):
    now = datetime.now().strftime("%H:%M:%S")
    log_msg = f"[{now}] {msg}"
    print(log_msg)
    logs.append(log_msg)
    if len(logs) > 60:
        logs.pop(0)

def send_bark(title, body):
    bark_key = os.environ.get("BARK_KEY")
    if not bark_key:
        add_log("⚠️ 未配置 BARK_KEY，跳过手机推送")
        return
    try:
        url = f"https://api.day.app/{bark_key}/{title}/{body}"
        requests.get(url, timeout=5)
        add_log(f"🔔 Bark 推送成功: {title}")
    except Exception as e:
        add_log(f"❌ Bark 推送异常: {str(e)}")

def run_check_logic():
    """核心查票逻辑：高强度伪装与全日志曝光"""
    global latest_movies_cache
    cinemas = config.get("cinemas", ["38279"])
    
    for cid in cinemas:
        add_log(f"🕵️ 开始向猫眼发起请求，目标影院 ID: {cid}")
        
        # 🛡️ 强化版移动端请求头，对抗机房风控
        user_agents = [
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36"
        ]
        headers = {
            "User-Agent": random.choice(user_agents),
            "Referer": "https://m.maoyan.com/app",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "X-Requested-With": "XMLHttpRequest"
        }
        url = f"https://m.maoyan.com/ajax/cinemaDetail?cinemaId={cid}"
        
        try:
            add_log(f"🌐 正在发送 HTTP GET 请求...")
            resp = requests.get(url, headers=headers, timeout=12)
            add_log(f"📥 猫眼响应状态码: {resp.status_code}")
            
            # 🔍 无论成败，把响应前 200 个字符打印出来暴露真相
            preview_text = resp.text[:200].replace('\n', ' ')
            add_log(f"📄 响应内容预览: {preview_text}")
            
            if resp.status_code != 200:
                add_log(f"❌ 请求失败，状态码异常: {resp.status_code}")
                continue
                
            # 尝试解析 JSON
            try:
                data = resp.json()
            except Exception as json_err:
                add_log(f"🔴 致命错误：猫眼返回的不是 JSON 数据（可能被防火墙拦截）: {str(json_err)}")
                continue
                
            add_log(f"📦 猫眼 JSON 顶层键名: {list(data.keys())}")
            
            show_data = data.get("showData")
            if not show_data:
                add_log(f"⚠️ 猫眼返回成功，但 showData 为空。完整数据片段: {str(data)[:150]}")
                continue
                
            movies = show_data.get("movies", [])
            latest_movies_cache = movies
            add_log(f"✅ 成功解析排片，获取到电影总数: {len(movies)}")
            
            target_movie = config.get("movie", "").strip()
            target_date = config.get("date", "").strip()
            add_log(f"🔍 过滤条件 -> 电影: '{target_movie}' | 日期: '{target_date}'")
            
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
                            
            if new_tickets:
                send_bark("发现新场次！", " | ".join(new_tickets[:5]))
                add_log(f"🔔 发现新场次，已成功触发推送: {len(new_tickets)} 个")
            else:
                add_log("💤 本轮检索完毕：暂无符合条件的新场次")
                
        except Exception as e:
            add_log(f"🔴 请求发生严重网络异常: {str(e)}")

# ================= 网页可视化大屏模板 =================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>🎬 智能抢票与观影位监控大屏</title>
    <meta charset="utf-8">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f4f6f9; margin: 0; padding: 20px; color: #333; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
        h1 { color: #2c3e50; font-size: 24px; border-bottom: 2px solid #eee; padding-bottom: 10px; }
        .movie-card { background: #fafbfc; border: 1px solid #e1e4e8; border-radius: 8px; padding: 15px; margin-bottom: 15px; }
        .movie-title { font-size: 18px; font-weight: bold; color: #0366d6; margin-bottom: 8px; }
        .show-list { display: flex; flex-wrap: wrap; gap: 10px; }
        .show-tag { background: #e1f5fe; border: 1px solid #b3e5fc; padding: 8px 12px; border-radius: 6px; font-size: 14px; }
        .log-box { background: #1e1e1e; color: #00ff00; padding: 15px; border-radius: 6px; font-family: monospace; height: 200px; overflow-y: scroll; font-size: 12px; margin-top: 20px; }
        .btn-refresh { background: #28a745; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-size: 14px; margin-bottom: 15px; font-weight: bold; }
        .btn-refresh:hover { background: #218838; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 实时排片与观影位监控大屏</h1>
        <button class="btn-refresh" onclick="triggerCheck()">🔄 手动立即触发一次抓取</button>
        <p>当前监控状态: <span id="status" style="font-weight:bold; color:green;">就绪</span></p>
        <h2>📅 当前缓存的电影排片</h2>
        <div id="movies-container">正在加载排片数据...</div>
        <h2>📟 云端实时运行日志（核心排查区）</h2>
        <div class="log-box" id="log-box"></div>
    </div>
    <script>
        function triggerCheck() {
            document.getElementById('log-box.innerHTML') += "<br>[Client] 正在发送手动触发指令...";
            fetch('/api/trigger').then(res => res.json()).then(data => {
                fetchStatus();
            });
        }
        function fetchStatus() {
            fetch('/api/status').then(res => res.json()).then(data => {
                let logBox = document.getElementById('log-box');
                logBox.innerHTML = (data.logs || []).join('<br>');
                logBox.scrollTop = logBox.scrollHeight;
                
                let container = document.getElementById('movies-container');
                let movies = data.movies || [];
                if(movies.length === 0) {
                    container.innerHTML = "<p style='color:gray;'>暂无排片缓存。请点击上方绿色按钮手动触发一次，然后观察下方日志！</p>";
                    return;
                }
                let html = "";
                movies.forEach(m => {
                    html += `<div class="movie-card"><div class="movie-title">🎥 ${m.nm}</div><div class="show-list">`;
                    if(m.shows) {
                        m.shows.forEach(s => {
                            if(s.plist) {
                                s.plist.forEach(p => {
                                    html += `<div class="show-tag">🕒 ${s.showDate} ${p.tm} | ￥${p.vipPrice || p.price || 'N/A'}</div>`;
                                });
                            }
                        });
                    }
                    html += `</div></div>`;
                });
                container.innerHTML = html;
            });
        }
        setInterval(fetchStatus, 4000);
        fetchStatus();
    </script>
</body>
</html>
"""

@app.route('/dashboard')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/trigger', methods=['GET', 'POST'])
def api_trigger():
    run_check_logic()
    return jsonify({"status": "checked"})

@app.route('/api/config', methods=['POST'])
def update_config():
    global config
    data = request.json
    config.update(data)
    add_log(f"🚀 收到 Mac 端指令 -> 运行状态: {config['is_running']}, 影院列表: {config['cinemas']}")
    # 只要 Mac 端下发了启动指令，立刻在主进程同步触发一次抓取！
    if config.get("is_running"):
        run_check_logic()
    return jsonify({"status": "ok"})

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({
        "is_running": config["is_running"],
        "cinemas": config["cinemas"],
        "logs": logs,
        "movies": latest_movies_cache
    })

@app.route('/')
def index():
    return "🎬 影院监控服务运行中！请访问 /dashboard 查看可视化大屏。"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
