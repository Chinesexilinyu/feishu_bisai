"""飞书文档操作助手 - 独立模块，仅提供docx文档创建能力，不暴露bitable数据访问"""
import yaml
import os
import requests

def _load_feishu_credentials():
    """加载飞书凭证"""
    secrets_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "config", "secrets.yaml"
    )
    with open(secrets_path, 'r', encoding='utf-8') as f:
        secrets = yaml.safe_load(f)
        feishu = secrets.get("feishu", {})
        return feishu["app_id"], feishu["app_secret"]

def _get_tenant_access_token():
    app_id, app_secret = _load_feishu_credentials()
    token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    token_payload = {"app_id": app_id, "app_secret": app_secret}
    token_resp = requests.post(token_url, json=token_payload, timeout=10)
    return token_resp.json()["tenant_access_token"]

def create_doc(title: str, content: str) -> str:
    """创建飞书文档并写入内容（纯docx权限，不涉及bitable）"""
    url = "https://open.feishu.cn/open-apis/docx/v1/documents"
    headers = {
        "Authorization": f"Bearer {_get_tenant_access_token()}",
        "Content-Type": "application/json"
    }

    body = {"title": title}
    resp = requests.post(url, headers=headers, json=body, timeout=10)
    resp_json = resp.json()

    if resp_json.get("code") != 0:
        raise Exception(f"创建文档失败: {resp_json.get('msg')}, 错误码={resp_json.get('code')}")

    document_id = resp_json["data"]["document"]["document_id"]
    print(f"[INFO] 文档创建成功, document_id={document_id}")

    blocks_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/children"

    HEADING_TYPE_MAP = {
        1: (3, "heading1"),
        2: (4, "heading2"),
        3: (5, "heading3"),
        4: (6, "heading4"),
    }

    lines = content.strip().split("\n")
    all_blocks = []
    for line in lines:
        line = line.strip()
        if not line:
            continue

        heading_level = 0
        for ch in line:
            if ch == '#':
                heading_level += 1
            else:
                break

        if heading_level >= 1 and heading_level <= 4 and line[heading_level:heading_level+1] == ' ':
            content_text = line[heading_level+1:].strip()
            bt, field_name = HEADING_TYPE_MAP.get(heading_level, (2, "text"))
            block = {
                "block_type": bt,
                field_name: {
                    "elements": [{"text_run": {"content": content_text}}],
                    "style": {}
                }
            }
            all_blocks.append(block)
        elif line.startswith("|") and line.endswith("|"):
            block = {
                "block_type": 2,
                "text": {
                    "elements": [{"text_run": {"content": line}}],
                    "style": {}
                }
            }
            all_blocks.append(block)
        elif line.startswith("---") or line.startswith("***"):
            continue
        else:
            block = {
                "block_type": 2,
                "text": {
                    "elements": [{"text_run": {"content": line}}],
                    "style": {}
                }
            }
            all_blocks.append(block)

    batch_size = 50
    total_batches = (len(all_blocks) + batch_size - 1) // batch_size
    success_count = 0
    for batch_idx in range(total_batches):
        i = batch_idx * batch_size
        batch_blocks = all_blocks[i:i+batch_size]
        blocks_body = {
            "children": batch_blocks,
            "index": 0,
        }
        resp = requests.post(blocks_url, headers=headers, json=blocks_body, timeout=60)
        resp_json = resp.json()
        resp_code = resp_json.get("code", -1)
        if resp_code == 0:
            success_count += 1
        else:
            print(f"[WARN] 第{batch_idx + 1}批内容写入失败: code={resp_code}, msg={resp_json.get('msg')}")

    print(f"[INFO] 文档内容写入完成: {success_count}/{total_batches} 批次成功, 共{len(all_blocks)}个块")
    return f"https://feishu.cn/docx/{document_id}"
