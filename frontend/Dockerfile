# frontend/Dockerfile

# 使用 Nginx 1.27 的 Alpine 精簡版作為基底映像，固定版本標籤以確保穩定性。
FROM nginx:1.27-alpine

# 將前端靜態檔案複製到 Nginx 的預設網頁目錄。
# /usr/share/nginx/html 是 Nginx 在 Alpine 映像上的預設靜態檔案根目錄。
COPY . /usr/share/nginx/html

# 對外開放 80 埠，這是 Nginx 預設監聽的 HTTP 埠。
EXPOSE 80

# Nginx 容器啟動時會自動執行其預設的 CMD (通常是 `nginx -g 'daemon off;'`)，
# 無需在此 Dockerfile 中額外指定。
