# ===== Semgrep 會抓 =====

import os

user = input("Enter something: ")

# ❌ 1. Code injection (Semgrep 一定抓)
eval(user)

# ❌ 2. SQL Injection (Semgrep 一定抓)
query = "SELECT * FROM users WHERE name='" + user + "'"
print(query)

# ===== Gitleaks 會抓 =====

# ❌ 3. Hardcoded secret (Gitleaks 會抓)
API_KEY = "sk_test_123456789abcdef"

# ❌ 4. AWS style secret (Gitleaks 會抓更穩)
AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
