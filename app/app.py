from flask import Flask, request, render_template_string, jsonify
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
import logging
import sys
import random
import threading
import time

app = Flask(__name__)

# Настройка логирования для вывода в stdout (Loki читает этот поток)
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# --- МЕТРИКИ PROMETHEUS ---
HTTP_CODE_COUNTER = Counter('app_http_codes_total', 'Count of HTTP codes', ['code'])
USER_ACTIONS = Counter('business_user_actions_total', 'User lifecycle events', ['action'])
UPTIME_GAUGE = Gauge('app_uptime_seconds', 'Number of seconds the app has been running')

# Инициализация меток для корректного отображения в Grafana
ALL_CODES = ['100', '101', '200', '201', '301', '304', '403', '404', '500', '503']
ALL_ACTIONS = ['register', 'login', 'reset_pass', 'delete_acc']

for code in ALL_CODES:
    HTTP_CODE_COUNTER.labels(code=code).inc(0)
for action in ALL_ACTIONS:
    USER_ACTIONS.labels(action=action).inc(0)

# --- ЛОГИКА ФОНОВЫХ ПРОЦЕССОВ ---
start_time = time.time()
stress_test_active = False

def monitor_worker():
    """Фоновый поток: обновление Uptime и генерация нагрузки (включая логи)"""
    global stress_test_active
    while True:
        # 1. Обновление Uptime
        UPTIME_GAUGE.set(time.time() - start_time)
        
        # 2. Генерация данных при включенном стресс-тесте
        if stress_test_active:
            # Генерация метрик кодов и действий
            c = random.choice(ALL_CODES)
            a = random.choice(ALL_ACTIONS)
            HTTP_CODE_COUNTER.labels(code=c).inc()
            USER_ACTIONS.labels(action=a).inc()
            
            # Генерация логов разных типов во время теста
            rand_val = random.random()
            if rand_val < 0.1:
                logger.error(f"STRESS-TEST: Critical system failure detected for action {a}")
            elif rand_val < 0.3:
                logger.warning(f"STRESS-TEST: Slow response time for action {a} with code {c}")
            elif rand_val < 0.6:
                logger.info(f"STRESS-TEST: User successfully executed {a}")
            
            time.sleep(0.3)
        else:
            time.sleep(1)

# Запуск мониторинга в отдельном потоке
threading.Thread(target=monitor_worker, daemon=True).start()

# --- ВЕБ-ИНТЕРФЕЙС (HTML) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>QA Observability Professional Sandbox</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 900px; margin: 40px auto; background: #f0f2f5; padding: 20px; color: #333; }
        .section { background: white; padding: 30px; border-radius: 15px; margin-bottom: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); border: 1px solid #e1e4e8; }
        h3 { color: #1a73e8; margin-top: 0; border-bottom: 2px solid #f0f2f5; padding-bottom: 15px; margin-bottom: 20px; text-transform: uppercase; font-size: 1.1em; }
        
        .radio-group { margin: 15px 0; display: flex; gap: 25px; background: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #dee2e6; }
        .radio-group label { cursor: pointer; font-weight: 600; display: flex; align-items: center; gap: 8px; }
        
        .btn-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; margin-top: 15px; }
        button { padding: 12px; cursor: pointer; border: none; border-radius: 8px; font-weight: bold; transition: all 0.2s ease; }
        button:hover { transform: translateY(-1px); box-shadow: 0 4px 8px rgba(0,0,0,0.1); opacity: 0.9; }
        button:active { transform: translateY(0); }
        
        .btn-log { background: #202124; color: white; width: 100%; margin-top: 15px; font-size: 1em; }
        .btn-1xx { background: #17a2b8; color: white; }
        .btn-2xx { background: #28a745; color: white; }
        .btn-3xx { background: #ffc107; color: #212529; }
        .btn-4xx { background: #fd7e14; color: white; }
        .btn-5xx { background: #dc3545; color: white; }
        .btn-biz { background: #673ab7; color: white; }
        
        .stress-section { background: #fff5f5; border: 2px dashed #ff4d4d; }
        .btn-stress { background: #ff4d4d; color: white; width: 100%; font-size: 1.2em; padding: 18px; }
        .btn-stress.active { background: #28a745; }
        
        .status-box { margin-top: 20px; padding: 12px; background: #e8f0fe; color: #1967d2; border-left: 5px solid #1a73e8; border-radius: 4px; font-weight: bold; display: none; }
        textarea { width: 100%; height: 80px; padding: 15px; box-sizing: border-box; border: 1px solid #ced4da; border-radius: 8px; font-size: 1em; resize: none; }
        
        .lvl-info { color: #28a745; } .lvl-warn { color: #fd7e14; } .lvl-error { color: #dc3545; }
    </style>
</head>
<body>
    <h1>QA Sandbox Control Panel</h1>

    <div class="section">
        <h3>1. Logs (Loki Integration)</h3>
        <textarea id="logMessage" placeholder="Type message to send to Loki logs..."></textarea>
        <div class="radio-group">
            <label class="lvl-info"><input type="radio" name="logLevel" value="info" checked> INFO</label>
            <label class="lvl-warn"><input type="radio" name="logLevel" value="warning"> WARNING</label>
            <label class="lvl-error"><input type="radio" name="logLevel" value="error"> ERROR</label>
        </div>
        <button class="btn-log" onclick="sendLog()">PUSH LOG MESSAGE</button>
        <div id="statusLogs" class="status-box"></div>
    </div>

    <div class="section">
        <h3>2. HTTP Status Codes (Prometheus)</h3>
        <div class="btn-grid">
            <button class="btn-1xx" onclick="sendCode('100')">100 Continue</button>
            <button class="btn-1xx" onclick="sendCode('101')">101 Switching</button>
            <button class="btn-2xx" onclick="sendCode('200')">200 OK</button>
            <button class="btn-2xx" onclick="sendCode('201')">201 Created</button>
            <button class="btn-3xx" onclick="sendCode('301')">301 Moved</button>
            <button class="btn-3xx" onclick="sendCode('304')">304 Not Mod</button>
            <button class="btn-4xx" onclick="sendCode('403')">403 Forbidden</button>
            <button class="btn-4xx" onclick="sendCode('404')">404 Not Found</button>
            <button class="btn-5xx" onclick="sendCode('500')">500 Server Err</button>
            <button class="btn-5xx" onclick="sendCode('503')">503 Service Unav</button>
        </div>
        <div id="statusCodes" class="status-box"></div>
    </div>

    <div class="section">
        <h3>3. Business User Events</h3>
        <div class="btn-grid">
            <button class="btn-biz" onclick="sendAction('register')">User Register</button>
            <button class="btn-biz" onclick="sendAction('login')">User Login</button>
            <button class="btn-biz" onclick="sendAction('reset_pass')">Reset Password</button>
            <button class="btn-biz" onclick="sendAction('delete_acc')">Delete Account</button>
        </div>
        <div id="statusActions" class="status-box"></div>
    </div>

    <div class="section stress-section">
        <h3>4. Load Simulation (Stress Test)</h3>
        <p>Generates 3 requests per second with random codes, business actions and logs.</p>
        <button id="stressButton" class="btn-stress" onclick="toggleStress()">START STRESS TEST</button>
        <div id="statusStress" class="status-box">STRESS TEST IS CURRENTLY RUNNING...</div>
    </div>

    <script>
        function notify(elementId, message) {
            const el = document.getElementById(elementId);
            el.innerText = message;
            el.style.display = 'block';
            if (elementId !== 'statusStress') {
                setTimeout(() => { el.style.display = 'none'; }, 3000);
            }
        }

        async function sendLog() {
            const msg = document.getElementById('logMessage').value;
            const lvl = document.querySelector('input[name="logLevel"]:checked').value;
            
            const formData = new URLSearchParams();
            formData.append('message', msg);
            formData.append('level', lvl);
            
            const response = await fetch('/log', { method: 'POST', body: formData });
            const result = await response.text();
            notify('statusLogs', result);
        }

        async function sendCode(code) {
            const response = await fetch('/status?code=' + code);
            const result = await response.text();
            notify('statusCodes', result);
        }

        async function sendAction(actionName) {
            const formData = new URLSearchParams();
            formData.append('action', actionName);
            
            const response = await fetch('/action', { method: 'POST', body: formData });
            const result = await response.text();
            notify('statusActions', result);
        }

        async function toggleStress() {
            const response = await fetch('/stress', { method: 'POST' });
            const data = await response.json();
            const btn = document.getElementById('stressButton');
            const status = document.getElementById('statusStress');
            
            if (data.active) {
                btn.innerText = 'STOP STRESS TEST';
                btn.classList.add('active');
                status.style.display = 'block';
            } else {
                btn.innerText = 'START STRESS TEST';
                btn.classList.remove('active');
                status.style.display = 'none';
            }
        }
    </script>
</body>
</html>
"""

# --- МАРШРУТЫ (ROUTES) ---

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/log', methods=['POST'])
def handle_log():
    # Получаем данные из формы. Ключи должны совпадать с JS (message, level)
    log_msg = request.form.get('message', 'No message content')
    log_lvl = request.form.get('level', 'info').lower()
    
    if log_lvl == 'error':
        logger.error(f"Manual Entry: {log_msg}")
    elif log_lvl == 'warning':
        logger.warning(f"Manual Entry: {log_msg}")
    else:
        logger.info(f"Manual Entry: {log_msg}")
        
    return f"Success: Sent as {log_lvl.upper()}"

@app.route('/status')
def handle_status():
    code_val = request.args.get('code', '200')
    HTTP_CODE_COUNTER.labels(code=code_val).inc()
    
    # Обработка ответов для браузера
    if code_val in ['100', '101', '304']:
        return f"HTTP {code_val} recorded", 200
    
    try:
        return f"HTTP {code_val} recorded", int(code_val)
    except:
        return "Invalid code", 400

@app.route('/action', methods=['POST'])
def handle_action():
    act_name = request.form.get('action', 'unknown')
    USER_ACTIONS.labels(action=act_name).inc()
    return f"Business Action '{act_name}' tracked"

@app.route('/stress', methods=['POST'])
def handle_stress():
    global stress_test_active
    stress_test_active = not stress_test_active
    return jsonify({"active": stress_test_active})

@app.route('/metrics')
def handle_metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

if __name__ == '__main__':
    # Слушаем на порту 5000
    app.run(host='0.0.0.0', port=5000)