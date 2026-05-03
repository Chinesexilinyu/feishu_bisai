# Access Token字段说明
## 基本信息
| 项 | 值 |
|----|----|
| 标准 | JWT (JSON Web Token) |
| 签名算法 | RS256 (RSA-SHA256非对称加密) |
| 有效期 | 默认7200秒（2小时） |
| 长度 | 约300~500字符（随权限内容长度变化） |
| 生成位置 | 认证服务TokenIssuer模块 |
| 验证位置 | 各Agent服务auth_middleware中间件 |

## 字段详细说明
| 字段名称 | 数据类型 | 必填 | 说明 |
|----------|----------|------|------|
| iss | String | 是 | 签发者，固定值：`agent-auth-service` |
| sub | String | 是 | 主体，即Agent ID，如：`doc_agent_001` |
| aud | String | 是 | 受众，固定值：`agent-service` |
| iat | Integer | 是 | 签发时间戳（Unix秒级时间戳） |
| exp | Integer | 是 | 过期时间戳，签发时间+有效期 |
| jti | String | 是 | Token唯一ID，UUID v4格式，用于Token吊销 |
| agent_id | String | 是 | Agent唯一标识 |
| agent_role | String | 是 | Agent角色：`admin`/`service`/`user` |
| agent_name | String | 是 | Agent显示名称，如：`飞书文档助手Agent` |
| capabilities | Array<String> | 是 | 权限列表，如：`["doc:read", "bitable:write", "web:search"]` |
| delegated_user | Object | 否 | 委托用户信息，包含用户ID、名称、权限等 |
| chain_of_trust | Array<Object> | 否 | 信任链，记录Token传递路径，包含每一层的Agent ID、类型、操作、时间戳 |
| parent_token_id | String | 否 | 父Token ID，用于关联上下游调用 |

## 生成规则
1. 每次Agent发起跨服务调用前，向认证服务申请Token
2. Token包含当前Agent的身份信息、权限范围、委托用户上下文
3. 采用RSA私钥签名，只有认证服务持有私钥，公钥公开给所有服务用于验证
4. Token唯一ID（jti）存储于吊销列表，支持主动吊销

## 安全策略
1. **签名验证**：所有服务必须验证Token签名，拒绝签名无效的请求
2. **有效期检查**：Token默认有效期2小时，过期必须重新申请
3. **Token吊销**：支持通过jti主动吊销Token，吊销后立即失效
4. **信任链验证**：多级调用时验证信任链完整性，防止越权调用
5. **权限最小化**：Token仅包含当前调用所需的最小权限集
6. **无静态存储**：Token动态生成，不存储于配置文件或代码中
7. **传输加密**：Token仅通过HTTPS/内部安全信道传输，不暴露于公网
