"""
Vibe Coding 生成工具 — 讀取指定的 prompt 檔，送給 Gemini，將產出印出並另存。
用法：
  python generate.py                      → 讀 prompt.txt（預設）
  python generate.py prompts/02_auth.txt  → 讀指定的 prompt 檔
產出會依 prompt 檔名命名（例如 02_auth_output.txt），不會覆蓋前一個模組的結果。
這支程式不含任何 key（從 .env 讀），可安全進版控。
"""
import os
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import types

# 從 .env 載入設定
load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
model = os.environ.get("AI_MODEL", "gemini-2.5-flash")
temperature = float(os.environ.get("AI_TEMPERATURE", "0.2"))

if not api_key or api_key.startswith("your_"):
    raise SystemExit("讀不到有效的 GEMINI_API_KEY，請確認 .env 設定。")

# 要讀哪個 prompt 檔：可用命令列指定，否則預設 prompt.txt
prompt_file = sys.argv[1] if len(sys.argv) > 1 else "prompt.txt"

try:
    with open(prompt_file, "r", encoding="utf-8") as f:
        prompt = f.read().strip()
except FileNotFoundError:
    raise SystemExit(f"找不到 {prompt_file}，請確認檔名與路徑。")

if not prompt:
    raise SystemExit(f"{prompt_file} 是空的，請貼入 Prompt 內容。")

# 建立 client 並送出
client = genai.Client(api_key=api_key)

print(f"Prompt 檔：{prompt_file}")
print(f"模型：{model}，temperature：{temperature}")
print("送出 Prompt，生成中...\n")

response = client.models.generate_content(
    model=model,
    contents=prompt,
    config=types.GenerateContentConfig(temperature=temperature),
)

output = response.text or "(沒有回傳內容)"
print(output)

# 產出檔名依 prompt 檔名命名，避免覆蓋掉前一個模組的結果
base = os.path.splitext(os.path.basename(prompt_file))[0]
output_file = f"{base}_output.txt"
with open(output_file, "w", encoding="utf-8") as f:
    f.write(output)
print(f"\n（產出已另存為 {output_file}）")