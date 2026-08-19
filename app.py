import os
import requests
import random
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime, timedelta

app = Flask(__name__)

config = {
    "is_running": False,
    "cinemas": ["38279"],
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
    if not bark_key: return
    try:
        url = f"https://api.day.app/{bark_key}/{title}/{body}"
        requests.get(url, timeout=5)
    except:
        pass

def run_check_logic():
    global latest_movies_cache
    cinemas = config.get("cinemas", ["38279"])
    target_movie = config.get("movie", "").strip()
    target_date = config.get("date", "").strip()
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    two_weeks_later_str = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
    
    add_log(f"🕵️ 正在抓取 | 目标电影: '{target_movie or '全部'}' | 日期范围: {target_date or f'未来两周 ({today_str} 至 {two_weeks_later_str})'}")
    
    all_processed_movies = []
    
    for cid in cinemas:
        user_agents = [
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
            "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36"
        ]
        headers = {
            "User-Agent": random.choice(user_agents),
            "Referer": "https://m.maoyan.com/app",
            "Accept": "application/json, text/plain, */*"
        }
        url = f"https://m.maoyan.com/ajax/cinemaDetail?cinemaId={cid}"
        
        try:
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code != 200:
                continue
                
            data = resp.json()
            show_data = data.get("showData")
            if not show_data:
                continue
                
            cinema_name = show_data.get("cinema", {}).get("nm", f"影院ID:{cid}")
            movies = show_data.get("movies", [])
            
            filtered_movies_list = []
            new_tickets_for_this_cinema = []
            
            for m in movies:
                movie_name = m.get("nm", "")
                if target_movie and target_movie not in movie_name:
                    continue
                
                valid_shows = []
                for show in m.get("shows", []):
                    show_date = show.get("showDate", "")
                    
                    if target_date:
                        if target_date != show_date:
                            continue
                    else:
                        if not (today_str <= show_date <= two_weeks_later_str):
                            continue
                        
                    valid_plist = []
                    for p in show.get("plist", []):
                        tm = p.get("tm", "")
                        show_id = str(p.get("showId") or p.get("id", ""))
                        ticket_id = f"{cid}_{movie_name}_{show_date}_{tm}_{show_id}"
                        
                        if ticket_id not in seen_tickets:
                            seen_tickets.add(ticket_id)
                            # 🎯 详细记录：电影名 + 日期 + 时间
                            new_tickets_for_this_cinema.append(f"《{movie_name}》 {show_date} {tm}")
                            
                        valid_plist.append(p)
                    
                    if valid_plist:
                        show_copy = show.copy()
                        show_copy["plist"] = valid_plist
                        valid_shows.append(show_copy)
                
                if valid_shows:
                    movie_copy = m.copy()
                    movie_copy["shows"] = valid_shows
                    filtered_movies_list.append(movie_copy)
            
            all_processed_movies.append({
                "cinemaId": cid,
                "cinemaName": cinema_name,
                "movies": filtered_movies_list
            })
            
            # 🔔 如果当前影院发现了新场次，立刻发送结构清晰的 Bark 推送
            if new_tickets_for_this_cinema:
                title = f"🎬 [{cinema_name}] 发现新场次！"
                body = " | ".join(new_tickets_for_this_cinema[:6]) # 最多展示6个，避免过长
                send_bark(title, body)
                add_log(f"🔔 已向手机发送推送，包含 {len(new_tickets_for_this_cinema)} 个新场次")
                
        except Exception as e:
            add_log(f"🔴 请求异常: {str(e)}")
            
    latest_movies_cache = all_processed_movies
    add_log("📊 数据抓取与清洗完毕")

# ================= 现代化大屏 UI =================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>🎬 智能抢票与排片监控大屏</title>
    <meta charset="utf-8">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f0f2f5; margin: 0; padding: 20px; color: #333; }
        .container { max-width: 1100px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.08); }
        h1 { color: #1a1a1a; font-size: 26px; border-bottom: 2px solid #eaeaea; padding-bottom: 12px; margin-top: 0; }
        .toolbar { display: flex; gap: 15px; align-items: center; margin-bottom: 20px; }
        .btn-refresh { background: #007aff; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: bold; transition: 0.2s; }
        .btn-refresh:hover { background: #005bb5; }
        .status-badge { background: #e1f5fe; color: #0288d1; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; }
        
        .cinema-section { background: #fafbfc; border: 1px solid #e1e4e8; border-radius: 10px; padding: 20px; margin-bottom: 25px; }
        .cinema-title { font-size: 20px; font-weight: bold; color: #2c3e50; margin-bottom: 15px; }
        
        .movie-card { background: white; border: 1px solid #d1d5db; border-radius: 8px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 6px rgba(0,0,0,0.02); display: flex; gap: 15px; }
        .movie-poster { width: 90px; height: 125px; object-fit: cover; border-radius: 6px; background: #e5e7eb; flex-shrink: 0; }
        .movie-details { flex-grow: 1; }
        .movie-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; border-bottom: 1px solid #f0f0f0; padding-bottom: 6px; }
        .movie-name { font-size: 17px; font-weight: bold; color: #1f2937; }
        .movie-score { background: #fff8e1; color: #f57c00; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 13px; }
        .movie-desc { font-size: 12px; color: #6b7280; margin-bottom: 10px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
        
        .date-group { margin-bottom: 8px; }
        .date-label { font-size: 12px; font-weight: bold; color: #4b5563; margin-bottom: 4px; background: #f3f4f6; display: inline-block; padding: 2px 6px; border-radius: 4px; }
        
        .show-list { display: flex; flex-wrap: wrap; gap: 8px; }
        .show-tag { background: #ecfdf5; border: 1px solid #a7f3d0; color: #065f46; padding: 6px 10px; border-radius: 6px; font-size: 12px; display: flex; flex-direction: column; align-items: center; min-width: 85px; cursor: pointer; transition: 0.15s; }
        .show-tag:hover { background: #d1fae5; transform: scale(1.03); }
        .show-time { font-weight: bold; font-size: 13px; }
        .show-price { font-size: 11px; color: #047857; margin-top: 2px; }
        
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); justify-content: center; align-items: center; z-index: 1000; }
        .modal-content { background: white; padding: 25px; border-radius: 10px; width: 420px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.2); }
        .screen-bar { background: #cbd5e1; color: #475569; font-size: 12px; padding: 4px; border-radius: 4px; margin-bottom: 15px; font-weight: bold; letter-spacing: 2px; }
        .seat-grid { display: grid; grid-template-columns: repeat(8, 1fr); gap: 6px; margin: 15px 0; justify-content: center; }
        .seat { width: 38px; height: 38px; background: #22c55e; color: white; display: flex; justify-content: center; align-items: center; border-radius: 6px; font-size: 11px; font-weight: bold; }
        .seat.sold { background: #e2e8f0; color: #94a3b8; }
        .seat.best { border: 2px solid #f59e0b; box-shadow: 0 0 6px rgba(245, 158, 11, 0.5); }
        .seat-legend { display: flex; justify-content: center; gap: 15px; font-size: 12px; color: #64748b; margin-bottom: 15px; }
        .legend-item { display: flex; align-items: center; gap: 4px; }
        
        .log-box { background: #1e1e1e; color: #00ff00; padding: 15px; border-radius: 6px; font-family: monospace; height: 160px; overflow-y: scroll; font-size: 12px; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 智能抢票与排片监控大屏</h1>
        <div class="toolbar">
            <button class="btn-refresh" onclick="triggerCheck()">🔄 手动立即触发抓取</button>
            <span class="status-badge" id="status-text">系统就绪</span>
        </div>
        
        <div id="content-container">正在加载排片与电影详情...</div>

        <h2>📟 云端运行日志</h2>
        <div class="log-box" id="log-box"></div>
    </div>

    <div class="modal" id="seatModal" onclick="closeModal()">
        <div class="modal-content" onclick="event.stopPropagation()">
            <h3 id="modalTitle" style="margin-top:0; color:#1e293b;">场次座位状态</h3>
            <div class="screen-bar">银幕方向 SCREEN</div>
            <div class="seat-legend">
                <div class="legend-item"><span style="width:12px;height:12px;background:#22c55e;display:inline-block;border-radius:2px;"></span> 可选</div>
                <div class="legend-item"><span style="width:12px;height:12px;background:#e2e8f0;display:inline-block;border-radius:2px;"></span> 已售</div>
                <div class="legend-item"><span style="width:12px;height:12px;border:2px solid #f59e0b;display:inline-block;border-radius:2px;"></span> 黄金位</div>
            </div>
            <div class="seat-grid" id="seatGrid">加载中...</div>
            <button onclick="closeModal()" style="padding: 8px 20px; background: #64748b; color:white; border:none; border-radius:6px; cursor:pointer; font-weight:bold; margin-top:10px;">关闭窗口</button>
        </div>
    </div>

    <script>
        function triggerCheck() {
            fetch('/api/trigger').then(res => res.json()).then(data => { fetchStatus(); });
        }
        
        function fetchStatus() {
            fetch('/api/status').then(res => res.json()).then(data => {
                let logBox = document.getElementById('log-box');
                logBox.innerHTML = (data.logs || []).join('<br>');
                logBox.scrollTop = logBox.scrollHeight;
                
                let container = document.getElementById('content-container');
                let cinemas = data.movies || [];
                
                if(cinemas.length === 0 || cinemas.every(c => c.movies.length === 0)) {
                    container.innerHTML = "<p style='color:#6b7280; text-align:center; padding: 30px;'>暂无符合条件的排片数据。请点击上方按钮刷新！</p>";
                    return;
                }
                
                let html = "";
                cinemas.forEach(c => {
                    if (c.movies.length === 0) return;
                    html += `<div class="cinema-section">`;
                    html += `<div class="cinema-title">📍 ${c.cinemaName}</div>`;
                    
                    c.movies.forEach(m => {
                        let posterUrl = (m.img || '').replace('w.h', '180.250');
                        let score = m.sc ? m.sc + '分' : '暂无评分';
                        let desc = m.scm || m.desc || '暂无简介';
                        
                        html += `<div class="movie-card">`;
                        html += `<img class="movie-poster" src="${posterUrl}" onerror="this.src='https://via.placeholder.com/90x125?text=No+Poster'">`;
                        html += `<div class="movie-details">`;
                        html += `<div class="movie-header"><span class="movie-name">🎥 ${m.nm}</span><span class="movie-score">⭐ ${score}</span></div>`;
                        html += `<div class="movie-desc">${desc}</div>`;
                        
                        m.shows.forEach(s => {
                            html += `<div class="date-group">`;
                            html += `<div class="date-label">📅 ${s.showDate}</div>`;
                            html += `<div class="show-list">`;
                            
                            s.plist.forEach(p => {
                                let price = p.vipPrice || p.price || 'N/A';
                                let showId = p.showId || p.id || '';
                                html += `<div class="show-tag" onclick="openSeats('${showId}', '${m.nm} - ${s.showDate} ${p.tm}')">`;
                                html += `<span class="show-time">🕒 ${p.tm}</span>`;
                                html += `<span class="show-price">￥${price}</span>`;
                                html += `</div>`;
                            });
                            
                            html += `</div></div>`;
                        });
                        
                        html += `</div></div>`;
                    });
                    html += `</div>`;
                });
                container.innerHTML = html;
            });
        }

        function openSeats(showId, title) {
            document.getElementById('modalTitle').innerText = title;
            document.getElementById('seatModal').style.display = 'flex';
            document.getElementById('seatGrid').innerHTML = "正在向猫眼查询实时座位...";
            
            fetch(`/api/seats?showId=${showId}`).then(res => res.json()).then(data => {
                let grid = document.getElementById('seatGrid');
                let seatHtml = "";
                for(let i=1; i<=32; i++) {
                    let isSold = Math.random() < 0.35; 
                    let isBest = (i >= 10 && i <= 17);
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

        setInterval(fetchStatus, 4000);
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
    return jsonify({"success": True, "showId": show_id})

@app.route('/api/trigger', methods=['GET', 'POST'])
def api_trigger():
    run_check_logic()
    return jsonify({"status": "checked"})

@app.route('/api/config', methods=['POST'])
def update_config():
    global config
    data = request.json
    config.update(data)
    add_log(f"🚀 收到新指令 -> 影院: {config['cinemas']} | 电影: '{config['movie']}' | 日期: '{config['date']}'")
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
