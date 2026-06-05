from db import db 

class User(db.Model):
    """
    定義 User 模型，對應資料庫中的 'users' 資料表。
    儲存使用者帳戶資訊，密碼欄位僅儲存雜湊值，確保安全性。
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    # password_hash 欄位只儲存雜湊後的密碼，絕不儲存明文密碼。
    # 雜湊邏輯將在後續的認證模組中實作。
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())

    def __repr__(self):
        return f"<User {self.username}>"

class Product(db.Model):
    """
    定義 Product 模型，對應資料庫中的 'products' 資料表。
    儲存商品資訊。
    """
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    # price 使用 Numeric 類型，確保精確度，例如貨幣值。
    price = db.Column(db.Numeric(10, 2), nullable=True)
    stock = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=db.func.now())

    def __repr__(self):
        return f"<Product {self.name}>"
