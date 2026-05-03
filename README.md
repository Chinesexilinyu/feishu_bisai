# 给AI发通行证：Agent身份与权限系统

面向多Agent协作场景的生产级身份与权限管理系统，解决AI Agent落地过程中的安全痛点，支持动态身份认证、细粒度权限控制、全链路审计追踪三大核心能力。

***

## 一、项目文件结构

```
2026feishubisai/
├── src/
│   ├── agents/                     # Agent实现层
│   │   ├── base_agent.py           # Agent基类
│   │   ├── doc_agent.py            # 文档助手Agent（用户交互入口，端口8001）
│   │   ├── data_agent.py           # 数据Agent（飞书表格操作，端口8002）
│   │   └── web_agent.py            # 检索Agent（公网检索，端口8003）
│   ├── auth_service/               # 认证授权服务
│   │   ├── key_manager.py          # RSA密钥管理
│   │   ├── token_issuer.py         # Token签发服务
│   │   └── token_validator.py      # Token验证服务
│   ├── audit_service/              # 审计日志服务
│   │   ├── logger.py               # 审计日志记录
│   │   ├── query.py                # 审计日志查询
│   │   └── tracer.py               # Trace ID管理
│   ├── common/                     # 公共模块
│   │   ├── auth_middleware.py      # Token验证中间件
│   │   └── agent_protocol.py       # Agent交互协议定义
│   ├── policy_engine/              # 权限决策引擎
│   │   ├── static_policy.py        # 静态权限规则
│   │   ├── dynamic_policy.py       # 动态权限决策
│   │   └── delegation.py           # 委托权限管理
│   ├── llm/                        # LLM适配层
│   │   ├── base.py                 # LLM基类
│   │   ├── openai_compatible.py    # OpenAI兼容接口适配（支持Ollama）
│   │   └── intent_recognizer.py    # 用户意图识别
│   └── utils/                      # 工具类
│       ├── feishu_client.py        # 飞书API客户端
│       └── feishu_doc.py           # 飞书文档操作工具
├── run_doc_agent.py                # DocAgent启动入口
├── run_data_agent.py               # DataAgent启动入口
├── run_web_agent.py                # WebAgent启动入口
├── log.py                          # 审计日志查询工具
├── requirements.txt                # 项目依赖
├── audit_logs.jsonl                # 审计日志存储文件（自动生成）
├── revoked_tokens.json             # 吊销Token列表（自动生成）
└── README.md                       # 项目说明文档
├── config/
│   ├── agents.yaml/                
│   ├── private_key.prm/             
│   ├── public_key.pem/              
│   ├── secrets.yaml/                     # 配置文档
│   ├── users.yaml/              
```

***

## 二、环境依赖配置

### 2.1 Python环境要求

- Python 3.10+ （推荐3.12.x）
- pip 23.0+

### 2.2 依赖安装

```bash
# 克隆项目到本地
git clone <仓库地址>
cd 2026feishubisai


# 安装依赖
pip install -r requirements.txt
```

### 2.3 本地Ollama部署（可选，不使用OpenAI时需要）

如果使用本地大模型替代OpenAI API，需要部署Ollama：

1. 下载安装Ollama
2. 拉取模型：

```bash
ollama pull qwen3:4b  
```

1. 验证Ollama服务：访问<http://localhost:11434> 确认服务正常运行

### 2.4 配置文件设置
在secrets.yaml填写以下配置：

cd ./config/secrets.yaml
```env
# 飞书应用配置，需要用户自行填写
feishu:
  app_id: ""
  app_secret: ""
  
  # 飞书目标链接（自动解析表格参数，无需手动配置app_token和table_id）
  target_feishu_url: ""



# 服务配置
server:
  host: "0.0.0.0"
  port: 8000
  base_url: "http://localhost:8000"  # 动态配置服务地址，根据实际部署修改

# LLM配置
llm:
  # 支持的类型: rule(默认规则匹配), openai(兼容OpenAI协议), ollama(本地部署模型)
  type: "ollama"
  # 通用配置
  api_base: "http://localhost:11434/v1" # 服务地址，如ollama填http://localhost:11434/v1，openai填https://api.openai.com/v1
  api_key: "ollama" # API密钥
  model_name: "qwen3:4b" # 模型名称，如ollama的qwen:7b，openai的gpt-3.5-turbo
```

### 2.5 飞书应用配置

1. 在飞书开放平台创建企业自建应用
2. 开通「多维表格」权限，授权应用访问表格的读写权限
3. 将应用添加到多维表格的协作者中，授予编辑权限

***

## 三、功能复现流程与指令

### 3.1 基础服务启动

按照以下顺序启动服务：

```bash
# 1. 启动DataAgent
python run_data_agent.py --server

# 2. 启动WebAgent
python run_web_agent.py --server

# 3. 启动DocAgent
python run_doc_agent.py

```

### 3.2 正常业务流程复现（Agent调用实现）

#### 1：仅读取内部数据

```bash
python run_data_agent.py --server

python run_doc_agent.py
# 进入交互模式后输入：
> 请读取表格数据，生成番茄小说数据分析报告

```

#### 2：读取内部数据和外部检索数据

```bash
python run_data_agent.py --server

python run_web_agent.py --server

python run_doc_agent.py
# 进入交互模式后输入：
> 请读取表格数据，结合外部检索数据，生成番茄小说数据分析报告
```

### 3.3 越权拦截测试复现

#### 测试场景：WebAgent访问内部数据


```bash
python run_data_agent.py --server

python run_web_agent.py 
# 进入交互模式后输入：
> 请读取表格数据，生成番茄小说数据分析报告
```



### 3.4 Agent不可用场景复现

1. 停止DataAgent服务
2. 再次请求生成报告：

```bash
python run_doc_agent.py
> 请读取内部表格数据，生成番茄小说数据分析报告
```


### 3.5 审计追溯实现复现

使用`log.py`工具查询审计日志：

```bash
# 1. 按Trace ID查询完整上下文
python log.py --traceid xxxxxxxx

# 2. 查看所有审计日志
python log.py --all --limit 100
```




***

## 四、常见问题


1**飞书API调用失败**：检查飞书应用权限配置，确认应用已添加到表格协作者

2**审计日志查询不到**：确认Trace ID正确，日志默认按时间倒序排列，最新日志在前

3**Ollama调用失败**：确认Ollama服务已启动，模型名称正确，`OPENAI_BASE_URL`配置为`http://localhost:11434/v1`

