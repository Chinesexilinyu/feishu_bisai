import base64
import gzip
import json

with open(r"d:\pythonproject\2026feishubisai\番茄小说数据测试管理.base", 'r', encoding='utf-8') as f:
    content = f.read()

# 提取gzipSnapshot内容
data = json.loads(content)
gzip_data = base64.b64decode(data["gzipSnapshot"])
decompressed = gzip.decompress(gzip_data)

print("=== 番茄小说数据结构 ===")
print(decompressed.decode('utf-8'))
