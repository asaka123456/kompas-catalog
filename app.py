from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import json
import base64
import re
from datetime import datetime
from io import BytesIO

app = Flask(__name__)
CORS(app)

DATA_FOLDER = 'data'
METADATA_FILE = os.path.join(DATA_FOLDER, 'catalog.json')
os.makedirs(DATA_FOLDER, exist_ok=True)

def load_catalog():
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_catalog(catalog):
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

# HTML прямо в коде
HTML_PAGE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Каталог файлов</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 600px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 { color: white; font-size: 1.8rem; margin-bottom: 8px; }
        .header p { color: rgba(255,255,255,0.8); }
        .card {
            background: white;
            border-radius: 24px;
            padding: 28px;
            margin-bottom: 24px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.15);
        }
        .card h2 { font-size: 1.3rem; margin-bottom: 20px; color: #1a2a3a; }
        .form-group { margin-bottom: 20px; }
        label { display: block; font-weight: 600; margin-bottom: 8px; color: #2a3a4a; }
        input {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e2e8f0;
            border-radius: 16px;
            font-size: 1rem;
        }
        input:focus { outline: none; border-color: #764ba2; }
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 16px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
        }
        button:hover { transform: translateY(-2px); }
        button:disabled { opacity: 0.6; cursor: not-allowed; }
        .upload-area {
            border: 2px dashed #cbd5e1;
            border-radius: 20px;
            padding: 20px;
            text-align: center;
            background: #fafcff;
            cursor: pointer;
            margin-bottom: 16px;
        }
        .upload-area:hover { border-color: #764ba2; background: rgba(118, 75, 162, 0.05); }
        .file-name { margin-top: 8px; font-size: 0.85rem; color: #764ba2; }
        .message {
            margin-top: 16px;
            padding: 10px 16px;
            border-radius: 16px;
            font-size: 0.85rem;
            display: none;
        }
        .message.success { background: #d4f5e6; color: #1a6e4a; display: block; }
        .message.error { background: #fee2e2; color: #c04030; display: block; }
        .message.info { background: #e0f0ff; color: #2c6e9e; display: block; }
        .search-row { display: flex; gap: 10px; }
        .search-row input { flex: 1; }
        .search-row button { width: auto; }
        .spinner {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid white;
            border-top-color: transparent;
            border-radius: 50%;
            animation: spin 0.6s linear infinite;
            margin-right: 8px;
            vertical-align: middle;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .hint-text { font-size: 0.7rem; color: #7a8a9a; margin-top: 5px; }
        @media (max-width: 600px) {
            .search-row { flex-direction: column; }
            .search-row button { width: 100%; }
        }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>Каталог файлов</h1>
        <p></p>
    </div>

    <div class="card">
        <h2>🔍 Найти</h2>
        <div class="search-row">
            <input type="text" id="searchCode" placeholder="Введите кодовое слово" autocomplete="off">
            <button id="searchBtn">📥 Скачать</button>
        </div>
        <div id="searchMessage" class="message"></div>
    </div>

    <div class="card">
        <h2>⬆️ Загрузить</h2>
        <div class="form-group">
            <label>Кодовое слово (придумайте уникальное) *</label>
            <input type="text" id="newCode" placeholder="например: шестерня_01">
            <div class="hint-text">Только буквы (рус/eng), цифры, _ и -</div>
        </div>
        <div class="form-group">
            <label>Название(необязательно)</label>
            <input type="text" id="newName" placeholder="например: Мой файл">
        </div>
        <div class="upload-area" id="uploadArea">
            📂 Нажмите или перетащите файл (макс. 15 МБ)
            <input type="file" id="fileInput" style="display: none;">
            <div id="fileNameDisplay" class="file-name"></div>
        </div>
        <button id="uploadBtn">✅ Загрузить файл</button>
        <div id="uploadMessage" class="message"></div>
    </div>
</div>

<script>
    async function callApi(endpoint, options = {}) {
        const response = await fetch(`/api/${endpoint}`, options);
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Ошибка запроса');
        }
        return await response.json();
    }

    async function uploadDetail(code, name, file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = async function(e) {
                try {
                    const result = await callApi('upload', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            code: code,
                            name: name,
                            fileName: file.name,
                            fileData: e.target.result
                        })
                    });
                    resolve(result);
                } catch (err) {
                    reject(err);
                }
            };
            reader.onerror = () => reject(new Error('Ошибка чтения файла'));
            reader.readAsDataURL(file);
        });
    }

    function showMessage(element, text, type) {
        element.textContent = text;
        element.className = `message ${type}`;
        element.style.display = 'block';
        setTimeout(() => {
            element.style.display = 'none';
        }, 4000);
    }

    function isValidCode(code) {
        return /^[a-zA-Zа-яА-ЯёЁ0-9_-]+$/.test(code);
    }

    const searchInput = document.getElementById('searchCode');
    const searchBtn = document.getElementById('searchBtn');
    const searchMsg = document.getElementById('searchMessage');
    const newCodeInput = document.getElementById('newCode');
    const newNameInput = document.getElementById('newName');
    const fileInput = document.getElementById('fileInput');
    const uploadArea = document.getElementById('uploadArea');
    const fileNameDisplay = document.getElementById('fileNameDisplay');
    const uploadBtn = document.getElementById('uploadBtn');
    const uploadMsg = document.getElementById('uploadMessage');

    let selectedFile = null;

    function handleFileSelect(file) {
        if (!file) {
            selectedFile = null;
            fileNameDisplay.textContent = '';
            return;
        }
        if (file.size > 15 * 1024 * 1024) {
            showMessage(uploadMsg, '❌ Файл слишком большой (макс. 15 МБ)', 'error');
            fileInput.value = '';
            selectedFile = null;
            return;
        }
        selectedFile = file;
        fileNameDisplay.textContent = `📎 ${file.name} (${(file.size/1024/1024).toFixed(2)} МБ)`;
    }

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) handleFileSelect(e.target.files[0]);
    });

    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', (e) => e.preventDefault());
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        if (e.dataTransfer.files.length) {
            handleFileSelect(e.dataTransfer.files[0]);
            fileInput.files = e.dataTransfer.files;
        }
    });

    uploadBtn.addEventListener('click', async () => {
        const code = newCodeInput.value.trim();
        const name = newNameInput.value.trim();

        if (!code) {
            showMessage(uploadMsg, '❌ Введите кодовое слово', 'error');
            return;
        }
        if (!isValidCode(code)) {
            showMessage(uploadMsg, '❌ Только буквы, цифры, _ и -', 'error');
            return;
        }
        if (!selectedFile) {
            showMessage(uploadMsg, '❌ Выберите файл', 'error');
            return;
        }

        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<span class="spinner"></span> Загрузка...';

        try {
            await uploadDetail(code, name, selectedFile);
            showMessage(uploadMsg, `✅ Файл "${code}" загружен!`, 'success');
            newCodeInput.value = '';
            newNameInput.value = '';
            selectedFile = null;
            fileInput.value = '';
            fileNameDisplay.textContent = '';
        } catch (err) {
            showMessage(uploadMsg, `❌ ${err.message}`, 'error');
        } finally {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = '✅ Загрузить';
        }
    });

    searchBtn.addEventListener('click', () => {
        const code = searchInput.value.trim();
        if (!code) {
            showMessage(searchMsg, '⚠️ Введите кодовое слово', 'error');
            return;
        }
        window.location.href = `/api/download/${encodeURIComponent(code)}`;
        showMessage(searchMsg, `⏳ Скачивание...`, 'info');
    });

    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') searchBtn.click();
    });
</script>
</body>
</html>
'''

@app.route('/')
def index():
    return HTML_PAGE

@app.route('/api/upload', methods=['POST'])
def api_upload():
    try:
        data = request.get_json()
        code = data.get('code', '').strip()
        name = data.get('name', '').strip()
        file_data_b64 = data.get('fileData', '')
        original_filename = data.get('fileName', '')

        if not code:
            return jsonify({'error': 'Введите кодовое слово'}), 400

        if not re.match(r'^[a-zA-Zа-яА-ЯёЁ0-9_-]+$', code):
            return jsonify({'error': 'Код может содержать только буквы, цифры, _ и -'}), 400

        catalog = load_catalog()
        if code in catalog:
            return jsonify({'error': f'Код "{code}" уже занят'}), 409

        if not file_data_b64:
            return jsonify({'error': 'Файл не выбран'}), 400

        if not name:
            name = re.sub(r'\.[^/.]+$', '', original_filename)

        if ',' in file_data_b64:
            file_data_b64 = file_data_b64.split(',')[1]

        catalog[code] = {
            'name': name,
            'fileName': original_filename,
            'uploadDate': datetime.now().isoformat(),
            'fileData': file_data_b64
        }
        save_catalog(catalog)

        return jsonify({'success': True, 'code': code})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<code>')
def api_download(code):
    catalog = load_catalog()
    if code not in catalog:
        return jsonify({'error': 'Файл не найден'}), 404

    info = catalog[code]
    file_data_b64 = info.get('fileData')
    if not file_data_b64:
        return jsonify({'error': 'Файл повреждён'}), 500

    try:
        file_bytes = base64.b64decode(file_data_b64)
        return send_file(
            BytesIO(file_bytes),
            as_attachment=True,
            download_name=info.get('fileName', f'{code}.bin'),
            mimetype='application/octet-stream'
        )
    except Exception as e:
        return jsonify({'error': f'Ошибка при скачивании: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
