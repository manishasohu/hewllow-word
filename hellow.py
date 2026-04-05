import base64

data = "3d2922646c726f57206f6c6c65482228746e697270"
data = bytes.fromhex(data).decode()[::-1]
exec(base64.b64decode(data).decode())
