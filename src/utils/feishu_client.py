import yaml
import os
import time
import requests
from urllib.parse import urlparse

class FeishuClient:
    _instance = None
    _initialized = False
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, table_name: str = "default"):
        if FeishuClient._initialized:
            return
        
        # 加载配置文件获取 app_id 和 app_secret
        secrets_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config", "secrets.yaml"
        )
        with open(secrets_path, 'r', encoding='utf-8') as f:
            secrets = yaml.safe_load(f)
            feishu_secrets = secrets.get("feishu", {})
            self.app_id = feishu_secrets.get("app_id", "")
            self.app_secret = feishu_secrets.get("app_secret", "")
            self.target_url = feishu_secrets.get("target_feishu_url", 
                "https://jcneyh7qlo8i.feishu.cn/wiki/CRunwszdyizFEmkit1Xc1tsGnLd?table=blk6XVlzM2xVXHzl")
        
        if not self.app_id or not self.app_secret:
            raise Exception("请配置config/secrets.yaml中的飞书app_id和app_secret")
        
        # 自动解析真实的 bitable app_token 和 table_id
        self.bitable_app_token = None
        self.bitable_table_id = None
        self._resolve_bitable_params()
        
        self.current_table = table_name
        FeishuClient._initialized = True
    
    def _resolve_bitable_params(self):
        """从飞书链接自动解析多维表格的真实 app_token 和 table_id"""
        # 从 URL 提取 document_id 和 block_id
        parsed = urlparse(self.target_url)
        path_parts = parsed.path.split("/")
        document_id = path_parts[-1].split("?")[0] if path_parts else ""
        
        from urllib.parse import parse_qs
        query_params = parse_qs(parsed.query)
        block_id = query_params.get("table", [""])[0]
        
        print(f"[INFO] 解析飞书链接: document_id={document_id}, block_id={block_id}")
        
        # 使用飞书 SDK 获取 tenant_access_token
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        token_payload = {"app_id": self.app_id, "app_secret": self.app_secret}
        token_resp = requests.post(token_url, json=token_payload, timeout=10)
        if token_resp.json().get("code") != 0:
            raise Exception(f"获取Token失败: {token_resp.json().get('msg')}")
        access_token = token_resp.json()["tenant_access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # 步骤1：尝试用 Wiki API 获取节点信息
        wiki_url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token={document_id}"
        resp = requests.get(wiki_url, headers=headers, timeout=10)
        resp_json = resp.json()
        
        space_id = None
        if resp_json.get("code") == 0:
            node_data = resp_json["data"]["node"]
            space_id = node_data.get("space_id", "")
            obj_token = node_data.get("obj_token", "")
            obj_type = node_data.get("obj_type", "")
            print(f"[INFO] Wiki节点: space_id={space_id}, obj_type={obj_type}, obj_token={obj_token}")
            document_id = obj_token  # 真实文档 token
            
            if obj_type == "bitable":
                # 多维表格本身
                self.bitable_app_token = obj_token
                print(f"[INFO] 找到独立多维表格: app_token={obj_token}")
        
        if not space_id:
            raise Exception("无法获取Wiki空间信息，请确认应用已开通 wiki:space:readonly 权限")
        
        # 步骤2：获取文档块列表，找到 bitable 块
        if not self.bitable_app_token:
            blocks_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks?page_size=500"
            resp = requests.get(blocks_url, headers=headers, timeout=10)
            resp_json = resp.json()
            
            if resp_json.get("code") == 0:
                blocks = resp_json["data"]["items"]
                for block in blocks:
                    block_type = block.get("block_type")
                    if block_type == 19:  # bitable 类型
                        self.bitable_app_token = block["bitable"]["token"]
                        print(f"[INFO] 找到内嵌多维表格: app_token={self.bitable_app_token}")
                        break
                if not self.bitable_app_token:
                    raise Exception("未在文档中找到内嵌多维表格，请确认链接中存在多维表格")
            else:
                print(f"[WARN] 获取文档块列表失败: {resp_json.get('msg')}")
                # 尝试直接用 document_id 作为 app_token
                self.bitable_app_token = document_id
                print(f"[INFO] 尝试使用 document_id 作为 app_token: {self.bitable_app_token}")
        
        # 步骤3：获取表格列表，取第一个默认表格
        tables_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.bitable_app_token}/tables?page_size=100"
        resp = requests.get(tables_url, headers=headers, timeout=10)
        resp_json = resp.json()
        
        if resp_json.get("code") == 0 and resp_json["data"]["items"]:
            tables = resp_json["data"]["items"]
            self.bitable_table_id = tables[0]["table_id"]
            print(f"[INFO] 获取到表格: {tables[0]['name']}, table_id={self.bitable_table_id}")
        else:
            # 如果获取表格失败，尝试用 block_id 转换 table_id
            # block_id 格式为 blkXXX，table_id 格式为 tblXXX
            if block_id.startswith("blk"):
                self.bitable_table_id = "tbl" + block_id[3:]
                print(f"[INFO] block_id转table_id: {self.bitable_table_id}")
            else:
                self.bitable_table_id = block_id
        
        print(f"[SUCCESS] 解析完成！app_token={self.bitable_app_token}, table_id={self.bitable_table_id}")

    def switch_table(self, table_name: str = "default") -> None:
        self.current_table = table_name
    
    def _get_tenant_access_token(self) -> str:
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        token_payload = {"app_id": self.app_id, "app_secret": self.app_secret}
        token_resp = requests.post(token_url, json=token_payload, timeout=10)
        return token_resp.json()["tenant_access_token"]

    def get_bitable_records(self, table_name: str = None) -> dict:
        """读取多维表格数据，使用 bitable API"""
        try:
            access_token = self._get_tenant_access_token()
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # 使用 bitable API 读取记录
            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.bitable_app_token}/tables/{self.bitable_table_id}/records?page_size=500"
            resp = requests.get(url, headers=headers, timeout=10)
            resp_json = resp.json()
            
            if resp_json.get("code") != 0:
                raise Exception(f"bitable API 返回错误: {resp_json.get('msg')}, 错误码={resp_json.get('code')}")
            
            items = resp_json["data"]["items"]
            
            # 转换为系统兼容格式
            record_map = {}
            for item in items:
                record_id = item["record_id"]
                fields = item["fields"]
                record = {}
                for field_name, field_value in fields.items():
                    if isinstance(field_value, list):
                        display_text = str(field_value[0].get("text", field_value[0]) if isinstance(field_value[0], dict) else field_value[0])
                        record[field_name] = {"value": [{"text": display_text}]}
                    elif isinstance(field_value, dict):
                        record[field_name] = {"value": [{"text": str(field_value)}]}
                    elif isinstance(field_value, (int, float)):
                        record[field_name] = {"value": field_value}
                    else:
                        record[field_name] = {"value": [{"text": str(field_value)}]}
                record_map[record_id] = record
            
            print(f"[SUCCESS] 成功从飞书多维表格读取 {len(record_map)} 条记录")
            return {"recordMap": record_map}
            
        except Exception as e:
            raise Exception(f"读取多维表格失败: {str(e)}")

    def create_doc(self, title: str, content: str) -> str:
        """创建飞书文档 - 先创建空文档，再添加内容块"""
        url = "https://open.feishu.cn/open-apis/docx/v1/documents"
        headers = {
            "Authorization": f"Bearer {self._get_tenant_access_token()}",
            "Content-Type": "application/json"
        }
        
        # 步骤1：创建文档（只支持 title 参数）
        body = {"title": title}
        resp = requests.post(url, headers=headers, json=body, timeout=10)
        resp_json = resp.json()
        
        if resp_json.get("code") != 0:
            raise Exception(f"创建文档失败: {resp_json.get('msg')}, 错误码={resp_json.get('code')}")
        
        document_id = resp_json["data"]["document"]["document_id"]
        revision_id = resp_json["data"]["document"]["revision_id"]
        print(f"[INFO] 文档创建成功, document_id={document_id}")
        
        # 步骤2：添加内容块
        blocks_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/children"
        blocks_body = {
            "children": [],
            "index": 0,
            "location": "start"
        }
        
        # 把内容按段落分割成文本块
        lines = content.strip().split("\n")
        for line in lines:
            if line.strip():
                block = {
                    "block_type": 2,  # 2 = 文本
                    "text": {
                        "elements": [{"text_run": {"content": line}}],
                        "style": {}
                    }
                }
                blocks_body["children"].append(block)
        
        if blocks_body["children"]:
            resp = requests.post(blocks_url, headers=headers, json=blocks_body, timeout=30)
            resp_json = resp.json()
            if resp_json.get("code") != 0:
                print(f"[WARN] 添加文档内容失败: {resp_json.get('msg')}, 文档已创建但内容为空")
        
        return f"https://feishu.cn/docx/{document_id}"
