# routes/products.py
from flask import Blueprint, request, jsonify, session, abort
from sqlalchemy import or_
import decimal # 用於精確處理 Numeric 類型，避免浮點數誤差

# 從 db.py 匯入 db 實例，從 models.py 匯入 Product 模型
from db import db
from models import Product

# 初始化 Flask Blueprint
products_bp = Blueprint('products_bp', __name__)

def serialize_product(product):
    """
    將 Product 物件序列化為字典，以便轉換為 JSON。
    特別處理 price (Numeric 類型)，將其轉換為字串以確保精度並兼容 JSON。
    """
    return {
        'id': product.id,
        'name': product.name,
        'description': product.description,
        'price': str(product.price),  # 將 Numeric 類型轉換為字串，避免浮點數精度問題
        'stock': product.stock
    }

@products_bp.route('/products', methods=['GET'])
def list_products():
    """
    GET /products
    回傳所有商品的列表。
    """
    try:
        products = Product.query.all()
        return jsonify([serialize_product(p) for p in products]), 200
    except Exception as e:
        # 內部記錄詳細錯誤，但對客戶端回傳通用錯誤訊息，不洩漏內部細節
        print(f"Error listing products: {e}")
        return jsonify({"message": "An unexpected error occurred while retrieving products."}), 500

@products_bp.route('/products/search', methods=['GET'])
def search_products():
    """
    GET /products/search?q=關鍵字
    根據關鍵字搜尋商品，比對商品的 name 或 description。
    """
    query_param = request.args.get('q', '').strip()

    if not query_param:
        # 如果沒有提供搜尋關鍵字，則回傳空列表，符合「搜尋」的語義
        return jsonify([]), 200

    try:
        # 使用 SQLAlchemy ORM 的 ilike 進行大小寫不敏感搜尋
        # 關鍵字以參數方式帶入，嚴禁字串拼接，防止 SQL Injection
        search_pattern = f"%{query_param}%"
        products = Product.query.filter(
            or_(
                Product.name.ilike(search_pattern),
                Product.description.ilike(search_pattern)
            )
        ).all()
        return jsonify([serialize_product(p) for p in products]), 200
    except Exception as e:
        print(f"Error searching products: {e}")
        return jsonify({"message": "An unexpected error occurred during product search."}), 500

@products_bp.route('/products', methods=['POST'])
def add_product():
    """
    POST /products
    新增一筆商品。需要登入驗證。
    接收 JSON 格式的 name, description, price, stock。
    執行輸入驗證，並回傳新增的商品資訊。
    """
    # 安全要求：檢查 Flask session 是否有 user_id，沒有則回傳 401
    if 'user_id' not in session:
        return jsonify({"message": "Authentication required to add products."}), 401

    data = request.get_json()
    if not data:
        return jsonify({"message": "Invalid JSON data provided."}), 400

    name = data.get('name')
    description = data.get('description')
    price = data.get('price')
    stock = data.get('stock')

    # 輸入驗證 (Input Validation)
    errors = []

    # 驗證 name
    if not name or not isinstance(name, str) or not (1 <= len(name) <= 100):
        errors.append("Product name is required and must be a string between 1 and 100 characters.")

    # 驗證 price
    if price is None:
        errors.append("Product price is required.")
    else:
        try:
            # 將 price 轉換為 Decimal 類型進行精確驗證，避免浮點數誤差
            # 先轉為字串再轉 Decimal 是最安全的做法，以防 JSON 傳入的是浮點數
            price_decimal = decimal.Decimal(str(price))
            if price_decimal < 0:
                errors.append("Product price cannot be negative.")
            # 可選：如果需要限制小數位數，例如只允許兩位小數
            # if price_decimal.as_tuple().exponent < -2:
            #     errors.append("Product price can have at most two decimal places.")
        except (decimal.InvalidOperation, TypeError):
            errors.append("Product price must be a valid non-negative number.")

    # 驗證 stock
    if stock is None:
        errors.append("Product stock is required.")
    else:
        try:
            stock_int = int(stock)
            if stock_int < 0:
                errors.append("Product stock cannot be negative.")
        except (ValueError, TypeError):
            errors.append("Product stock must be a valid non-negative integer.")

    if errors:
        # 回傳通用錯誤訊息，不洩漏資料庫結構或堆疊細節
        return jsonify({"message": "Validation failed.", "errors": errors}), 400

    try:
        new_product = Product(
            name=name,
            description=description,
            price=price_decimal, # 使用已驗證的 Decimal 類型
            stock=stock_int      # 使用已驗證的整數類型
        )
        db.session.add(new_product)
        db.session.commit()
        return jsonify(serialize_product(new_product)), 201
    except Exception as e:
        db.session.rollback() # 發生錯誤時回滾事務
        print(f"Error adding product: {e}") # 內部記錄錯誤
        return jsonify({"message": "An unexpected error occurred while adding the product."}), 500
