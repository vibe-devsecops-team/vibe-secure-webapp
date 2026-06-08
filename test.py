API_KEY = "safe_value"

print("test")
user = input()

query = f"SELECT * FROM users WHERE name='{user}'"

print(query)
