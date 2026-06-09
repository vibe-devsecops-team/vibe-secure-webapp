# backend/seed.py

import os
import sys
from werkzeug.security import generate_password_hash

# 為了確保在不同執行環境下，能正確地從 'backend' 根目錄匯入模組，
# 我們會嘗試匯入。如果遇到 ImportError，會給出提示。
# 預期此腳本會從專案的根目錄執行，例如：`python backend/seed.py`
try:
    from app import app
    from db import db
    from models import User, Product
except ImportError as e:
    print(f"錯誤：無法匯入模組。請確認您是否從專案根目錄執行此腳本，")
    print(f"或 'backend' 目錄已正確設定為 Python 模組路徑。詳細錯誤：{e}")
    sys.exit(1)


def create_seed_data():
    """
    在資料庫中建立測試資料。
    包含一個測試使用者和多筆測試商品。
    此函數必須在 Flask application context 中執行。
    """
    print("--- 開始建立種子資料 ---")

    # --- 建立測試使用者 ---
    # 從環境變數讀取使用者名稱和密碼，若未設定則使用合理的預設值。
    # 這是為了避免在程式碼中硬編碼任何敏感資訊。
    test_username = os.getenv("SEED_USERNAME", "testuser")
    # 測試用密碼，絕不可用於生產環境。
    # 即使是測試密碼，也必須經過雜湊處理後儲存。
    test_password = os.getenv("SEED_PASSWORD", "password123")

    print(f"\n嘗試建立測試使用者: '{test_username}'")

    # 檢查使用者是否已存在，以確保腳本可重複執行而不會產生重複資料。
    existing_user = User.query.filter_by(username=test_username).first()
    if existing_user:
        print(f"使用者 '{test_username}' 已存在，跳過建立。")
    else:
        # 安全要求：密碼必須用 werkzeug.security 的 generate_password_hash 雜湊後存入。
        # 絕不可儲存明文密碼，也不可印出密碼或雜湊值。
        hashed_password = generate_password_hash(test_password)
        new_user = User(username=test_username, password_hash=hashed_password)
        db.session.add(new_user)
        print(f"使用者 '{test_username}' 已成功建立。")

    # --- 建立測試商品 ---
    # 定義多筆測試商品資料，方便測試搜尋和商品列表功能。
    products_data = [
        {"name": "智慧型手機", "description": "最新款的智慧型手機，擁有強大處理器和高清螢幕，拍照功能卓越。", "price": 19999.00, "stock": 50},
        {"name": "藍牙耳機", "description": "高品質音效，舒適佩戴，超長續航的無線藍牙耳機，支援降噪。", "price": 2499.00, "stock": 120},
        {"name": "筆記型電腦", "description": "輕薄便攜，性能卓越，適合辦公與娛樂的筆記型電腦，配備SSD。", "price": 35999.00, "stock": 30},
        {"name": "智能手錶", "description": "健康監測、訊息通知、多種運動模式的智能手錶，防水設計。", "price": 5999.00, "stock": 80},
        {"name": "無線充電板", "description": "支援多種設備的快速無線充電板，桌面更整潔，兼容Qi標準。", "price": 899.00, "stock": 200},
    ]

    print("\n--- 嘗試建立測試商品 ---")
    for product_info in products_data:
        product_name = product_info["name"]
        # 檢查商品是否已存在，避免重複建立。
        existing_product = Product.query.filter_by(name=product_name).first()
        if existing_product:
            print(f"商品 '{product_name}' 已存在，跳過建立。")
        else:
            new_product = Product(
                name=product_name,
                description=product_info["description"],
                price=product_info["price"],
                stock=product_info["stock"]
            )
            db.session.add(new_product)
            print(f"商品 '{product_name}' 已成功建立。")

    # 提交所有變更到資料庫。
    try:
        db.session.commit()
        print("\n--- 所有種子資料已成功提交至資料庫 ---")
    except Exception as e:
        # 若有任何錯誤，回滾事務以保持資料庫狀態一致。
        db.session.rollback()
        print(f"\n--- 提交資料時發生錯誤: {e}，已回滾 ---")
    finally:
        # 確保關閉資料庫 session，釋放資源。
        db.session.close()


if __name__ == "__main__":
    # 所有的資料庫操作都必須在 Flask application context 底下執行。
    # 這是因為 SQLAlchemy 實例 `db` 是綁定在 Flask app 物件上的。
    with app.app_context():
        create_seed_data()
