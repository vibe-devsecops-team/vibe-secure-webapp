import os
from flask_sqlalchemy import SQLAlchemy

# 初始化 SQLAlchemy 實例
# 這個實例將在 Flask 應用程式初始化時被配置
db = SQLAlchemy()

def get_database_uri() -> str:
    """
    從環境變數組裝 PostgreSQL 資料庫連線 URI。
    嚴格要求所有連線資訊必須透過環境變數提供，禁止硬編碼。
    """
    # 從環境變數讀取資料庫連線資訊
    # 如果環境變數不存在，則拋出 ValueError，確保機密資訊不會被遺漏
    db_user = os.getenv('POSTGRES_USER')
    db_password = os.getenv('POSTGRES_PASSWORD')
    db_host = os.getenv('POSTGRES_HOST')
    db_port = os.getenv('POSTGRES_PORT', '5432') # 提供預設 port，但仍建議明確設定
    db_name = os.getenv('POSTGRES_DB')

    # 檢查所有必要的環境變數是否都已設定
    if not all([db_user, db_password, db_host, db_name]):
        missing_vars = [
            var_name for var_name, var_value in {
                'POSTGRES_USER': db_user,
                'POSTGRES_PASSWORD': db_password,
                'POSTGRES_HOST': db_host,
                'POSTGRES_DB': db_name
            }.items() if not var_value
        ]
        raise ValueError(
            f"以下必要的資料庫環境變數未設定：{', '.join(missing_vars)}。 "
            "請確保 POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_DB 已正確設定。"
        )

    # 組裝 PostgreSQL 連線字串
    # 格式：postgresql://user:password@host:port/dbname
    database_uri = (
        f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    )
    
    # 為了安全考量，不在此處或任何 log 中印出連線字串，
    # 即使是部分資訊也應避免，以防洩露。
    return database_uri
