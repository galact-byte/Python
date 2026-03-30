"""
项目进度爬虫 - Web GUI
在浏览器中操作爬虫：选择项目类型、配置参数、启动爬取、下载 Excel
使用方法: python gui.py
"""

import http.server
import json
import os
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# 确保能导入同目录的 scraper 模块
sys.path.insert(0, str(Path(__file__).parent))

from scraper import (
    PROJECT_TYPES, CONFIG,
    load_config, save_config,
    create_session, check_session, auto_login,
    fetch_all, export_excel,
)

PORT = 5050
OUTPUT_DIR = Path(__file__).parent / "output"

# ============ 爬取状态（线程共享） ============
scrape_state = {
    "running": False,
    "logs": [],
    "result": None,
    "error": None,
}


def _run_scrape(types_to_scrape):
    """在后台线程中执行爬取"""
    state = scrape_state
    state["running"] = True
    state["logs"] = []
    state["result"] = None
    state["error"] = None

    def log(msg):
        state["logs"].append(msg)

    total_count = 0
    session = None
    cert_path = key_path = None

    try:
        load_config()
        log("[..] 初始化连接...")

        cookie = CONFIG.get("cookie", "")
        session, cert_path, key_path = create_session(
            CONFIG["pfx_path"], CONFIG["pfx_password"], cookie or None
        )

        # 鉴权（只需登录一次）
        # 用等保路径检查 session（PHPSESSID 是全局的，与具体模块无关）
        if cookie:
            log("[..] 检查已有 Session...")
            if check_session(session, CONFIG["base_url"]):
                log("[OK] Session 有效")
            else:
                log("[!] Session 已过期，尝试自动登录...")
                cookie = None

        if not cookie:
            log("[..] 自动登录中...")
            success = auto_login(
                session, CONFIG["base_url"],
                CONFIG["username"], CONFIG["password"],
            )
            if not success:
                raise RuntimeError("自动登录失败，请检查配置或手动更新 Cookie")
            log("[OK] 登录成功")

        # 逐个类型爬取
        for type_key in types_to_scrape:
            type_info = PROJECT_TYPES[type_key]
            type_name = type_info["name"]
            api_path = type_info["path"]

            log(f"\n[..] 开始爬取: {type_name}")
            try:
                rows = fetch_all(session, CONFIG["base_url"], api_path, CONFIG["page_size"])
                log(f"[OK] 获取 {len(rows)} 条记录")

                log("[..] 导出 Excel...")
                output_dir = str(OUTPUT_DIR)
                filepath = export_excel(rows, output_dir, type_name)
                log(f"[OK] 已导出: {os.path.basename(filepath)}")
                total_count += len(rows)
            except Exception as e:
                log(f"[X] {type_name} 失败: {e}")

        log(f"\n{'='*40}")
        log(f"[OK] 全部完成，共 {total_count} 条记录")
        state["result"] = {"count": total_count}

    except Exception as e:
        log(f"[X] 错误: {e}")
        state["error"] = str(e)
    finally:
        if cert_path or key_path:
            for f in (cert_path, key_path):
                if f:
                    try:
                        os.unlink(f)
                    except OSError:
                        pass
        state["running"] = False


# ============ HTML 页面 ============
HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>项目进度爬虫</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Microsoft YaHei',-apple-system,sans-serif;background:#0f0f0f;color:#e5e5e5;min-height:100vh;padding:2rem}
.container{max-width:820px;margin:0 auto}
h1{font-size:1.4rem;margin-bottom:1.5rem;display:flex;align-items:center;gap:.5rem}
h1 span{color:#00d4aa}
.card{background:#1a1a1a;border:1px solid #272727;border-radius:10px;padding:1.25rem;margin-bottom:1rem}
.card-title{font-size:.8rem;color:#666;text-transform:uppercase;letter-spacing:.08em;margin-bottom:1rem;font-weight:600}
.form-row{display:flex;gap:.75rem;margin-bottom:.6rem;align-items:center}
.form-row label{min-width:90px;font-size:.82rem;color:#999}
input,select{flex:1;padding:.45rem .7rem;background:#111;border:1px solid #333;border-radius:6px;color:#e5e5e5;font-size:.82rem;outline:none;font-family:inherit}
input:focus,select:focus{border-color:#00d4aa}
select option{background:#1a1a1a}
.btn{padding:.55rem 1.4rem;border:none;border-radius:6px;font-size:.85rem;font-weight:500;cursor:pointer;transition:all .15s}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn-primary{background:#00d4aa;color:#0a0a0a}
.btn-primary:hover:not(:disabled){background:#00e6b8}
.btn-secondary{background:#2a2a2a;color:#ccc}
.btn-secondary:hover:not(:disabled){background:#333}
.btn-sm{padding:.35rem .8rem;font-size:.78rem}
.actions{display:flex;gap:.5rem;margin-top:.75rem}
#log{background:#0d0d0d;border:1px solid #222;border-radius:8px;padding:.85rem 1rem;font-family:'JetBrains Mono','Consolas',monospace;font-size:.78rem;line-height:1.7;max-height:320px;overflow-y:auto;white-space:pre-wrap;color:#777;min-height:80px}
.l-ok{color:#00d4aa}.l-err{color:#ff6b9d}.l-warn{color:#f59e0b}.l-info{color:#555}
.files-list{display:flex;flex-direction:column;gap:.4rem}
.file-item{display:flex;align-items:center;justify-content:space-between;padding:.5rem .75rem;background:#111;border-radius:6px}
.file-item a{color:#00d4aa;text-decoration:none;font-size:.82rem}
.file-item a:hover{text-decoration:underline}
.file-time{font-size:.72rem;color:#555}
.empty{color:#444;font-size:.82rem;padding:.3rem 0}
.type-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:.4rem;margin-bottom:.75rem}
.type-chip{padding:.4rem .6rem;background:#111;border:1px solid #333;border-radius:6px;font-size:.78rem;cursor:pointer;text-align:center;transition:all .15s;user-select:none}
.type-chip:hover{border-color:#555}
.type-chip.selected{border-color:#00d4aa;background:rgba(0,212,170,.08);color:#00d4aa}
</style>
</head>
<body>
<div class="container">
  <h1><span>&#9670;</span> 项目进度爬虫</h1>

  <div class="card">
    <div class="card-title">选择爬取类型（点击选择，可多选）</div>
    <div class="type-grid" id="typeGrid"></div>
    <div class="actions">
      <button class="btn btn-primary" id="btnScrape" onclick="startScrape()">开始爬取</button>
      <button class="btn btn-secondary" onclick="selectAll()">全选</button>
      <button class="btn btn-secondary" onclick="selectNone()">清空</button>
    </div>
  </div>

  <div class="card">
    <div class="card-title">运行日志</div>
    <div id="log"><span class="l-info">等待操作...</span></div>
  </div>

  <div class="card">
    <div class="card-title">已导出文件</div>
    <div id="files" class="files-list"><p class="empty">暂无文件</p></div>
  </div>

  <div class="card">
    <div class="card-title">连接配置</div>
    <div class="form-row"><label>服务器地址</label><input id="cfgUrl"></div>
    <div class="form-row"><label>证书路径</label><input id="cfgPfx"></div>
    <div class="form-row"><label>用户名</label><input id="cfgUser"></div>
    <div class="form-row"><label>密码</label><input id="cfgPass" type="password"></div>
    <div class="form-row"><label>Cookie</label><input id="cfgCookie" placeholder="PHPSESSID（留空则自动登录）"></div>
    <div class="actions">
      <button class="btn btn-secondary btn-sm" onclick="saveConfig()">保存配置</button>
    </div>
  </div>
</div>

<script>
const TYPES=__TYPES_JSON__;
const selected=new Set(['dengbao']);
const grid=document.getElementById('typeGrid');

Object.entries(TYPES).forEach(([k,v])=>{
  const d=document.createElement('div');
  d.className='type-chip'+(selected.has(k)?' selected':'');
  d.textContent=v.name;
  d.dataset.key=k;
  d.onclick=()=>{
    if(selected.has(k)){selected.delete(k);d.classList.remove('selected')}
    else{selected.add(k);d.classList.add('selected')}
  };
  grid.appendChild(d);
});

function selectAll(){
  document.querySelectorAll('.type-chip').forEach(d=>{selected.add(d.dataset.key);d.classList.add('selected')});
}
function selectNone(){
  selected.clear();
  document.querySelectorAll('.type-chip').forEach(d=>d.classList.remove('selected'));
}

let polling=null;

async function loadConfig(){
  try{
    const r=await fetch('/api/config');
    const c=await r.json();
    document.getElementById('cfgUrl').value=c.base_url||'';
    document.getElementById('cfgPfx').value=c.pfx_path||'';
    document.getElementById('cfgUser').value=c.username||'';
    document.getElementById('cfgPass').value=c.password||'';
    document.getElementById('cfgCookie').value=c.cookie||'';
  }catch(e){console.error(e)}
}

async function saveConfig(){
  const c={
    base_url:document.getElementById('cfgUrl').value,
    pfx_path:document.getElementById('cfgPfx').value,
    username:document.getElementById('cfgUser').value,
    password:document.getElementById('cfgPass').value,
    cookie:document.getElementById('cfgCookie').value,
  };
  await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(c)});
  alert('配置已保存');
}

async function startScrape(){
  if(selected.size===0){alert('请至少选择一种类型');return}
  document.getElementById('btnScrape').disabled=true;
  document.getElementById('log').innerHTML='';
  const types=Array.from(selected);
  await fetch('/api/scrape',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({types})});
  if(polling)clearInterval(polling);
  polling=setInterval(async()=>{
    const r=await fetch('/api/status');
    const d=await r.json();
    renderLog(d.logs);
    if(!d.running){
      clearInterval(polling);polling=null;
      document.getElementById('btnScrape').disabled=false;
      loadFiles();
    }
  },500);
}

function renderLog(logs){
  const el=document.getElementById('log');
  el.innerHTML=logs.map(l=>{
    let c='l-info';
    if(l.includes('[OK]'))c='l-ok';
    else if(l.includes('[X]'))c='l-err';
    else if(l.includes('[!]'))c='l-warn';
    return'<span class="'+c+'">'+esc(l)+'</span>';
  }).join('\n')||'<span class="l-info">等待操作...</span>';
  el.scrollTop=el.scrollHeight;
}
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}

async function loadFiles(){
  try{
    const r=await fetch('/api/files');
    const f=await r.json();
    const el=document.getElementById('files');
    if(!f.length){el.innerHTML='<p class="empty">暂无文件</p>';return}
    el.innerHTML=f.map(x=>
      '<div class="file-item"><a href="/download/'+encodeURIComponent(x.name)+'" download>'+esc(x.name)+'</a><span class="file-time">'+x.time+'</span></div>'
    ).join('');
  }catch(e){console.error(e)}
}

loadConfig();loadFiles();
</script>
</body>
</html>"""


# ============ HTTP 请求处理 ============

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 不输出默认日志

    def _json_response(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _html_response(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/":
            types_json = json.dumps(
                {k: {"name": v["name"]} for k, v in PROJECT_TYPES.items()},
                ensure_ascii=False,
            )
            html = HTML_PAGE.replace("__TYPES_JSON__", types_json)
            self._html_response(html)

        elif path == "/api/status":
            self._json_response({
                "running": scrape_state["running"],
                "logs": scrape_state["logs"],
                "result": scrape_state["result"],
                "error": scrape_state["error"],
            })

        elif path == "/api/config":
            load_config()
            self._json_response({
                "base_url": CONFIG.get("base_url", ""),
                "pfx_path": CONFIG.get("pfx_path", ""),
                "username": CONFIG.get("username", ""),
                "password": CONFIG.get("password", ""),
                "cookie": CONFIG.get("cookie", ""),
            })

        elif path == "/api/files":
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            files = sorted(
                OUTPUT_DIR.glob("*.xlsx"),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            self._json_response([{
                "name": f.name,
                "time": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            } for f in files[:30]])

        elif path.startswith("/download/"):
            filename = path[len("/download/"):]
            # 安全检查：防止路径穿越
            if ".." in filename or "/" in filename or "\\" in filename:
                self._json_response({"error": "无效文件名"}, 400)
                return
            filepath = OUTPUT_DIR / filename
            if filepath.exists() and filepath.suffix == ".xlsx":
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.end_headers()
                self.wfile.write(filepath.read_bytes())
            else:
                self._json_response({"error": "文件不存在"}, 404)

        else:
            self._json_response({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        content_len = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_len)) if content_len > 0 else {}

        if path == "/api/scrape":
            if scrape_state["running"]:
                self._json_response({"error": "正在爬取中，请等待"}, 400)
                return

            types = body.get("types", ["dengbao"])
            # 校验类型
            invalid = [t for t in types if t not in PROJECT_TYPES]
            if invalid:
                self._json_response({"error": f"不支持的类型: {invalid}"}, 400)
                return

            threading.Thread(
                target=_run_scrape, args=(types,), daemon=True
            ).start()
            self._json_response({"status": "started"})

        elif path == "/api/config":
            load_config()
            CONFIG.update(body)
            save_config()
            self._json_response({"status": "saved"})

        else:
            self._json_response({"error": "Not found"}, 404)


def main():
    print("=" * 45)
    print("  项目进度爬虫 - Web GUI")
    print("=" * 45)
    print()
    print(f"[OK] 服务地址: http://localhost:{PORT}")
    print("[OK] 浏览器即将自动打开...")
    print("[..] 按 Ctrl+C 停止服务\n")

    threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()

    server = http.server.HTTPServer(("localhost", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[OK] 服务已停止")
        server.server_close()


if __name__ == "__main__":
    main()
