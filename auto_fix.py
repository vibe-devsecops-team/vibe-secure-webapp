"""
auto_fix.py — 讀取 Semgrep 的 JSON 掃描報告，呼叫 Gemini 針對每筆問題產生修正，
並在通過語法驗證後寫回原始檔案。

設計原則：
- 只改 Semgrep 報告指定的行號範圍，不動其他程式碼
- 同一檔案有多筆問題時，由後往前處理，避免行號互相影響
- 修正後必須通過 ast.parse 語法驗證，否則捨棄、交給人工
- AI 判斷無法在保留功能前提下安全修復時（AUTOFIX_SKIP），誠實跳過
- 只處理 .py 檔；其餘類型記錄後交給人工
- 機器只「提案」，合併仍須經 Security Gate 與人工審查
"""
import os
import json
import sys
import time
import re
import ast
import logging
from dotenv import load_dotenv
from google import genai
from google.genai import types

# 配置日誌，方便追蹤腳本執行狀況
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def load_config() -> tuple:
    """
    從 .env 或環境變數載入 Gemini API 金鑰、模型名稱和溫度，並建立 client。
    金鑰一律從環境變數讀取，不可寫死。
    """
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    ai_model = os.getenv("AI_MODEL", "gemini-2.5-flash")
    ai_temperature = float(os.getenv("AI_TEMPERATURE", "0.2"))

    if not api_key or api_key.startswith("your_"):
        logging.error("錯誤：讀不到有效的 GEMINI_API_KEY，請確認 .env 或環境變數設定。")
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


def call_gemini_api(client, prompt: str, model_name: str, temperature: float,
                    max_retries: int = 3) -> str:
    """
    呼叫 Gemini API 取得修正後的程式碼，並剝除可能的 markdown 標記。
    針對伺服器端的暫時性錯誤（如 503 忙線）會自動重試，等待時間遞增；
    對不會因重試而改善的錯誤（如金鑰無效）則立即放棄。
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
            is_transient = any(
                code in error_text
                for code in ["503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED"]
            )

            if not is_transient:
                logging.error(f"呼叫 Gemini API 時發生不可重試的錯誤: {e}")
                return ""

            if attempt == max_retries:
                logging.error(f"呼叫 Gemini API 時發生錯誤，已重試 {max_retries} 次仍失敗: {e}")
                return ""

            wait_seconds = 2 ** attempt  # 第1次等2秒、第2次等4秒、第3次等8秒
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


def read_semgrep_report(report_path: str) -> dict:
    """讀取 Semgrep JSON 掃描報告。"""
    if not os.path.exists(report_path):
        logging.info(f"Semgrep 報告 '{report_path}' 不存在。無需修正，腳本結束。")
        return {"results": []}

    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logging.error(f"從 '{report_path}' 解析 JSON 時發生錯誤: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"讀取 Semgrep 報告 '{report_path}' 時發生錯誤: {e}")
        sys.exit(1)


def create_gemini_prompt(check_id: str, message: str, context_before: list,
                         problem_lines: list, context_after: list) -> str:
    """
    建構給 Gemini API 的 Prompt。
    把「要被取代的原始程式碼」與「僅供參考的前後文」明確分開，
    避免模型把整段上下文一起輸出。
    """
    before_str = "".join(context_before)
    problem_str = "".join(problem_lines)
    after_str = "".join(context_after)

    prompt = f"""你是一位資深的 Python 資安工程師。你的任務是修正 Semgrep 識別出的資安問題。
本專案技術棧：Python、Flask、SQLAlchemy、PostgreSQL（psycopg2，SQL 參數佔位符為 %s）。

【問題資訊】
- 規則 ID：{check_id}
- 問題描述：{message}

【前文（僅供理解語境，禁止輸出）】
{before_str}
【需要修正的原始程式碼（你的輸出會整段取代這一段）】
{problem_str}
【後文（僅供理解語境，禁止輸出）】
{after_str}
【輸出規則】
1. 只輸出「用來取代【需要修正的原始程式碼】的新程式碼」，絕對不可以輸出前文或後文。
2. 只輸出純程式碼，不要任何解釋、不要 Markdown 的 ``` 標記。
3. 保持與原始程式碼相同的縮排層級。
4. 修正必須保留原始程式碼的功能意圖，只能將「不安全的實作方式」換成「安全的實作方式」，不可以用刪除功能邏輯的方式來規避問題。「保留功能意圖」不等於「保持完全相同的資料型別」，若安全寫法在這一段內就能完成調整（例如把單一字串改成「SQL 樣板與參數」的組合），這是正常必要的修正。
5. 你的輸出只能取代上述區段，無法修改檔案的其他位置。若修正需要新的 import，請在輸出內以獨立一行寫入（與該區段同縮排層級），不要假設可以改動檔案開頭。
6. 若你評估這個問題無法在上述限制內、且「保留功能」的前提下安全修復，請只輸出一行註解：# AUTOFIX_SKIP: 原因
"""
    return prompt


def main():
    semgrep_report_path = "semgrep-results.json"

    report = read_semgrep_report(semgrep_report_path)
    results = report.get("results", [])

    # 沒有任何發現時直接結束，不需要金鑰
    if not results:
        logging.info("Semgrep 報告中沒有發現任何問題。無需修正。")
        sys.exit(0)

    client, ai_model, ai_temperature = load_config()

    # 將發現的問題按檔案路徑分組，方便對同一檔案由後往前處理
    findings_by_file = {}
    for res in results:
        findings_by_file.setdefault(res["path"], []).append(res)

    fixed_files_summary = set()
    fixed_rules_summary = set()
    skipped_for_human = []  # 機器沒處理、需要人工看的項目：(檔案, 原因)

    for file_path, findings in findings_by_file.items():
        # 只處理 Python 檔（語法驗證用 ast.parse，無法驗證其他類型）
        if not file_path.endswith(".py"):
            logging.info(f"跳過非 Python 檔案（交由人工處理）: {file_path}")
            for f in findings:
                skipped_for_human.append((file_path, f"{f['check_id']}：非 Python 檔案，不支援自動修復"))
            continue

        logging.info(f"正在處理檔案中的問題: {file_path}")

        # 同一檔案多筆問題：由檔案最後一筆往前處理，避免行號替換後互相影響
        findings.sort(key=lambda x: x["start"]["line"], reverse=True)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                current_file_lines = f.readlines()
            original_file_content = "".join(current_file_lines)
        except FileNotFoundError:
            logging.error(f"跳過檔案 '{file_path}': 檔案不存在。")
            for f in findings:
                skipped_for_human.append((file_path, f"{f['check_id']}：檔案不存在"))
            continue
        except Exception as e:
            logging.error(f"跳過檔案 '{file_path}': 讀取檔案時發生錯誤: {e}")
            for f in findings:
                skipped_for_human.append((file_path, f"{f['check_id']}：讀取檔案失敗"))
            continue

        for finding in findings:
            start_line = finding["start"]["line"]  # 1-indexed
            end_line = finding["end"]["line"]      # 1-indexed
            check_id = finding["check_id"]
            message = finding["extra"]["message"]

            logging.info(f"  - 嘗試修正規則 '{check_id}'，位於行號 {start_line}-{end_line}")

            start_idx_0 = start_line - 1
            end_idx_0 = end_line - 1

            # 取問題行前後各 5 行作為「僅供參考」的上下文
            context_lines_count = 5
            context_start_idx = max(0, start_idx_0 - context_lines_count)
            context_end_idx = min(len(current_file_lines), end_idx_0 + context_lines_count + 1)

            context_before = current_file_lines[context_start_idx:start_idx_0]
            problem_lines = current_file_lines[start_idx_0:end_idx_0 + 1]
            context_after = current_file_lines[end_idx_0 + 1:context_end_idx]

            prompt = create_gemini_prompt(check_id, message, context_before, problem_lines, context_after)
            fixed_code_raw = call_gemini_api(client, prompt, ai_model, ai_temperature)

            if not fixed_code_raw:
                logging.warning(f"    Gemini 未返回修正建議，跳過規則 '{check_id}' 在 '{file_path}' 的修正。")
                skipped_for_human.append((file_path, f"{check_id}：Gemini 未返回修正內容"))
                continue

            # AI 誠實表示無法在保留功能前提下安全修復 → 記錄原因並跳過
            if "AUTOFIX_SKIP" in fixed_code_raw:
                if "AUTOFIX_SKIP:" in fixed_code_raw:
                    skip_reason = fixed_code_raw.split("AUTOFIX_SKIP:", 1)[-1].strip()
                else:
                    skip_reason = "未提供原因"
                logging.info(f"    Gemini 判斷此問題無法在保留功能的前提下安全修復，跳過規則 '{check_id}'：{skip_reason}")
                skipped_for_human.append((file_path, f"{check_id}：{skip_reason}"))
                continue

            # Gemini 常回傳去除縮排的片段，不能假設它會照抄原縮排，
            # 一律以原始問題行的縮排為準補回去
            original_first_line = current_file_lines[start_idx_0]
            indent = original_first_line[:len(original_first_line) - len(original_first_line.lstrip())]

            fixed_code_lines = []
            for i, line in enumerate(fixed_code_raw.splitlines()):
                if line.strip() == "":
                    fixed_code_lines.append("\n")
                elif i == 0:
                    fixed_code_lines.append(indent + line.strip() + "\n")
                else:
                    # 後續行：Gemini 有給自己的縮排就保留，否則套用原縮排
                    fixed_code_lines.append(line + "\n" if line.startswith(" ") else indent + line + "\n")

            # 原問題行若是檔案最後一行且沒有換行符，修正後也維持一致
            if not current_file_lines[end_idx_0].endswith('\n') and fixed_code_lines and fixed_code_lines[-1].endswith('\n'):
                fixed_code_lines[-1] = fixed_code_lines[-1].rstrip('\n')

            # 先在「候選版本」上套用，驗證語法合法後才真正採用，
            # 避免 Gemini 回傳不乾淨的內容導致檔案壞掉
            candidate_lines = current_file_lines.copy()
            candidate_lines[start_idx_0:end_idx_0 + 1] = fixed_code_lines
            candidate_content = "".join(candidate_lines)

            is_valid, syntax_err = validate_python(candidate_content)
            if not is_valid:
                logging.warning(f"    修正後語法不合法（{syntax_err}），捨棄此筆修正：'{check_id}' in '{file_path}'，交由人工處理。")
                logging.warning(f"    Gemini 實際回傳內容：\n---\n{fixed_code_raw}\n---")
                skipped_for_human.append((file_path, f"{check_id}：修正後語法不合法"))
                continue

            current_file_lines = candidate_lines
            fixed_files_summary.add(file_path)
            fixed_rules_summary.add(check_id)
            logging.info(f"    成功為規則 '{check_id}' 生成並應用修正。")

        # 處理完該檔案所有發現後，有變化才寫回
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
    logging.info("--- 修正摘要 ---")
    if fixed_files_summary:
        logging.info(f"總共修正了 {len(fixed_files_summary)} 個檔案:")
        for f in sorted(fixed_files_summary):
            logging.info(f"  - {f}")
        logging.info(f"總共應用了 {len(fixed_rules_summary)} 條規則的修正:")
        for r in sorted(fixed_rules_summary):
            logging.info(f"  - {r}")
    else:
        logging.info("沒有任何檔案被修正。")

    if skipped_for_human:
        logging.info("--- 需人工處理 ---")
        for path, reason in skipped_for_human:
            logging.info(f"  - {path}：{reason}")


if __name__ == "__main__":
    main()
