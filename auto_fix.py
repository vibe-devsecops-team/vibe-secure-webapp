import time
import os
import json
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import types
import logging
import re
import ast

# 配置日誌，方便追蹤腳本執行狀況
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_config() -> tuple:
    """
    從 .env 檔案載入 Gemini API 金鑰、模型名稱和溫度，並建立 client。
    確保 API 金鑰從環境變數讀取，不可寫死。
    """
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    ai_model = os.getenv("AI_MODEL", "gemini-2.5-flash")
    ai_temperature = float(os.getenv("AI_TEMPERATURE", "0.2"))

    if not api_key or api_key.startswith("your_"):
        logging.error("錯誤：讀不到有效的 GEMINI_API_KEY，請確認 .env 設定。")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    logging.info(f"Gemini API 已配置。模型: {ai_model}, 溫度: {ai_temperature}")
    return client, ai_model, ai_temperature

def strip_markdown_fence(text: str) -> str:
    """去除 Gemini 回傳內容中可能殘留的 markdown 程式碼區塊標記。"""
    text = text.strip()
    text = re.sub(r'^```[a-zA-Z]*\n?', '', text)
    text = re.sub(r'\n?```$', '', text)
    return text.strip()

#與Gemini進行互動

def call_gemini_api(client, prompt: str, model_name: str, temperature: float,
                     max_retries: int = 3) -> str:
    """
    呼叫 Gemini API 取得修正後的程式碼，並剝除可能的 markdown 標記。
    針對伺服器端的暫時性錯誤（如 503 忙線）會自動重試，採遞增等待時間；
    但對於不會因重試而改善的錯誤（如金鑰無效）則立即放棄，不做無意義的重試。
    """
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=temperature),
            )
            raw = (response.text or "").strip()
            if not raw:
                logging.warning("Gemini API 對於給定提示未返回任何內容。")
                return ""
            return strip_markdown_fence(raw)

        except Exception as e:
            error_text = str(e)
            # 只有明確判斷為「暫時性」的錯誤才值得重試；
            # 其餘一律視為不會因重試而改善，直接放棄。
            is_transient = any(code in error_text for code in ["503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED"])

            if not is_transient:
                logging.error(f"呼叫 Gemini API 時發生不可重試的錯誤: {e}")
                return ""

            if attempt == max_retries:
                logging.error(f"呼叫 Gemini API 時發生錯誤，已重試 {max_retries} 次仍失敗: {e}")
                return ""

            wait_seconds = 2 ** attempt  # 遞增等待：第1次等2秒、第2次等4秒、第3次等8秒
            logging.warning(f"Gemini API 暫時性錯誤（第 {attempt}/{max_retries} 次嘗試）：{e}")
            logging.warning(f"等待 {wait_seconds} 秒後重試...")
            time.sleep(wait_seconds)

    return ""

def validate_python(code: str):
    """檢查一段程式碼是否為語法合法的 Python，回傳 (是否合法, 錯誤原因)。"""
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, str(e)

# --- Semgrep 報告處理 ---
def read_semgrep_report(report_path: str) -> dict:
    """
    讀取 Semgrep JSON 掃描報告。
    """
    if not os.path.exists(report_path):
        logging.info(f"Semgrep 報告 '{report_path}' 不存在。無需修正，腳本結束。")
        return {"results": []}

    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            report = json.load(f)
        return report
    except json.JSONDecodeError as e:
        logging.error(f"從 '{report_path}' 解析 JSON 時發生錯誤: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"讀取 Semgrep 報告 '{report_path}' 時發生錯誤: {e}")
        sys.exit(1)

def create_gemini_prompt(check_id: str, message: str, context_code: list[str], problem_start_line: int, problem_end_line: int) -> str:
    """
    建構給 Gemini API 的 Prompt。
    明確要求只回傳修正後的程式碼區塊本身，不要任何說明文字、不要 markdown 的 ``` 標記。
    """
    # 將上下文程式碼列表拼接成單一字串，保持原始換行
    context_str = "".join(context_code)

    prompt = f"""你是一位資深的 Python 資安工程師。你的任務是修正 Semgrep 識別出的資安漏洞或程式碼品質問題。

**問題詳情:**
- **規則 ID:** {check_id}
- **問題描述:** {message}
- **有問題的行號 (在提供的上下文程式碼中，為 1-indexed):** 第 {problem_start_line} 行到第 {problem_end_line} 行

**上下文程式碼 (包含有問題的行及其前後程式碼):**
```python
{context_str.strip()}
```

**重要指示:**
1.  **只回傳修正後的 Python 程式碼區塊本身。**
2.  **不要包含任何解釋、註解或 Markdown 的 ``` 標記。**
3.  **修正範圍必須僅限於有問題的行 ({problem_start_line} 到 {problem_end_line})。**
4.  **不可更動上下文其餘程式碼的邏輯或結構。**
5.  **確保修正後的程式碼是語法正確的 Python。**
6.  **盡可能保持原始縮排。**
7.  **修正必須保留原始程式碼的功能意圖，只能將「不安全的實作方式」換成「安全的實作方式」，不可以用刪除功能邏輯的方式來規避安全問題。**
    **例如：若原始程式碼用 eval() 將輸入解析成資料，正確做法是改用 ast.literal_eval() 等安全方式繼續完成「解析」這件事；錯誤做法是直接刪除解析邏輯、讓函式不再做任何處理（例如直接回傳原始輸入）。**
    **如果你評估這個問題無法在「保留功能」的前提下安全修復，請回傳原始程式碼不做任何更動，並在程式碼最後一行以註解寫明：`# AUTOFIX_SKIP: 原因`，而不是用刪除功能的方式勉強通過。**


def fixed_function():
    print("This is fixed code.")
    return True
"""
    return prompt

def main():
    semgrep_report_path = "semgrep-results.json"
    client, ai_model, ai_temperature = load_config()

    report = read_semgrep_report(semgrep_report_path)
    results = report.get("results", [])

    if not results:
        logging.info("Semgrep 報告中沒有發現任何問題。無需修正。")
        sys.exit(0)

    # 將發現的問題按檔案路徑分組
    # 這樣可以針對單一檔案的所有問題進行處理，並應用「由後往前」的修正策略。
    findings_by_file = {}
    for res in results:
        file_path = res["path"]
        if file_path not in findings_by_file:
            findings_by_file[file_path] = []
        findings_by_file[file_path].append(res)

    fixed_files_summary = set() # 記錄被修正的檔案
    fixed_rules_summary = set() # 記錄被修正的規則

    for file_path, findings in findings_by_file.items():
        logging.info(f"正在處理檔案中的問題: {file_path}")

        # 對於同一個檔案的多筆發現，必須由檔案的最後一筆問題往前處理。
        # 這樣可以避免行號替換後互相影響，確保每次替換的行號都是準確的。
        findings.sort(key=lambda x: x["start"]["line"], reverse=True)

        # 讀取整個檔案內容到記憶體中，作為一個行列表
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                current_file_lines = f.readlines()
            original_file_content = "".join(current_file_lines) # 儲存原始內容用於比較
        except FileNotFoundError:
            logging.error(f"跳過檔案 '{file_path}': 檔案不存在。")
            continue
        except Exception as e:
            logging.error(f"跳過檔案 '{file_path}': 讀取檔案時發生錯誤: {e}")
            continue

        for finding in findings:
            start_line = finding["start"]["line"] # Semgrep 報告中的起始行號 (1-indexed)
            end_line = finding["end"]["line"]     # Semgrep 報告中的結束行號 (1-indexed)
            check_id = finding["check_id"]
            message = finding["extra"]["message"]

            logging.info(f"  - 嘗試修正規則 '{check_id}'，位於行號 {start_line}-{end_line}")

            # 將 1-indexed 行號轉換為 0-indexed 列表索引
            start_idx_0 = start_line - 1
            end_idx_0 = end_line - 1

            # 提取問題行號前後各 5 行作為上下文
            context_lines_count = 5
            context_start_idx = max(0, start_idx_0 - context_lines_count)
            context_end_idx = min(len(current_file_lines), end_idx_0 + context_lines_count + 1) # +1 因為 slice 結束是排他的

            # 從當前記憶體中的檔案內容提取上下文程式碼
            context_code_for_prompt = current_file_lines[context_start_idx:context_end_idx]

            # 建構給 Gemini 的 Prompt
            prompt = create_gemini_prompt(check_id, message, context_code_for_prompt, start_line, end_line)
            
            # 呼叫 Gemini API 取得修正後的程式碼
            fixed_code_raw = call_gemini_api(client, prompt, ai_model, ai_temperature)

            if not fixed_code_raw:
                logging.warning(f"    Gemini 未返回修正建議，或返回空內容，跳過規則 '{check_id}' 在 '{file_path}' 的修正。")
                continue
            if "AUTOFIX_SKIP" in fixed_code_raw:
                skip_reason = fixed_code_raw.split("AUTOFIX_SKIP:", 1)[-1].strip() if "AUTOFIX_SKIP:" in fixed_code_raw else "未提供原因"
                logging.info(f"    Gemini 判斷此問題無法在保留功能的前提下安全修復，跳過規則 '{check_id}'：{skip_reason}")
                continue
            # 取得原始問題行的縮排（以第一行的前導空白為準），
            # 因為 Gemini 常會回傳「去除縮排」的程式碼片段，需要程式自己補回去，
            # 不能假設 AI 每次都會照抄原本的縮排。
            original_first_line = current_file_lines[start_idx_0]
            indent = original_first_line[:len(original_first_line) - len(original_first_line.lstrip())]

            fixed_lines_raw = fixed_code_raw.splitlines()
            fixed_code_lines = []
            for i, line in enumerate(fixed_lines_raw):
                if line.strip() == "":
                    fixed_code_lines.append("\n")
                elif i == 0:
                    # 第一行直接套用原始縮排
                    fixed_code_lines.append(indent + line.strip() + "\n")
                else:
                    # 後續行：如果 Gemini 有給自己的相對縮排就保留，否則套用同一層級
                    fixed_code_lines.append(indent + line + "\n" if not line.startswith(" ") else line + "\n")

            # 處理最後一行可能沒有換行符的情況，如果原始問題行最後一行沒有換行符，則修正後也應保持
            if not current_file_lines[end_idx_0].endswith('\n') and fixed_code_lines and fixed_code_lines[-1].endswith('\n'):
                fixed_code_lines[-1] = fixed_code_lines[-1].rstrip('\n')
             # 先在「候選版本」上套用這次修改，驗證語法合法後才真正寫入
             # 避免 Gemini 回傳不乾淨的內容（例如連上下文一起吐回來）導致檔案壞掉。
            candidate_lines = current_file_lines.copy()
            candidate_lines[start_idx_0 : end_idx_0 + 1] = fixed_code_lines
            candidate_content = "".join(candidate_lines)

            is_valid, syntax_err = validate_python(candidate_content)
            if not is_valid:
                logging.warning(f"    修正後語法不合法（{syntax_err}），捨棄此筆修正：'{check_id}' in '{file_path}'，交由人工處理。")
                logging.warning(f"    Gemini 實際回傳內容：\n---\n{fixed_code_raw}\n---")
                continue

            current_file_lines = candidate_lines
            fixed_files_summary.add(file_path)
            fixed_rules_summary.add(check_id)
            logging.info(f"    成功為規則 '{check_id}' 生成並應用修正。")

        # 處理完該檔案的所有發現後，將修改後的內容寫回檔案
        modified_file_content = "".join(current_file_lines)
        if modified_file_content != original_file_content:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(current_file_lines)
                logging.info(f"成功將修正寫回檔案: '{file_path}'。")
            except Exception as e:
                logging.error(f"寫入修正到檔案 '{file_path}' 時發生錯誤: {e}")
        else:
            logging.info(f"檔案 '{file_path}' 處理完所有問題後，內容未發生變化。")

    # --- 輸出摘要 ---
    logging.info("\n--- 修正摘要 ---")
    if fixed_files_summary:
        logging.info(f"總共修正了 {len(fixed_files_summary)} 個檔案:")
        for f in sorted(list(fixed_files_summary)):
            logging.info(f"  - {f}")
        logging.info(f"總共應用了 {len(fixed_rules_summary)} 條規則的修正:")
        for r in sorted(list(fixed_rules_summary)):
            logging.info(f"  - {r}")
    else:
        logging.info("沒有任何檔案被修正。")

if __name__ == "__main__":
    main()
