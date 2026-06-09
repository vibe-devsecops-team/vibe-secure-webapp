# backend/Dockerfile

# 使用 Python 3.12 的精簡版作為基底映像，固定版本標籤以確保穩定性和可重現性
FROM python:3.12-slim

# 設定容器內的工作目錄。所有後端程式碼將會放在此目錄下。
WORKDIR /app

# 建立一個非 root 使用者和群組，以提高安全性。
# -u 1001: 指定使用者 ID (通常建議使用大於 1000 的 ID)
# -g 1001: 指定群組 ID
# --system: 建立系統使用者，不建立家目錄
# appuser: 使用者名稱
RUN groupadd --system appgroup && useradd --system --create-home --uid 1001 --gid appgroup appuser

# 將 requirements.txt 複製到工作目錄，並安裝依賴套件。
# 這樣做可以利用 Docker 的快取機制：如果 requirements.txt 沒有改變，就不會重新安裝套件。
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 將專案的其餘程式碼複製到工作目錄。
# 注意：這裡會將 backend/ 目錄下的所有內容複製到 /app。
COPY . .

# 更改工作目錄及其內容的擁有者為非 root 使用者，確保應用程式可以讀寫檔案。
RUN chown -R appuser:appgroup /app

# 切換到非 root 使用者執行應用程式，降低潛在的安全風險。
USER appuser

# 對外開放 5000 埠，這是 Gunicorn 預設監聽的埠。
EXPOSE 5000

# 使用 Gunicorn 啟動 Flask 應用程式。
# -b 0.0.0.0:5000: 綁定到所有網路介面的 5000 埠，允許外部連線。
# app:app: 指定 Flask 應用程式的進入點 (app.py 檔案中的 app 變數)。
CMD ["gunicorn", "-b", "0.0.0.0:5000", "--access-logfile", "-", "app:app"]
