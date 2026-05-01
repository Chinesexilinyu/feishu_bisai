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
        self.all_tables = {}  # {table_name: {"table_id": ..., "fields": [...]}}
        self._resolve_bitable_params()
        
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
        
        # 步骤3：获取表格列表，存储全部表格
        tables_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.bitable_app_token}/tables?page_size=100"
        resp = requests.get(tables_url, headers=headers, timeout=10)
        resp_json = resp.json()
        
        if resp_json.get("code") == 0 and resp_json["data"]["items"]:
            tables = resp_json["data"]["items"]
            self.bitable_table_id = tables[0]["table_id"]
            for t in tables:
                self.all_tables[t["name"]] = {"table_id": t["table_id"], "fields": []}
                print(f"[INFO] 获取到表格: {t['name']}, table_id={t['table_id']}")
            
            # 步骤4：获取每个表的字段元数据（field name → Chinese label）
            for table_name, table_info in self.all_tables.items():
                tbl_id = table_info["table_id"]
                fields_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.bitable_app_token}/tables/{tbl_id}/fields?page_size=100"
                fields_resp = requests.get(fields_url, headers=headers, timeout=10)
                fields_json = fields_resp.json()
                if fields_json.get("code") == 0:
                    for f in fields_json["data"]["items"]:
                        table_info["fields"].append({
                            "field_name": f["field_name"],
                            "field_label": f.get("field_name", ""),  # fallback
                        })
                    field_names = [f["field_name"] for f in table_info["fields"]]
                    print(f"[INFO]   表格[{table_name}]字段: {field_names}")
                else:
                    print(f"[WARN]   表格[{table_name}]字段获取失败: {fields_json.get('msg')}")
        else:
            if block_id.startswith("blk"):
                self.bitable_table_id = "tbl" + block_id[3:]
                self.all_tables["default"] = {"table_id": self.bitable_table_id, "fields": []}
                print(f"[INFO] block_id转table_id: {self.bitable_table_id}")
            else:
                self.bitable_table_id = block_id
                self.all_tables["default"] = {"table_id": self.bitable_table_id, "fields": []}
        
        print(f"[SUCCESS] 解析完成！app_token={self.bitable_app_token}, table_id={self.bitable_table_id}")

    def switch_table(self, table_name: str = "default") -> None:
        self.current_table = table_name

    def get_table_names(self) -> list:
        """获取所有表格名称列表"""
        return list(self.all_tables.keys())

    def get_all_table_records(self) -> dict:
        """读取所有多维表格的全部记录，返回 {table_name: {records, fields, row_count}}"""
        try:
            access_token = self._get_tenant_access_token()
            headers = {"Authorization": f"Bearer {access_token}"}
            all_data = {}
            
            for table_name, table_info in self.all_tables.items():
                tbl_id = table_info["table_id"]
                url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{self.bitable_app_token}/tables/{tbl_id}/records?page_size=500"
                resp = requests.get(url, headers=headers, timeout=15)
                resp_json = resp.json()
                
                if resp_json.get("code") != 0:
                    print(f"[WARN] 表格[{table_name}]读取失败: {resp_json.get('msg')}")
                    continue
                
                items = resp_json.get("data", {}).get("items", [])
                records = []
                for item in items:
                    fields = item.get("fields", {})
                    flat_record = {}
                    for field_name, field_value in fields.items():
                        if isinstance(field_value, list) and len(field_value) > 0:
                            elem = field_value[0]
                            if isinstance(elem, dict):
                                flat_record[field_name] = elem.get("text", str(elem))
                            else:
                                flat_record[field_name] = str(elem)
                        elif isinstance(field_value, (int, float)):
                            flat_record[field_name] = field_value
                        elif isinstance(field_value, str):
                            flat_record[field_name] = field_value
                        elif field_value is None:
                            flat_record[field_name] = ""
                        else:
                            flat_record[field_name] = str(field_value)
                    records.append(flat_record)
                
                all_data[table_name] = {
                    "records": records,
                    "row_count": len(records),
                    "fields": [f["field_name"] for f in table_info.get("fields", [])],
                    "table_id": tbl_id
                }
                print(f"[SUCCESS] 表格[{table_name}]: 读取 {len(records)} 条记录")
            
            # 汇总info
            total_rows = sum(v["row_count"] for v in all_data.values())
            table_summary = ", ".join(f"{k}({v['row_count']}行)" for k, v in all_data.items())
            print(f"[SUCCESS] 全部表格读取完成: 共{len(all_data)}张表, {total_rows}条记录 ({table_summary})")
            
            return {"tables": all_data, "table_count": len(all_data), "total_rows": total_rows}
            
        except Exception as e:
            raise Exception(f"读取多维表格失败: {str(e)}")
    
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
        
        # 步骤2：添加内容块，分批写入避免长度超限
        blocks_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/children"
        
        # 飞书docx API block_type映射：
        # 1=页面(不可作为子块创建), 2=文本, 3=标题1, 4=标题2, 5=标题3, 6=标题4
        HEADING_TYPE_MAP = {
            1: (3, "heading1"),   # # 一级标题 → block_type=3, field=heading1
            2: (4, "heading2"),   # ## 二级标题 → block_type=4, field=heading2
            3: (5, "heading3"),   # ### 三级标题 → block_type=5, field=heading3
            4: (6, "heading4"),   # #### 四级标题 → block_type=6, field=heading4
        }
        
        # 把内容按段落分割成文本块
        lines = content.strip().split("\n")
        all_blocks = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检测标题级别（统计开头的#个数）
            heading_level = 0
            for ch in line:
                if ch == '#':
                    heading_level += 1
                else:
                    break
            
            if heading_level >= 1 and heading_level <= 4 and line[heading_level:heading_level+1] == ' ':
                # 标题块
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
                # 表格行作为普通文本处理
                block = {
                    "block_type": 2,
                    "text": {
                        "elements": [{"text_run": {"content": line}}],
                        "style": {}
                    }
                }
                all_blocks.append(block)
            elif line.startswith("---") or line.startswith("***"):
                # 分隔线，跳过或作为文本
                continue
            else:
                # 普通文本块
                block = {
                    "block_type": 2,
                    "text": {
                        "elements": [{"text_run": {"content": line}}],
                        "style": {}
                    }
                }
                all_blocks.append(block)
        
        # 分批写入，每批最多50个块，避免接口超限
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
                # 打印第一个失败块的详细信息用于调试
                if batch_blocks:
                    print(f"[DEBUG] 失败批次首个块: block_type={batch_blocks[0].get('block_type')}, keys={list(batch_blocks[0].keys())}")
        
        print(f"[INFO] 文档内容写入完成: {success_count}/{total_batches} 批次成功, 共{len(all_blocks)}个块")
        return f"https://feishu.cn/docx/{document_id}"
