from docx import Document

doc_path = r"d:\pythonproject\2026feishubisai\给 AI 发通行证：构建 Agent 身份与权限系统.docx"
doc = Document(doc_path)

print("=== Word文档需求内容 ===")
for para in doc.paragraphs:
    if para.text.strip():
        print(para.text)
        print("-" * 50)
