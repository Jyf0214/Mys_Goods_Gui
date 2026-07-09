"""
米游社商品兑换助手 - 网页版
基于 Flask + SocketIO 的 Web GUI
"""
import os
import sys
import json
import uuid
import base64
import tempfile
import threading
from pathlib import Path
from io import BytesIO
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit

# 将 pyqt_app 加入路径以复用核心模块
WEB_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = WEB_DIR.parent
PYQT_DIR = PROJECT_DIR / 'pyqt_app'
sys.path.insert(0, str(PYQT_DIR))

from utils.http_client import get_http_client
from utils.storage import Storage
from utils.helpers import build_task_config
from utils.logger import setup_logger, get_logger
from core.goods import GoodsService
from core.auth import AuthService as BaseAuthService

setup_logger()
logger = get_logger()

app = Flask(__name__,
            template_folder=str(WEB_DIR / 'templates'),
            static_folder=str(WEB_DIR / 'static'))
app.config['SECRET_KEY'] = 'mys_goods_gui_web'

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 全局存储实例（使用 web_app 目录下的 data）
WEB_DATA_DIR = WEB_DIR / 'data'
WEB_DATA_DIR.mkdir(exist_ok=True)

storage = Storage()
storage.data_dir = WEB_DATA_DIR
storage.config_file = WEB_DATA_DIR / 'config.json'
storage.tasks_file = WEB_DATA_DIR / 'tasks.json'
storage.wishlist_file = WEB_DATA_DIR / 'wishlist.json'
storage._ensure_files()

goods_service = GoodsService()
http_client = get_http_client()


# ─── 认证服务（无 PyQt 依赖） ────────────────────────────────────────────────

class WebAuthService:
    """网页版认证服务"""

    APP_VERSION = BaseAuthService.APP_VERSION
    DEVICE_NAME = BaseAuthService.DEVICE_NAME
    DEVICE_MODEL = BaseAuthService.DEVICE_MODEL
    LATEST_COOKIE_NAMES = BaseAuthService.LATEST_COOKIE_NAMES
    COMPAT_COOKIE_NAMES = BaseAuthService.COMPAT_COOKIE_NAMES

    def __init__(self):
        self.http_client = get_http_client()
        self.device_id = uuid.uuid4().hex
        self._checking = False

    def _get_headers(self):
        return {
            "x-rpc-app_version": self.APP_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-rpc-game_biz": "bbs_cn",
            "x-rpc-sys_version": "12",
            "x-rpc-device_id": self.device_id,
            "x-rpc-device_name": self.DEVICE_NAME,
            "x-rpc-device_model": self.DEVICE_MODEL,
            "x-rpc-app_id": "bll8iq97cem8",
            "x-rpc-client_type": "4",
            "User-Agent": "okhttp/4.9.3",
        }

    def generate_qr_code(self):
        """生成二维码，返回 (qr_url, ticket) 或 (None, None)"""
        url = "https://passport-api.miyoushe.com/account/ma-cn-passport/web/createQRLogin"
        response = self.http_client.post(url, headers=self._get_headers())
        if not response or response.get('retcode') != 0:
            logger.error("生成二维码失败")
            return None, None

        data = response.get('data', {})
        qr_url = data.get('url')
        ticket = data.get('ticket')
        logger.info("二维码生成成功")
        return qr_url, ticket

    def create_qr_base64(self, qr_url: str) -> str:
        """生成二维码图片的 Base64 字符串"""
        import qrcode
        qr = qrcode.QRCode()
        qr.add_data(qr_url)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue()).decode('utf-8')

    def check_login_status(self, ticket: str):
        """检查登录状态，返回 (status, cookies_or_error)"""
        url = 'https://passport-api.miyoushe.com/account/ma-cn-passport/web/queryQRLoginStatus'
        data = {"ticket": ticket}

        response = self.http_client.get_raw_response(url, headers=self._get_headers(), json_data=data)
        if not response:
            return 'error', '网络请求失败'

        try:
            res = response.json()
            if res.get('retcode') == 0:
                status = res.get('data', {}).get('status')
                if status == "Created":
                    return 'waiting', '等待扫码确认...'
                elif status == "Confirmed":
                    cookies = self._parse_cookies(
                        response.headers.get('Set-Cookie', ''),
                        response.cookies.get_dict(),
                    )
                    if cookies:
                        return 'success', cookies
                    else:
                        return 'error', '解析 Cookie 失败'
                else:
                    return 'waiting', f'未知状态: {status}'
            else:
                return 'error', res.get('message', '未知错误')
        except Exception as e:
            return 'error', f'解析响应失败: {e}'

    def _parse_cookies(self, set_cookie, response_cookies=None):
        """解析 Cookie"""
        from http.cookies import SimpleCookie
        import re

        cookie_dict = dict(response_cookies or {})
        parsed = SimpleCookie()
        try:
            parsed.load(set_cookie)
            cookie_dict.update({name: morsel.value for name, morsel in parsed.items()})
        except Exception:
            for name, value in re.findall(r'([^=;\s]+)=([^;]+)', set_cookie):
                cookie_dict[name] = value

        cookie_dict = self._normalize_cookies(cookie_dict)
        return cookie_dict if self._has_supported_cookies(cookie_dict) else None

    def parse_manual_cookies(self, cookie_str: str):
        """解析手动输入的 Cookie"""
        try:
            cookies = cookie_str.split('; ')
            cookie_dict = {}
            for cookie in cookies:
                if '=' in cookie:
                    key, value = cookie.split('=', 1)
                    cookie_dict[key] = value

            cookie_dict = self._normalize_cookies(cookie_dict)
            if self._has_supported_cookies(cookie_dict):
                return cookie_dict
            return None
        except Exception as e:
            logger.error(f"解析 Cookie 失败: {e}")
            return None

    @classmethod
    def _normalize_cookies(cls, cookies):
        normalized = {k.strip(): v.strip() for k, v in cookies.items() if k and v}
        account_id = (normalized.get("account_id") or normalized.get("ltuid") or
                      normalized.get("account_id_v2") or normalized.get("ltuid_v2"))
        mid = normalized.get("account_mid_v2") or normalized.get("ltmid_v2")
        cookie_token = normalized.get("cookie_token") or normalized.get("cookie_token_v2")
        ltoken = normalized.get("ltoken") or normalized.get("ltoken_v2")

        if account_id:
            normalized.setdefault("account_id", account_id)
            normalized.setdefault("ltuid", account_id)
            normalized.setdefault("account_id_v2", account_id)
            normalized.setdefault("ltuid_v2", account_id)
        if mid:
            normalized.setdefault("account_mid_v2", mid)
            normalized.setdefault("ltmid_v2", mid)
        if cookie_token:
            normalized.setdefault("cookie_token", cookie_token)
            normalized.setdefault("cookie_token_v2", cookie_token)
        if ltoken:
            normalized.setdefault("ltoken", ltoken)
            normalized.setdefault("ltoken_v2", ltoken)

        return normalized

    @classmethod
    def _has_supported_cookies(cls, cookies):
        latest_ok = all(name in cookies for name in cls.LATEST_COOKIE_NAMES)
        compat_ok = all(name in cookies for name in cls.COMPAT_COOKIE_NAMES) and "account_mid_v2" in cookies
        return latest_ok or compat_ok

    @staticmethod
    def cookies_to_string(cookies):
        normalized = WebAuthService._normalize_cookies(cookies)
        return ';'.join(f"{k}={v}" for k, v in normalized.items())


web_auth = WebAuthService()

# ─── 任务管理 ──────────────────────────────────────────────────────────────────

running_tasks = {}  # {task_name: threading.Thread}
task_stop_events = {}  # {task_name: threading.Event}


def run_exchange_task(task_config, stop_event):
    """在线程中运行兑换任务"""
    import asyncio
    import httpx
    import ntplib

    name = task_config['name']
    target_time = datetime.fromisoformat(task_config['time'])
    count = task_config.get('count', 5)
    payload = task_config['payload']
    headers = task_config['headers']

    socketio.emit('task_log', {'task': name, 'message': f'任务已启动，目标时间: {target_time}'})

    # NTP 时间校准
    time_offset = 0
    try:
        client = ntplib.NTPClient()
        response = client.request('ntp.aliyun.com', timeout=5)
        ntp_time = datetime.utcfromtimestamp(response.tx_time).replace(
            hour=datetime.utcfromtimestamp(response.tx_time).hour + 8
        ) if False else datetime.utcfromtimestamp(response.tx_time)
        from datetime import timedelta
        ntp_time = datetime.utcfromtimestamp(response.tx_time) + timedelta(hours=8)
        time_offset = (ntp_time - datetime.now()).total_seconds()
        socketio.emit('task_log', {'task': name, 'message': f'NTP 校准成功，偏移: {time_offset:.3f} 秒'})
    except Exception as e:
        socketio.emit('task_log', {'task': name, 'message': f'NTP 校准失败: {e}，使用本地时间'})

    from datetime import timedelta

    while not stop_event.is_set():
        current_time = datetime.now() + timedelta(seconds=time_offset)
        delay = (target_time - current_time).total_seconds()

        if delay <= 5:
            if delay > 0:
                socketio.emit('task_log', {'task': name, 'message': f'还剩 {delay:.3f} 秒，准备执行...'})
                stop_event.wait(max(0, delay - 0.05))

            if stop_event.is_set():
                break

            # 并发执行多次兑换
            socketio.emit('task_log', {'task': name, 'message': '开始执行兑换...'})

            async def do_exchange():
                async with httpx.AsyncClient() as client:
                    for _ in range(count):
                        try:
                            resp = await client.post(
                                "https://bbs-api.miyoushe.com/common/homushop/v1/web/goods/exchange",
                                data=json.dumps(payload),
                                headers=headers,
                                timeout=10
                            )
                            result = resp.text
                            socketio.emit('task_log', {'task': name, 'message': f'兑换结果: {result}'})
                            logger.info(f"任务 {name} 返回: {result}")
                        except Exception as e:
                            socketio.emit('task_log', {'task': name, 'message': f'兑换失败: {e}'})

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(do_exchange())
            finally:
                loop.close()

            socketio.emit('task_log', {'task': name, 'message': '任务执行完成'})
            socketio.emit('task_completed', {'task': name})
            break

        elif delay <= 60:
            socketio.emit('task_log', {'task': name, 'message': f'还剩 {delay:.1f} 秒'})
            stop_event.wait(1)
        elif delay <= 300:
            socketio.emit('task_log', {'task': name, 'message': f'还剩 {delay:.0f} 秒'})
            for _ in range(5):
                if stop_event.is_set():
                    break
                stop_event.wait(1)
        else:
            socketio.emit('task_log', {'task': name, 'message': f'当前时间: {current_time.strftime("%H:%M:%S")}, 还剩 {delay:.0f} 秒'})
            for _ in range(min(30, int(delay - 60))):
                if stop_event.is_set():
                    break
                stop_event.wait(1)

    if name in running_tasks:
        del running_tasks[name]
    if name in task_stop_events:
        del task_stop_events[name]


# ─── 页面路由 ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/favicon.ico')
def favicon():
    icon_path = WEB_DIR.parent / 'pyqt_app' / 'tray_icon.ico'
    if icon_path.exists():
        return send_from_directory(str(icon_path.parent), icon_path.name, mimetype='image/x-icon')
    return '', 204


# ─── API 路由 ──────────────────────────────────────────────────────────────────

@app.route('/api/login/status', methods=['GET'])
def api_login_status():
    """检查登录状态"""
    cookies = storage.get_cookies()
    if cookies and 'account_id' in cookies:
        return jsonify({
            'logged_in': True,
            'account_id': cookies.get('account_id', ''),
        })
    return jsonify({'logged_in': False})


@app.route('/api/login/qr/generate', methods=['POST'])
def api_qr_generate():
    """生成二维码"""
    qr_url, ticket = web_auth.generate_qr_code()
    if qr_url and ticket:
        qr_base64 = web_auth.create_qr_base64(qr_url)
        return jsonify({
            'success': True,
            'qr_image': f'data:image/png;base64,{qr_base64}',
            'ticket': ticket,
        })
    return jsonify({'success': False, 'message': '生成二维码失败'}), 400


@app.route('/api/login/qr/check', methods=['POST'])
def api_qr_check():
    """检查二维码登录状态"""
    data = request.get_json()
    ticket = data.get('ticket', '')
    if not ticket:
        return jsonify({'status': 'error', 'message': '缺少 ticket'}), 400

    status, result = web_auth.check_login_status(ticket)
    if status == 'success':
        device_id = uuid.uuid4().hex
        storage.save_cookies(result, device_id)
        return jsonify({'status': 'success', 'message': '登录成功'})
    elif status == 'error':
        return jsonify({'status': 'error', 'message': result})
    else:
        return jsonify({'status': 'waiting', 'message': result})


@app.route('/api/login/manual', methods=['POST'])
def api_manual_login():
    """手动 Cookie 登录"""
    data = request.get_json()
    cookie_str = data.get('cookie', '').strip()
    if not cookie_str:
        return jsonify({'success': False, 'message': '请输入 Cookie'}), 400

    cookies = web_auth.parse_manual_cookies(cookie_str)
    if cookies:
        device_id = uuid.uuid4().hex
        storage.save_cookies(cookies, device_id)
        return jsonify({'success': True, 'message': '登录成功'})
    else:
        return jsonify({
            'success': False,
            'message': 'Cookie 格式不正确或缺少必要字段'
        }), 400


@app.route('/api/games', methods=['GET'])
def api_games():
    """获取游戏列表"""
    games = goods_service.get_game_list()
    if games is not None:
        return jsonify({'success': True, 'games': games})
    return jsonify({'success': False, 'message': '获取游戏列表失败'}), 500


@app.route('/api/goods/<game_key>', methods=['GET'])
def api_goods(game_key):
    """获取商品列表"""
    cookies = storage.get_cookies()
    cookie_str = WebAuthService.cookies_to_string(cookies)

    goods = goods_service.get_goods_list(game_key, cookie_str)
    if goods is not None:
        return jsonify({'success': True, 'goods': goods})
    return jsonify({'success': False, 'message': '获取商品列表失败'}), 500


@app.route('/api/points', methods=['GET'])
def api_points():
    """获取米游币数量"""
    cookies = storage.get_cookies()
    cookie_str = WebAuthService.cookies_to_string(cookies)

    points = goods_service.get_user_points(cookie_str)
    return jsonify({'success': True, 'points': points or 0})


@app.route('/api/addresses', methods=['GET'])
def api_addresses():
    """获取收货地址列表"""
    cookies = storage.get_cookies()
    cookie_str = WebAuthService.cookies_to_string(cookies)

    addresses = goods_service.get_address_list(cookie_str)
    return jsonify({'success': True, 'addresses': addresses or []})


@app.route('/api/wishlist', methods=['GET'])
def api_wishlist_get():
    """获取心愿单"""
    wishlist = storage.get_wishlist()
    return jsonify({'success': True, 'wishlist': wishlist})


@app.route('/api/wishlist', methods=['POST'])
def api_wishlist_add():
    """添加到心愿单"""
    data = request.get_json()
    item = {
        'name': data.get('name', ''),
        'id': data.get('id', ''),
        'time': data.get('time', ''),
        'biz': data.get('biz', ''),
    }
    storage.add_to_wishlist(item)
    return jsonify({'success': True, 'message': f'已添加: {item["name"]}'})


@app.route('/api/wishlist', methods=['DELETE'])
def api_wishlist_clear():
    """清空心愿单"""
    storage.clear_wishlist()
    return jsonify({'success': True, 'message': '心愿单已清空'})


@app.route('/api/tasks', methods=['GET'])
def api_tasks_get():
    """获取任务列表"""
    tasks = storage.get_tasks()
    # 标记运行状态
    for task in tasks:
        task['running'] = task['name'] in running_tasks
    return jsonify({'success': True, 'tasks': tasks})


@app.route('/api/tasks', methods=['POST'])
def api_tasks_create():
    """创建任务"""
    data = request.get_json()
    name = data.get('name', '').strip()
    goods_id = data.get('goods_id', '')
    game_biz = data.get('game_biz', '')
    address_id = data.get('address_id', '')
    time_str = data.get('time', '')
    count = data.get('count', 5)

    if not name:
        return jsonify({'success': False, 'message': '请输入任务名称'}), 400
    if not goods_id:
        return jsonify({'success': False, 'message': '请选择商品'}), 400

    cookies = storage.get_cookies()
    cookie_str = WebAuthService.cookies_to_string(cookies)
    device_id = storage.get_device_id()
    uid = cookies.get('account_id', '')

    task_config = build_task_config(
        name=name,
        goods_id=goods_id,
        uid=uid,
        game_biz=game_biz,
        address_id=address_id,
        device_id=device_id,
        cookie=cookie_str,
        time=time_str,
        count=count,
    )

    storage.add_task(task_config)
    return jsonify({'success': True, 'message': '任务创建成功'})


@app.route('/api/tasks/<task_name>', methods=['DELETE'])
def api_tasks_delete(task_name):
    """删除任务"""
    if task_name in running_tasks:
        return jsonify({'success': False, 'message': '请先停止运行中的任务'}), 400

    storage.remove_task(task_name)
    return jsonify({'success': True, 'message': '任务已删除'})


@app.route('/api/tasks/clear', methods=['DELETE'])
def api_tasks_clear():
    """清空任务列表"""
    if running_tasks:
        return jsonify({'success': False, 'message': '请先停止所有运行中的任务'}), 400

    storage.clear_tasks()
    return jsonify({'success': True, 'message': '任务列表已清空'})


@app.route('/api/tasks/<task_name>/start', methods=['POST'])
def api_task_start(task_name):
    """启动任务"""
    if task_name in running_tasks:
        return jsonify({'success': False, 'message': '任务已在运行中'}), 400

    tasks = storage.get_tasks()
    task_config = None
    for t in tasks:
        if t['name'] == task_name:
            task_config = t
            break

    if not task_config:
        return jsonify({'success': False, 'message': '任务不存在'}), 404

    stop_event = threading.Event()
    thread = threading.Thread(target=run_exchange_task, args=(task_config, stop_event), daemon=True)
    thread.start()

    running_tasks[task_name] = thread
    task_stop_events[task_name] = stop_event

    return jsonify({'success': True, 'message': '任务已启动'})


@app.route('/api/tasks/<task_name>/stop', methods=['POST'])
def api_task_stop(task_name):
    """停止任务"""
    if task_name not in running_tasks:
        return jsonify({'success': False, 'message': '任务未在运行'}), 400

    stop_event = task_stop_events.get(task_name)
    if stop_event:
        stop_event.set()

    return jsonify({'success': True, 'message': '任务已停止'})


@app.route('/api/logs', methods=['GET'])
def api_logs():
    """获取日志"""
    log_file = WEB_DIR / 'logs' / 'app.log'
    if not log_file.exists():
        return jsonify({'success': True, 'content': ''})

    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'success': True, 'content': content})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ─── SocketIO 事件 ────────────────────────────────────────────────────────────

@socketio.on('connect')
def handle_connect():
    logger.info("WebSocket 客户端已连接")


@socketio.on('disconnect')
def handle_disconnect():
    logger.info("WebSocket 客户端已断开")


# ─── 启动 ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"启动网页版米游社商品兑换助手")
    print(f"访问地址: http://localhost:{port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
