# Agent 身份与权限系统设计方案

## 一、核心问题与解决思路

### 1.1 传统IAM为何失效？

| 维度 | 传统IAM (User→App) | Agent场景 (User→Agent→Agent→Service) |
|------|-------------------|--------------------------------------|
| 身份主体 | 单一用户 | 多层委托（用户→Agent A→Agent B） |
| 权限验证 | 边界内信任 | 跨边界需要显式验证 |
| 信任传递 | API Key/Session | 需要可验证的信任链 |
| 审计粒度 | 用户操作日志 | Agent调用链+用户上下文 |

### 1.2 三大核心痛点解决方案

```
痛点1: 身份混淆 → Access Token + 签名验证
痛点2: 信任链缺失 → JWT嵌套 + Chain of Trust
痛点3: 审计黑洞 → 结构化审计日志 + 调用链ID
```

---

## 二、系统架构设计

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户交互层                               │
│                    (自然语言指令 → 任务解析)                      │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                     Agent 编排层                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ 文档助手Agent │  │ 企业数据Agent │  │ 外部检索Agent │           │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘           │
│         │                  │                  │                   │
└─────────┼──────────────────┼──────────────────┼───────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    A2A 认证授权层 (核心)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Token服务   │  │ 权限引擎    │  │ 审计服务    │              │
│  │ • 签发      │  │ • 静态授权  │  │ • 日志记录  │              │
│  │ • 验证      │  │ • 动态授权  │  │ • 链路追踪  │              │
│  │ • 撤销      │  │ • 委托计算  │  │ • 异常告警  │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                        资源访问层                                │
│     ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│     │ 飞书OpenAPI  │  │ 外部Web API  │  │ 本地工具     │        │
│     │ • 通讯录     │  │ • 搜索引擎   │  │ • 文件读写   │        │
│     │ • 多维表格   │  │ • 公开数据   │  │ • 数据处理   │        │
│     │ • 日历      │  │              │  │              │        │
│     └──────────────┘  └──────────────┘  └──────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件职责

| 组件 | 职责 | 关键技术 |
|------|------|----------|
| **Token服务** | Agent身份凭证管理 | JWT + RS256签名 |
| **权限引擎** | 静态/动态授权计算 | Policy Engine + RBAC |
| **审计服务** | 全链路追踪与日志 | TraceID + 结构化日志 |
| **Agent网关** | 拦截所有A2A调用 | 中间件模式 |

---

## 三、Access Token 设计

### 3.1 JWT Token 结构

```json
{
  "header": {
    "alg": "RS256",
    "typ": "JWT",
    "kid": "key-id-001"
  },
  "payload": {
    // === 标准声明 ===
    "iss": "agent-auth-service",           // 签发者
    "sub": "agent-doc-assistant-001",      // Agent唯一标识
    "aud": "agent-data-service",           // 目标服务
    "exp": 1714060800,                     // 过期时间
    "iat": 1714057200,                     // 签发时间
    "jti": "token-uuid-12345",             // Token唯一ID(用于撤销)
    
    // === Agent扩展声明 ===
    "agent_id": "doc-assistant",           // Agent身份ID
    "agent_role": "coordinator",           // Agent角色
    "agent_name": "飞书文档助手",           // Agent显示名称
    
    // === 能力声明 ===
    "capabilities": [
      "doc:read",
      "doc:write",
      "data:query"
    ],
    
    // === 委托上下文 ===
    "delegated_user": {
      "user_id": "user-001",
      "user_name": "张三",
      "user_role": "admin"
    },
    
    // === 信任链 ===
    "chain_of_trust": [
      {
        "agent_id": "user-001",
        "agent_type": "human",
        "action": "initiate",
        "timestamp": 1714057200
      },
      {
        "agent_id": "doc-assistant",
        "agent_type": "ai_agent",
        "action": "delegate",
        "timestamp": 1714057210
      }
    ],
    
    // === 会话上下文 ===
    "session_id": "session-uuid-67890",
    "trace_id": "trace-uuid-abcdef",        // 全链路追踪ID
    "parent_token_id": null                 // 父Token ID(嵌套委托时)
  },
  "signature": "..."                        // RS256签名
}
```

### 3.2 Token 类型与应用场景

| Token类型 | 有效期 | 用途 | 示例场景 |
|----------|--------|------|----------|
| **Agent Identity Token** | 长期(24h) | Agent身份认证 | Agent启动时获取 |
| **Capability Token** | 短期(1h) | 操作授权凭证 | 委托调用时签发 |
| **Delegation Token** | 极短期(15min) | 嵌套委托 | Agent A→Agent B |
| **Session Token** | 会话级 | 用户会话关联 | 自然语言交互 |

---

## 四、权限模型设计

### 4.1 三层权限架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Layer 1: 静态授权                         │
│  (Agent注册时由管理员预定义，运行期间不变)                      │
│                                                              │
│  Agent Profile:                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ agent_id: doc-assistant                             │    │
│  │ static_capabilities:                                │    │
│  │   - doc:read, doc:write                            │    │
│  │   - data:query (not data:admin)                    │    │
│  │   - web:search                                      │    │
│  │ restrictions:                                        │    │
│  │   - no_direct_db_access: true                       │    │
│  │   - max_delegation_depth: 2                         │    │
│  └─────────────────────────────────────────────────────┘    │
└───────────────────────────────┬─────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────┐
│                    Layer 2: 用户权限                         │
│  (用户在系统中的实际权限)                                      │
│                                                              │
│  User Permissions:                                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ user_id: user-001                                   │    │
│  │ role: admin                                         │    │
│  │ permissions:                                        │    │
│  │   - feishu:contact:read                            │    │
│  │   - feishu:bitable:read, feishu:bitable:write      │    │
│  │   - feishu:calendar:read                           │    │
│  │   - feishu:doc:read, feishu:doc:write              │    │
│  └─────────────────────────────────────────────────────┘    │
└───────────────────────────────┬─────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────┐
│              Layer 3: 动态授权 (有效权限交集)                  │
│  (实时计算: Agent能力 ∩ 用户权限)                             │
│                                                              │
│  Effective Permissions Calculation:                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 当 doc-assistant 代表 user-001 执行操作时:          │    │
│  │                                                      │    │
│  │ Agent Capabilities: {doc:*, data:query, web:search}│    │
│  │ User Permissions:   {feishu:*:read, feishu:doc:*}  │    │
│  │ ──────────────────────────────────────────────────  │    │
│  │ Effective: {doc:read, doc:write, data:query}       │    │
│  │                                                      │    │
│  │ ❌ data:admin 被排除 (Agent无此能力)                │    │
│  │ ❌ feishu:contact:read 被排除 (Agent无此能力)       │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 能力声明语法

```
# 能力声明格式: resource:action 或 resource:subresource:action

# 基础能力
doc:read          # 读取文档
doc:write         # 写入文档
data:query        # 查询数据
data:admin        # 数据管理(高风险)

# 细粒度能力
feishu:contact:read       # 读取飞书通讯录
feishu:bitable:read       # 读取多维表格
feishu:bitable:write      # 写入多维表格
feishu:calendar:read      # 读取日历

# 外部能力
web:search         # 网络搜索
web:scrape         # 网页抓取
```

### 4.3 Agent角色定义

| Agent角色 | 静态能力 | 典型职责 |
|----------|---------|---------|
| **Coordinator** | doc:*, task:*, delegate:* | 任务编排、委托管理 |
| **DataAgent** | feishu:bitable:*, feishu:contact:read | 企业数据访问 |
| **WebAgent** | web:search, web:scrape | 外部信息检索 |
| **AdminAgent** | *:* (所有权限) | 系统管理(谨慎使用) |

---

## 五、核心流程设计

### 5.1 正常委托流程

```
用户: "帮我生成一份包含销售数据的飞书文档报告"

┌──────┐     ┌────────────┐     ┌────────────┐     ┌──────────┐
│ User │     │ DocAgent   │     │ DataAgent  │     │ 飞书API  │
└──┬───┘     └─────┬──────┘     └─────┬──────┘     └────┬─────┘
   │               │                  │                  │
   │ 1.自然语言请求  │                  │                  │
   │──────────────>│                  │                  │
   │               │                  │                  │
   │               │ 2.获取Identity Token                 │
   │               │─────────────────────────────────────>│
   │               │                  │                  │
   │               │ 3.签发Token(agent_id=doc-agent)     │
   │               │<─────────────────────────────────────│
   │               │                  │                  │
   │               │ 4.委托请求: 查询销售数据               │
   │               │   Token(委托链: user→doc-agent)     │
   │               │─────────────────>│                  │
   │               │                  │                  │
   │               │                  │ 5.验证Token      │
   │               │                  │   • 签名验证     │
   │               │                  │   • 委托链完整性 │
   │               │                  │   • 权限计算     │
   │               │                  │   user权限 ∩ agent能力
   │               │                  │                  │
   │               │                  │ 6.访问飞书API    │
   │               │                  │─────────────────>│
   │               │                  │                  │
   │               │                  │ 7.返回数据       │
   │               │                  │<─────────────────│
   │               │                  │                  │
   │               │ 8.返回数据+审计日志ID                 │
   │               │<─────────────────│                  │
   │               │                  │                  │
   │               │ 9.生成报告并写入飞书文档              │
   │               │─────────────────────────────────────>│
   │               │                  │                  │
   │ 10.返回完成报告 │                  │                  │
   │<──────────────│                  │                  │
   │               │                  │                  │
   │               │ 11.审计日志记录   │                  │
   │               │─────────────────────────────────────>│
   │               │                  │                  │
```

**关键Token变化**:

```json
// Step 3: DocAgent的身份Token
{
  "sub": "doc-agent-001",
  "capabilities": ["doc:*", "delegate:*"],
  "delegated_user": {
    "user_id": "user-001",
    "user_role": "admin"
  }
}

// Step 4: DocAgent委托给DataAgent的Token
{
  "sub": "data-agent-001",
  "capabilities": ["feishu:bitable:read"],
  "delegated_user": {
    "user_id": "user-001"
  },
  "chain_of_trust": [
    {"agent_id": "user-001", "action": "initiate"},
    {"agent_id": "doc-agent", "action": "delegate"}
  ],
  "parent_token_id": "token-doc-agent-001"
}
```

### 5.2 越权拦截流程

```
外部检索Agent尝试访问企业数据

┌──────┐     ┌────────────┐     ┌────────────┐
│ User │     │ WebAgent   │     │ DataAgent  │
└──┬───┘     └─────┬──────┘     └─────┬──────┘
   │               │                  │
   │ 1.恶意指令(或误操作)              │
   │ "读取企业通讯录"                  │
   │──────────────>│                  │
   │               │                  │
   │               │ 2.委托请求: 读取通讯录
   │               │   Token(web-agent capabilities)
   │               │─────────────────>│
   │               │                  │
   │               │                  │ 3.权限校验
   │               │                  │   web-agent capabilities:
   │               │                  │   {web:search, web:scrape}
   │               │                  │   
   │               │                  │   请求: feishu:contact:read
   │               │                  │   结果: ❌ NOT_AUTHORIZED
   │               │                  │
   │               │ 4.拒绝 + 错误码   │
   │               │<─────────────────│
   │               │   {              │
   │               │     "error": "FORBIDDEN",
   │               │     "code": 403,
   │               │     "message": "Agent 'web-agent' 缺少能力 'feishu:contact:read'",
   │               │     "audit_id": "audit-xxx"
   │               │   }              │
   │               │                  │
   │ 5.返回错误信息  │                  │
   │<──────────────│                  │
   │               │                  │
   │               │ 6.审计日志记录(拦截事件)
   │               │────────────────────────────>
```

### 5.3 动态授权流程

```
场景: 用户临时授予Agent一次性高权限操作

┌──────┐     ┌────────────┐     ┌────────────┐
│ User │     │ DocAgent   │     │ AuthServer │
└──┬───┘     └─────┬──────┘     └─────┬──────┘
   │               │                  │
   │ 1.敏感操作请求: 删除文档           │
   │──────────────>│                  │
   │               │                  │
   │               │ 2.检查静态权限    │
   │               │   doc:write ✓    │
   │               │   doc:delete ✗   │
   │               │                  │
   │               │ 3.请求动态授权    │
   │               │─────────────────>│
   │               │                  │
   │ 4.请求用户确认 │                  │
   │<─────────────────────────────────│
   │               │                  │
   │ 5.用户授权确认 │                  │
   │─────────────────────────────────>│
   │               │                  │
   │               │ 6.签发临时Token  │
   │               │   (有效期15分钟) │
   │               │<─────────────────│
   │               │                  │
   │               │ 7.执行删除操作    │
   │               │                  │
   │ 8.操作完成     │                  │
   │<──────────────│                  │
```

---

## 六、审计日志设计

### 6.1 审计日志结构

```json
{
  "audit_id": "audit-20240425-001",
  "timestamp": "2024-04-25T10:30:00Z",
  "trace_id": "trace-uuid-abcdef",
  
  // === 事件分类 ===
  "event_type": "AUTHORIZATION_DECISION",
  "event_category": "A2A_AUTH",
  "decision": "ALLOW",  // ALLOW | DENY
  
  // === 主体信息 ===
  "subject": {
    "agent_id": "doc-agent-001",
    "agent_name": "飞书文档助手",
    "agent_role": "coordinator"
  },
  
  // === 委托上下文 ===
  "delegation_context": {
    "delegated_user": {
      "user_id": "user-001",
      "user_name": "张三"
    },
    "chain_depth": 2,
    "chain_path": ["user-001", "doc-agent-001", "data-agent-001"]
  },
  
  // === 资源与操作 ===
  "resource": {
    "type": "feishu_bitable",
    "resource_id": "bitable-xxx",
    "action": "read"
  },
  
  // === 权限详情 ===
  "authorization": {
    "requested_capability": "feishu:bitable:read",
    "agent_capabilities": ["doc:*", "data:query"],
    "user_permissions": ["feishu:*:read"],
    "effective_permission": "feishu:bitable:read",
    "decision_reason": "CAPABILITY_MATCH"
  },
  
  // === 风险评估 ===
  "risk_assessment": {
    "risk_level": "LOW",
    "risk_factors": [],
    "anomaly_detected": false
  },
  
  // === 上下文信息 ===
  "context": {
    "ip_address": "192.168.1.100",
    "session_id": "session-xxx",
    "user_agent": "DocAgent/1.0",
    "request_id": "req-xxx"
  }
}
```

### 6.2 关键事件类型

| 事件类型 | 描述 | 记录时机 |
|---------|------|---------|
| `TOKEN_ISSUED` | Token签发 | Agent获取身份凭证 |
| `TOKEN_VERIFIED` | Token验证 | A2A调用验证 |
| `TOKEN_REVOKED` | Token撤销 | 异常检测/用户操作 |
| `AUTHORIZATION_DECISION` | 授权决策 | 每次权限校验 |
| `DELEGATION_INITIATED` | 委托发起 | Agent间委托开始 |
| `POLICY_VIOLATION` | 策略违规 | 越权尝试拦截 |
| `ANOMALY_DETECTED` | 异常检测 | 可疑行为识别 |

### 6.3 审计日志查询接口

```python
# 查询接口设计
class AuditQuery:
    def query_by_trace_id(trace_id: str) -> List[AuditLog]:
        """查询完整调用链"""
        
    def query_by_user(user_id: str, time_range: TimeRange) -> List[AuditLog]:
        """查询用户所有委托操作"""
        
    def query_by_agent(agent_id: str, time_range: TimeRange) -> List[AuditLog]:
        """查询Agent所有操作"""
        
    def query_denied_events(time_range: TimeRange) -> List[AuditLog]:
        """查询所有拒绝事件"""
        
    def export_audit_report(format: str = "json") -> str:
        """导出审计报告"""
```

---

## 七、安全增强设计

### 7.1 Token盗用防护

```
┌──────────────────────────────────────────────────────────┐
│                   多重防护机制                            │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  1. 绑定验证 (Binding)                                   │
│     Token绑定:                                           │
│     • Agent实例ID (process_id + machine_id)             │
│     • 网络指纹 (IP + User-Agent)                         │
│     • 时间窗口 (签发时间 + 有效期)                        │
│                                                          │
│  2. 实时撤销 (Revocation)                                │
│     • Token黑名单 (Redis)                                │
│     • 异常检测触发自动撤销                               │
│     • 用户主动撤销接口                                   │
│                                                          │
│  3. 频率限制 (Rate Limiting)                             │
│     • 单Agent QPS限制                                    │
│     • 单用户委托深度限制                                 │
│     • 异常行为熔断                                       │
│                                                          │
│  4. 签名验证 (Signature)                                 │
│     • RS256非对称加密                                    │
│     • 定期密钥轮换                                       │
│     • 密钥泄露应急响应                                   │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### 7.2 Prompt Injection防护

```python
# Prompt Injection检测与防护
class PromptInjectionDefense:
    def __init__(self):
        self.dangerous_patterns = [
            r"ignore.*previous.*instruction",
            r"you are now.*admin",
            r"grant.*permission",
            r"bypass.*auth"
        ]
    
    def detect_injection(self, user_input: str) -> bool:
        """检测Prompt注入尝试"""
        for pattern in self.dangerous_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                return True
        return False
    
    def sanitize_delegation(self, delegation_request: dict) -> dict:
        """清理委托请求"""
        # 1. 验证委托方Token有效性
        # 2. 检查委托深度限制
        # 3. 验证被委托Agent身份
        # 4. 确保权限不扩大
        pass
```

### 7.3 异常行为检测

```
异常检测规则引擎:

Rule 1: 异常时间访问
  IF (access_time NOT IN business_hours) AND (resource_type = "sensitive")
  THEN risk_score += 30

Rule 2: 高频委托
  IF (delegation_count_per_minute > 10)
  THEN risk_score += 40

Rule 3: 权限升级尝试
  IF (requested_capability NOT IN static_capabilities) AND (attempt_count > 3)
  THEN risk_score += 50

Rule 4: 跨域访问异常
  IF (agent_id IN web_agents) AND (resource_type IN internal_resources)
  THEN risk_score += 60

WHEN risk_score >= 70:
  - 立即拦截请求
  - 撤销相关Token
  - 发送告警通知
```

---

## 八、技术选型建议

### 8.1 推荐技术栈

| 层次 | 推荐技术 | 理由 |
|------|---------|------|
| **Token服务** | Python + PyJWT + cryptography | JWT标准实现，RS256签名 |
| **权限引擎** | Python + OPA(Open Policy Agent) | 声明式策略，灵活强大 |
| **审计服务** | Python + Elasticsearch + Kibana | 结构化日志，可视化分析 |
| **缓存** | Redis | Token黑名单、会话缓存 |
| **数据库** | PostgreSQL | Agent配置、权限策略存储 |
| **消息队列** | RabbitMQ/Kafka | 异步审计日志处理 |
| **API框架** | FastAPI | 异步、高性能、自动文档 |

### 8.2 项目结构建议

```
agent-iam-system/
├── README.md
├── docs/
│   ├── architecture.md         # 架构设计文档
│   ├── protocol.md             # A2A协议文档
│   ├── api-spec.yaml           # OpenAPI规范
│   └── demo-guide.md           # 演示指南
│
├── src/
│   ├── auth_service/           # Token服务
│   │   ├── token_issuer.py     # Token签发
│   │   ├── token_validator.py  # Token验证
│   │   └── key_manager.py      # 密钥管理
│   │
│   ├── policy_engine/          # 权限引擎
│   │   ├── static_policy.py    # 静态授权
│   │   ├── dynamic_policy.py   # 动态授权
│   │   └── delegation.py       # 委托计算
│   │
│   ├── audit_service/          # 审计服务
│   │   ├── logger.py           # 日志记录
│   │   ├── tracer.py           # 链路追踪
│   │   └── query.py            # 查询接口
│   │
│   ├── gateway/                # Agent网关
│   │   ├── middleware.py       # 认证中间件
│   │   └── rate_limiter.py     # 频率限制
│   │
│   ├── agents/                 # Agent实现
│   │   ├── doc_agent.py        # 文档助手Agent
│   │   ├── data_agent.py       # 企业数据Agent
│   │   └── web_agent.py        # 外部检索Agent
│   │
│   └── api/                    # API接口
│       ├── auth_api.py         # 认证接口
│       ├── delegation_api.py   # 委托接口
│       └── audit_api.py        # 审计接口
│
├── config/
│   ├── agents.yaml             # Agent配置
│   ├── policies.yaml           # 权限策略
│   └── secrets.yaml            # 密钥配置
│
├── scripts/
│   ├── start.sh                # 启动脚本
│   ├── demo_normal.sh          # 正常流程演示
│   └── demo_attack.sh          # 攻击拦截演示
│
└── tests/
    ├── test_token.py           # Token测试
    ├── test_policy.py          # 权限测试
    └── test_integration.py     # 集成测试
```

---

## 九、实现路线图

### Phase 1: 基础框架 (第1-2周)

- [ ] 搭建项目结构
- [ ] 实现Token服务(签发+验证)
- [ ] 实现静态授权引擎
- [ ] 实现基础审计日志
- [ ] 创建3个基础Agent

**交付物**: 可运行的MVP，支持基本A2A认证

### Phase 2: 核心功能 (第3-4周)

- [ ] 实现委托授权流程
- [ ] 实现动态授权机制
- [ ] 实现越权拦截
- [ ] 完善审计日志结构
- [ ] 添加链路追踪

**交付物**: 完整A2A认证授权系统

### Phase 3: 安全增强 (第5周)

- [ ] Token盗用防护
- [ ] Prompt Injection检测
- [ ] 异常行为检测
- [ ] Token撤销机制

**交付物**: 安全增强版系统

### Phase 4: 演示优化 (第6周)

- [ ] 完善演示脚本
- [ ] 添加可视化界面(可选)
- [ ] 性能优化
- [ ] 文档完善

**交付物**: 比赛提交版本

---

## 十、演示脚本设计

### 10.1 正常委托流程演示

```bash
# 演示脚本: demo_normal.sh

echo "=========================================="
echo "场景1: 正常委托流程演示"
echo "=========================================="

# Step 1: 启动系统
echo "[1] 启动Agent IAM系统..."
./scripts/start.sh

# Step 2: 用户请求生成报告
echo "[2] 用户请求: 生成包含销售数据的飞书文档报告"
curl -X POST http://localhost:8000/api/task \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-001",
    "task": "生成一份包含Q1销售数据的飞书文档报告",
    "agent_id": "doc-assistant"
  }'

# Step 3: 观察调用链
echo "[3] 调用链路:"
echo "  User(user-001) → DocAgent → DataAgent → 飞书API"

# Step 4: 查看审计日志
echo "[4] 审计日志:"
curl http://localhost:8000/api/audit/trace/{trace_id}

echo "[✓] 正常流程演示完成"
```

### 10.2 越权拦截演示

```bash
# 演示脚本: demo_attack.sh

echo "=========================================="
echo "场景2: 越权拦截演示"
echo "=========================================="

# Step 1: 外部检索Agent尝试访问企业数据
echo "[1] 外部检索Agent尝试委托访问企业数据"
curl -X POST http://localhost:8000/api/delegate \
  -H "Content-Type: application/json" \
  -d '{
    "from_agent": "web-agent",
    "to_agent": "data-agent",
    "action": "read",
    "resource": "feishu:contact"
  }'

# Step 2: 观察拦截结果
echo "[2] 预期结果: 403 Forbidden"
echo "  错误信息: Agent 'web-agent' 缺少能力 'feishu:contact:read'"

# Step 3: 查看审计日志
echo "[3] 拦截事件审计日志:"
curl http://localhost:8000/api/audit/denied?time_range=1h

echo "[✓] 越权拦截演示完成"
```

---

## 十一、关键代码示例

### 11.1 Token签发服务

```python
from datetime import datetime, timedelta
import jwt
from cryptography.hazmat.primitives import serialization

class TokenService:
    def __init__(self, private_key_path: str, public_key_path: str):
        with open(private_key_path, 'rb') as f:
            self.private_key = serialization.load_pem_private_key(
                f.read(), password=None
            )
        with open(public_key_path, 'rb') as f:
            self.public_key = serialization.load_pem_public_key(
                f.read()
            )
    
    def issue_token(
        self,
        agent_id: str,
        agent_role: str,
        capabilities: list,
        delegated_user: dict = None,
        expires_in: int = 3600
    ) -> str:
        """签发Agent身份Token"""
        now = datetime.utcnow()
        
        payload = {
            # 标准声明
            "iss": "agent-auth-service",
            "sub": agent_id,
            "iat": now,
            "exp": now + timedelta(seconds=expires_in),
            "jti": str(uuid.uuid4()),
            
            # Agent扩展
            "agent_id": agent_id,
            "agent_role": agent_role,
            "capabilities": capabilities,
            
            # 委托上下文
            "delegated_user": delegated_user,
            "chain_of_trust": []
        }
        
        if delegated_user:
            payload["chain_of_trust"].append({
                "agent_id": delegated_user["user_id"],
                "agent_type": "human",
                "action": "initiate",
                "timestamp": int(now.timestamp())
            })
        
        token = jwt.encode(
            payload,
            self.private_key,
            algorithm="RS256"
        )
        
        return token
    
    def verify_token(self, token: str) -> dict:
        """验证Token并返回payload"""
        try:
            payload = jwt.decode(
                token,
                self.public_key,
                algorithms=["RS256"]
            )
            return {"valid": True, "payload": payload}
        except jwt.ExpiredSignatureError:
            return {"valid": False, "error": "TOKEN_EXPIRED"}
        except jwt.InvalidSignatureError:
            return {"valid": False, "error": "INVALID_SIGNATURE"}
        except Exception as e:
            return {"valid": False, "error": str(e)}
```

### 11.2 权限引擎

```python
class PolicyEngine:
    def __init__(self, agent_config: dict, user_permissions: dict):
        self.agent_config = agent_config
        self.user_permissions = user_permissions
    
    def check_authorization(
        self,
        agent_id: str,
        user_id: str,
        resource: str,
        action: str
    ) -> dict:
        """检查授权"""
        
        # 获取Agent静态能力
        agent_caps = self.agent_config.get(agent_id, {}).get("capabilities", [])
        
        # 获取用户权限
        user_perms = self.user_permissions.get(user_id, [])
        
        # 计算请求的能力
        requested_cap = f"{resource}:{action}"
        
        # 权限交集计算
        effective_perms = self._calculate_effective_permissions(
            agent_caps, user_perms
        )
        
        # 检查是否授权
        is_authorized = self._match_capability(requested_cap, effective_perms)
        
        return {
            "authorized": is_authorized,
            "requested": requested_cap,
            "effective_permissions": effective_perms,
            "reason": "CAPABILITY_MATCH" if is_authorized else "CAPABILITY_MISMATCH"
        }
    
    def _calculate_effective_permissions(
        self,
        agent_capabilities: list,
        user_permissions: list
    ) -> list:
        """计算有效权限交集"""
        effective = []
        
        for cap in agent_capabilities:
            # 支持通配符匹配
            if cap.endswith(":*"):
                prefix = cap[:-2]
                matching_user_perms = [
                    p for p in user_permissions
                    if p.startswith(prefix)
                ]
                effective.extend(matching_user_perms)
            elif cap in user_permissions:
                effective.append(cap)
        
        return effective
    
    def _match_capability(self, requested: str, capabilities: list) -> bool:
        """匹配能力"""
        for cap in capabilities:
            if cap == "*:*":
                return True
            if cap == requested:
                return True
            if cap.endswith(":*"):
                prefix = cap[:-2]
                if requested.startswith(prefix):
                    return True
        return False
```

### 11.3 审计日志服务

```python
import json
from datetime import datetime
from typing import List, Optional

class AuditService:
    def __init__(self, storage_backend):
        self.storage = storage_backend
    
    def log_authorization_event(
        self,
        event_type: str,
        decision: str,
        subject: dict,
        resource: dict,
        authorization: dict,
        trace_id: str,
        delegation_context: dict = None
    ):
        """记录授权事件"""
        
        audit_log = {
            "audit_id": f"audit-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.utcnow().isoformat(),
            "trace_id": trace_id,
            
            "event_type": event_type,
            "event_category": "A2A_AUTH",
            "decision": decision,
            
            "subject": subject,
            "delegation_context": delegation_context,
            "resource": resource,
            "authorization": authorization,
            
            "risk_assessment": self._assess_risk(
                decision, authorization, delegation_context
            )
        }
        
        self.storage.save(audit_log)
        return audit_log["audit_id"]
    
    def query_by_trace_id(self, trace_id: str) -> List[dict]:
        """按trace_id查询完整调用链"""
        return self.storage.query({"trace_id": trace_id})
    
    def query_denied_events(
        self,
        time_range: tuple = None
    ) -> List[dict]:
        """查询所有拒绝事件"""
        query = {"decision": "DENY"}
        if time_range:
            query["timestamp"] = {
                "$gte": time_range[0],
                "$lte": time_range[1]
            }
        return self.storage.query(query)
    
    def _assess_risk(
        self,
        decision: str,
        authorization: dict,
        delegation_context: dict
    ) -> dict:
        """风险评估"""
        risk_score = 0
        risk_factors = []
        
        if decision == "DENY":
            risk_score += 20
            risk_factors.append("AUTHORIZATION_DENIED")
        
        if delegation_context and delegation_context.get("chain_depth", 0) > 3:
            risk_score += 30
            risk_factors.append("DEEP_DELEGATION_CHAIN")
        
        return {
            "risk_level": "HIGH" if risk_score >= 50 else "MEDIUM" if risk_score >= 30 else "LOW",
            "risk_score": risk_score,
            "risk_factors": risk_factors
        }
```

---

## 十二、文档提交清单

### 必需文档

1. **技术方案设计文档** (architecture.md)
   - 系统架构图
   - Access Token字段说明
   - A2A认证流程图
   - API接口定义

2. **安装与运行指南** (README.md)
   - 环境依赖
   - 安装步骤
   - 启动命令
   - 快速开始

3. **演示脚本** (demo-guide.md)
   - 正常流程演示步骤
   - 越权拦截演示步骤
   - 预期结果说明

4. **代码仓库**
   - 可运行代码
   - 配置文件
   - 测试用例

### 加分文档

- 协议规范文档 (protocol.md)
- 安全威胁分析 (security-analysis.md)
- 性能测试报告 (performance.md)
- 可视化演示视频

---

## 总结

这个方案的核心亮点:

1. **三层权限模型**: 静态授权 + 用户权限 + 动态计算，既保证安全又保持灵活性

2. **完整的信任链**: JWT嵌套设计，支持多层委托的可验证追溯

3. **结构化审计**: 全链路追踪 + 风险评估，满足企业级安全要求

4. **安全增强**: Token绑定、实时撤销、异常检测等多重防护

5. **可演示性强**: 清晰的正常流程和攻击拦截场景，便于验收

建议按照Phase 1-4的路线图逐步实现，确保每个阶段都有可演示的交付物。
