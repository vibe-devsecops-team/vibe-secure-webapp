# routes/auth.py

from flask import Blueprint, request, jsonify, session
from werkzeug.security import check_password_hash
# 假設 db.py 和 models.py 在專案根目錄或可透過相對路徑存取
from db import db
from models import User

# 定義 Flask Blueprint，名稱為 auth_bp
auth_bp = Blueprint('auth_bp', __name__)

# --- 安全相關常數 ---
# 輸入驗證：使用者名稱與密碼的長度限制
MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 50
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

# 錯誤訊息：通用錯誤訊息，避免帳號列舉攻擊
GENERIC_AUTH_ERROR = "Invalid username or password"
# --- 安全相關常數結束 ---


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    處理使用者登入請求。
    接收 JSON 格式的 username 和 password，驗證後回傳登入結果。
    """
    # 1. 取得請求中的 JSON 資料
    data = request.get_json()
    if not data:
        # 若請求非 JSON 格式，回傳 400 Bad Request
        return jsonify({"message": "Request must be JSON"}), 400

    username = data.get('username')
    password = data.get('password')

    # 2. 輸入驗證：檢查 username 和 password 是否存在且符合長度限制
    if not username or not password:
        # 若缺少 username 或 password，回傳 400 Bad Request
        return jsonify({"message": "Username and password are required"}), 400

    if not (MIN_USERNAME_LENGTH <= len(username) <= MAX_USERNAME_LENGTH):
        # 若 username 長度不符，回傳 400 Bad Request
        return jsonify({"message": f"Username must be between {MIN_USERNAME_LENGTH} and {MAX_USERNAME_LENGTH} characters"}), 400

    if not (MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH):
        # 若 password 長度不符，回傳 400 Bad Request
        return jsonify({"message": f"Password must be between {MIN_PASSWORD_LENGTH} and {MAX_PASSWORD_LENGTH} characters"}), 400

    # 3. 查詢使用者：使用 SQLAlchemy ORM 依 username 查詢
    #    此處嚴禁使用字串拼接或 f-string 組 SQL，以防止 SQL Injection
    user = User.query.filter_by(username=username).first()

    # 4. 密碼驗證：使用 werkzeug.security 的 check_password_hash 比對雜湊值
    #    嚴禁比對明文密碼，也禁止將密碼當作查詢條件
    if user and check_password_hash(user.password_hash, password):
        # 5. 登入成功：在 Flask session 中記錄使用者 ID
        session["user_id"] = user.id
        # 回傳成功訊息，HTTP 狀態碼 200 OK
        # 確保回應中不包含任何敏感資訊，如密碼或密碼雜湊值
        return jsonify({"message": "Login successful"}), 200
    else:
        # 6. 登入失敗：回傳通用錯誤訊息
        #    不透露是「帳號不存在」還是「密碼錯誤」，以避免帳號列舉攻擊
        #    HTTP 狀態碼 401 Unauthorized
        return jsonify({"message": GENERIC_AUTH_ERROR}), 401
