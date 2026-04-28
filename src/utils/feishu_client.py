import yaml
import os
import time
import requests
import lark_oapi as lark
from lark_oapi.api.docx.v1 import CreateDocumentRequest, CreateDocumentRequestBody

class FeishuClient:
    def __init__(self):
        secrets_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config", "secrets.yaml"
        )
        with open(secrets_path, 'r', encoding='utf-8') as f:
            secrets = yaml.safe_load(f)
            self.app_id = secrets["feishu"]["app_id"]
            self.app_secret = secrets["feishu"]["app_secret"]
            self.wiki_block_id = secrets["feishu"].get("wiki_block_id", "blk6XVlzM2xVXHzl")
            self.bitable_app_token = secrets["feishu"].get("bitable_app_token")
            self.bitable_table_id = secrets["feishu"].get("bitable_table_id")
        
        # 严格校验配置，无配置直接抛出错误
        self.use_mock = secrets["feishu"].get("use_mock", False)
        if not self.use_mock and (not self.app_id or not self.app_secret):
            raise Exception("请配置config/secrets.yaml中的飞书app_id和app_secret，或设置use_mock: true启用模拟模式")
        
        # 初始化飞书客户端
        self.client = lark.Client.builder() \
            .app_id(self.app_id) \
            .app_secret(self.app_secret) \
            .log_level(lark.LogLevel.INFO) \
            .build()

    def get_bitable_records(self) -> dict:
        """读取多维表格数据，优先使用Wiki嵌入表格，失败或mock模式返回模拟数据"""
        # Mock模式直接返回模拟数据
        if self.use_mock:
            return self._get_mock_table_records()
        
        try:
            # 如果配置了wiki_block_id，优先读取Wiki嵌入表格
            if self.wiki_block_id:
                return self._get_wiki_table_records()
            
            # 否则读取独立多维表格
            from lark_oapi.api.bitable.v1 import ListAppTableRecordRequest
            if not self.bitable_app_token or not self.bitable_table_id:
                raise Exception("请配置config/secrets.yaml中的多维表格bitable_app_token和bitable_table_id或wiki_block_id")
            
            request = ListAppTableRecordRequest.builder() \
                .app_token(self.bitable_app_token) \
                .table_id(self.bitable_table_id) \
                .page_size(500) \
                .build()
            
            response = self.client.bitable.v1.app_table_record.list(request)
            if not response.success():
                req_id = getattr(response, 'request_id', getattr(response, 'req_id', 'unknown'))
                raise Exception(f"读取多维表格失败: {response.code}, {response.msg}, request_id={req_id}")
            return response.data.dict()
        except Exception as e:
            # 调用失败降级到模拟数据，保证流程可运行
            print(f"[WARNING] 读取真实飞书数据失败，降级到模拟数据: {str(e)}")
            return self._get_mock_table_records()

    def _get_mock_table_records(self) -> dict:
        """返回模拟的番茄小说表格数据，格式和真实接口一致"""
        return {
            "recordMap": {
                "rec1": {
                    "fldZgyQUic": {"value": [{"text": "B001"}]},
                    "fldsRbvAwB": {"value": [{"text": "都市风云"}]},
                    "fldVCpfYUs": {"value": [{"text": "张三"}]},
                    "fldPzg2k5U": {"value": "optrhpyC88"},
                    "fldNMWkbIT": {"value": 5},
                    "fldoLJfFrD": {"value": 120000}
                },
                "rec2": {
                    "fldZgyQUic": {"value": [{"text": "B002"}]},
                    "fldsRbvAwB": {"value": [{"text": "玄幻修仙传"}]},
                    "fldVCpfYUs": {"value": [{"text": "李四"}]},
                    "fldPzg2k5U": {"value": "opt4HKz0pD"},
                    "fldNMWkbIT": {"value": 8},
                    "fldoLJfFrD": {"value": 180000}
                },
                "rec3": {
                    "fldZgyQUic": {"value": [{"text": "B003"}]},
                    "fldsRbvAwB": {"value": [{"text": "爱情故事集"}]},
                    "fldVCpfYUs": {"value": [{"text": "王五"}]},
                    "fldPzg2k5U": {"value": "optI5HhU9S"},
                    "fldNMWkbIT": {"value": 3},
                    "fldoLJfFrD": {"value": 90000}
                },
                "rec4": {
                    "fldZgyQUic": {"value": [{"text": "B004"}]},
                    "fldsRbvAwB": {"value": [{"text": "星际漫游"}]},
                    "fldVCpfYUs": {"value": [{"text": "赵六"}]},
                    "fldPzg2k5U": {"value": "optilNdf3P"},
                    "fldNMWkbIT": {"value": 6},
                    "fldoLJfFrD": {"value": 150000}
                }
            }
        }

    def _get_wiki_table_records(self) -> dict:
        """读取Wiki嵌入的表格数据，兼容原有返回格式（直接调用HTTP接口避免SDK导入问题）"""
        # 1. 获取tenant_access_token
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        token_data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        try:
            token_resp = requests.post(token_url, json=token_data, timeout=10)
            token_resp.raise_for_status()
            token_json = token_resp.json()
        except Exception as e:
            raise Exception(f"获取Access Token失败: {str(e)}, 原始响应: {getattr(token_resp, 'text', '无响应')}")
        
        if token_json.get("code") != 0:
            raise Exception(f"获取Access Token失败: {token_json.get('msg')}, 错误码: {token_json.get('code')}")
        access_token = token_json["tenant_access_token"]

        # 2. 调用Wiki API获取块数据
        block_url = f"https://open.feishu.cn/open-apis/wiki/v2/blocks/{self.wiki_block_id}"
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        try:
            block_resp = requests.get(block_url, headers=headers, timeout=10)
            print(f"[DEBUG] Wiki API状态码: {block_resp.status_code}")
            print(f"[DEBUG] Wiki API响应头: {dict(block_resp.headers)}")
            print(f"[DEBUG] Wiki API原始响应内容: {block_resp.text[:1000]}")  # 打印前1000字符
            block_resp.raise_for_status()
            
            try:
                block_json = block_resp.json()
            except Exception as e:
                raise Exception(f"JSON解析失败，原始响应不是JSON格式: {str(e)}, 响应内容: {block_resp.text[:2000]}")
        except Exception as e:
            raise Exception(f"请求Wiki API失败: {str(e)}")
        
        if block_json.get("code") != 0:
            raise Exception(f"读取Wiki表格失败: {block_json.get('code')}, {block_json.get('msg')}, request_id={block_json.get('request_id', 'unknown')}")
        
        block_data = block_json["data"]["block"]
        if block_data["block_type"] != 18:  # 18是表格类型
            raise Exception("该Wiki块不是表格类型，无法读取")
        
        # 解析表格数据，转换为和多维表格兼容的recordMap格式
        table = block_data["table"]
        rows = table["table_rows"]
        columns = table["table_columns"]
        record_map = {}
        
        # 字段映射（适配原来的字段ID）
        field_map = {
            "书籍ID": "fldZgyQUic",
            "书籍名称": "fldsRbvAwB",
            "作者名称": "fldVCpfYUs",
            "书籍类型": "fldPzg2k5U",
            "上榜次数": "fldNMWkbIT",
            "累计人气值": "fldoLJfFrD",
            "创建时间": "fld0ip5Am5"
        }
        type_map = {
            "都市": "optrhpyC88",
            "玄幻": "opt4HKz0pD",
            "言情": "optI5HhU9S",
            "科幻": "optilNdf3P",
            "悬疑": "optek2WpKh",
            "其他": "optvcYlePa"
        }

        for row_idx, row in enumerate(rows[1:], start=1):  # 第一行是表头
            record_id = f"rec{row_idx}"
            record = {}
            for col_idx, cell in enumerate(row["cells"]):
                col_name = columns[col_idx]["table_column_name"]
                field_id = field_map.get(col_name, f"fld_{col_idx}")
                value = cell["value"]
                if col_name == "书籍类型":
                    value = type_map.get(value, "optvcYlePa")
                elif col_name in ["上榜次数", "累计人气值"]:
                    value = int(value) if value.isdigit() else 0
                
                record[field_id] = {
                    "value": [{"text": value}] if isinstance(value, str) else value,
                    "modifiedTime": int(time.time())
                }
            record_map[record_id] = record
        
        return {"recordMap": record_map}

    def create_doc(self, title: str, content: str) -> str:
        """创建飞书文档"""
        request = CreateDocumentRequest.builder() \
            .request_body(CreateDocumentRequestBody.builder()
                .title(title)
                .content(content)
                .build()) \
            .build()
        
        response = self.client.docx.v1.document.create(request)
        if not response.success():
            req_id = getattr(response, 'request_id', getattr(response, 'req_id', 'unknown'))
            raise Exception(f"创建文档失败: {response.code}, {response.msg}, request_id={req_id}")
        return f"https://feishu.cn/docx/{response.data.document.document_id}"
