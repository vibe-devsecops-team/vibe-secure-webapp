# backend/app.py

# 1. 匯入必要的模組
import os
from flask import Flask
from flask_cors import CORS

# 從 backend 根目錄進行絕對匯入
# 假設 db.py 提供了 db 實例和 get_database_uri 函數
from db import db, get_database_uri
# 匯入模型以確保它們被 SQLAlchemy 註冊，以便 db.create_all() 能正確建立資料表
from models import User, Product
# 匯入 Blueprint
from routes.auth import auth_bp
from routes.products import products_bp

# 2. 建立 module 層級的 Flask 應用程式實例
# 方便日後用 gunicorn 以 app:app 啟動
app = Flask(__name__)

# 3. 從環境變數讀取設定
# 連線字串與 SECRET_KEY 一律從環境變數讀取，嚴禁寫死在程式碼中
secret_key = os.environ.get('FLASK_SECRET_KEY')
if not secret_key:
    # SECRET_KEY 對於 Flask Session 和其他安全功能至關重要，若未設定則應立即停止應用程式
    raise RuntimeError("FLASK_SECRET_KEY environment variable not set. This is critical for session security.")

app.config['SECRET_KEY'] = secret_key
app.config['SQLALCHEMY_DATABASE_URI'] = get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # 禁用 SQLAlchemy 事件追蹤，減少記憶體開銷

# debug 模式不可寫死為 True；預設為 False（或由環境變數控制）
# Flask debug 模式會開啟可遠端執行程式碼的除錯器，是嚴重風險
app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

# 4. 初始化資料庫
db.init_app(app)

# 5. 在應用程式啟動時，於 app context 內呼叫 db.create_all() 建立資料表
# 這確保了在應用程式啟動時，所有定義在 models 中的資料表都會被建立
# 注意：在生產環境中，通常會使用 Alembic 等資料庫遷移工具來管理資料表結構
with app.app_context():
    db.create_all()

# 6. 註冊所有 Blueprint
app.register_blueprint(auth_bp)
app.register_blueprint(products_bp)

# 7. 設定 CORS (使用 flask-cors)
# 因為登入用 Flask session、前後端不同來源、需要帶 cookie，所以 supports_credentials=True
# 且因帶憑證時瀏覽器不允許萬用字元，origin 必須指定明確的前端來源
# 開發可先設為 http://localhost:8080，實際埠號之後再調整
frontend_origin = os.environ.get('FLASK_FRONTEND_ORIGIN', 'http://localhost:8080')
CORS(app, supports_credentials=True, origins=[frontend_origin])

# 8. 提供 if __name__ == "__main__" 區塊以利本機執行
if __name__ == "__main__":
    # 在本地開發時，可以透過設定 FLASK_DEBUG 環境變數來啟用 debug 模式
    # 在生產環境中，此值應為 False
    print(f"Running Flask app in debug mode: {app.config['DEBUG']}")
    print(f"CORS configured for origin: {frontend_origin}")
    # 不可在 log 或回應中印出機密，這裡只印出配置資訊
    app.run(host='0.0.0.0', port=5000)
