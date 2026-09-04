import os

# Gitleaks 測試：故意放一個假的 API Key
API_KEY = "sk_test_123456789abcdef"

# Semgrep 測試：故意使用危險的 eval()
user = input("Enter something: ")
eval(user)

print("Test completed")
