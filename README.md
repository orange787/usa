# Ops-Dev Requirement Bridge

运营 (Telegram) 与开发 (Lark/飞书) 之间的自动化需求对接系统。

运营人员在 Telegram Group 发布需求和反馈，开发团队在 Lark 上协作，GitHub Issues 作为统一的需求池管理平台。通过多 Agent 协作实现需求收集、整理、同步和进度追踪的自动化。

## 快速开始

```bash
git clone <repo-url> lark-TG-BOT
cd lark-TG-BOT

# 必须使用 Python 3.12（pydantic-core 与 3.13+ 不兼容）
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# 编辑 .env 填入各项配置（见下方详细说明）
# 编辑 config/whitelist.yaml 填入管理员 Telegram user ID

python -m src.main
```

## 系统架构

```
┌─────────────────────┐          ┌───────────────────┐          ┌─────────────────────┐
│   Telegram Group    │          │   GitHub Issues    │          │     Lark Group      │
│   (运营团队)         │          │   (需求池/SSoT)    │          │     (开发团队)       │
└────────┬────────────┘          └────────┬──────────┘          └────────┬────────────┘
         │                                │                              │
    TG Bot (收集)                    需求管理中枢                    Lark Bot (同步)
         │                                │                              │
         ▼                                ▼                              ▼
┌────────────────────────────────────────────────────────────────────────────────────┐
│                            Orchestrator (中枢调度)                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │  TG Listener │  │  Requirement │  │   GitHub     │  │    Lark Dispatcher     │ │
│  │    Agent     │  │  Analyst     │  │   Manager    │  │       Agent            │ │
│  │  (消息收集)   │  │  Agent       │  │   Agent      │  │  (需求推送 + 进度回收)  │ │
│  │              │  │  (需求提炼)   │  │  (需求池CRUD)│  │                        │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────────────────┘ │
│                         ┌──────────────┐                                           │
│                         │  Status Sync │                                           │
│                         │    Agent     │                                           │
│                         │  (状态双向同步)│                                           │
│                         └──────────────┘                                           │
└────────────────────────────────────────────────────────────────────────────────────┘
```

## 核心功能

### 工作流 1: 需求收集 (Telegram → GitHub → Lark)

1. 运营在 TG 群讨论需求
2. 关键词自动检测 或 手动 `/submit` 触发
3. LLM 分析对话 → 生成结构化需求（标题、描述、优先级、类型、验收标准）
4. TG 管理员审批（白名单机制）
5. 审批通过 → 自动创建 GitHub Issue（带 labels）
6. 自动推送到 Lark 开发群（交互式卡片）

### 工作流 2: 需求对齐 (Lark → GitHub → Telegram)

1. 开发团队在 Lark 讨论
2. LLM 分析讨论内容，提取需运营确认的问题
3. Lark 管理员审批问题列表
4. 问题归档到 GitHub Issue 评论
5. 推送到 TG 运营群等待回复

### 工作流 3: 状态同步与报告

- GitHub Issue 状态变更 → 自动通知 TG + Lark
- 每日定时生成需求状态日报
- 超时未处理需求自动升级提醒
- 版本发布自动生成变更日志

## 技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.12（推荐，3.13+ 不兼容） |
| Telegram Bot | python-telegram-bot v21 |
| Lark Bot | lark-oapi v1.5.3 (官方 SDK) |
| GitHub | PyGithub |
| LLM | Claude API / OpenAI API (可切换) |
| 事件总线 | 自研 async EventBus |
| 定时任务 | APScheduler |
| 消息队列 | Redis (AsyncIO EventBus) |
| 部署 | Docker Compose / 本地 + ngrok |

## 项目结构

```
lark-TG-BOT/
├── config/
│   ├── settings.yaml          # 全局配置（关键词、优先级、调度等）
│   ├── whitelist.yaml         # TG/Lark 管理员白名单
│   ├── labels.yaml            # GitHub label 体系定义
│   └── prompts/               # LLM prompt 模板
│       ├── requirement_extract.md
│       ├── priority_assess.md
│       └── daily_report.md
├── src/
│   ├── main.py                # 主入口
│   ├── core/
│   │   ├── config.py          # 配置加载
│   │   ├── models.py          # Pydantic 数据模型
│   │   ├── event_bus.py       # 异步事件总线
│   │   └── orchestrator.py    # 中枢调度器
│   ├── agents/
│   │   ├── tg_listener.py     # TG 消息收集 Agent
│   │   ├── requirement_analyst.py  # 需求分析 Agent
│   │   ├── github_manager.py  # GitHub 管理 Agent
│   │   ├── lark_dispatcher.py # Lark 对接 Agent
│   │   └── status_sync.py     # 状态同步 Agent
│   ├── bots/
│   │   ├── telegram_bot.py    # TG Bot 入口
│   │   └── lark_bot.py        # Lark Webhook 服务
│   ├── services/
│   │   ├── github_service.py  # GitHub API 封装
│   │   ├── lark_service.py    # Lark API 封装
│   │   └── llm/
│   │       ├── base.py        # LLM 抽象接口
│   │       ├── claude.py      # Claude 实现
│   │       ├── openai_llm.py  # OpenAI 实现
│   │       └── factory.py     # LLM 工厂
│   └── utils/
│       ├── message_parser.py  # 消息解析工具
│       └── template_engine.py # 模板渲染
├── tests/                     # 测试
├── scripts/
│   └── setup_github_labels.py # 初始化 GitHub labels
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

## 五个 Agent

| Agent | 职责 | 核心 Skills |
|-------|------|-------------|
| **TG Listener** | Telegram 消息收集与交互 | 消息捕获、关键词检测、Bot 命令、管理员审批 |
| **Requirement Analyst** | LLM 驱动的需求分析 | 需求提取、分类、优先级评估、冲突检测、文档生成 |
| **GitHub Manager** | GitHub Issues 需求池管理 | Issue CRUD、标签管理、状态流转、统计报告 |
| **Lark Dispatcher** | Lark/飞书对接 | 需求推送（交互卡片）、进度收集、管理员审批、提醒 |
| **Status Sync** | 三端状态同步 | 双向同步、日报生成、超时升级、变更日志 |

## Telegram Bot 命令

| 命令 | 功能 |
|------|------|
| `/submit` | 提交需求（基于最近 15 条聊天记录，LLM 分析提取） |
| `/status` | 查看进行中的需求列表 |
| `/list` | 查看所有需求列表 |
| `/help` | 显示帮助信息 |

关键词自动触发：在聊天中提到"需求"、"bug"、"紧急"等词时，Bot 自动识别并提示提交。

## Lark Webhook 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/lark/event` | POST | 接收 Lark 消息事件 |
| `/lark/card` | POST | 处理交互卡片按钮点击（接受/拒绝/讨论） |
| `/health` | GET | 健康检查 |

## GitHub Label 体系

系统使用分层 label 管理需求状态：

- **类型**: `type/feature`, `type/bug`, `type/data`, `type/event`, `type/optimization`
- **优先级**: `priority/P0` (紧急), `priority/P1` (高), `priority/P2` (中), `priority/P3` (低)
- **状态**: `status/todo` → `status/in-progress` → `status/review` → `status/done`
- **来源**: `source/ops`, `source/dev`
- **审批**: `approval/pending`, `approval/approved`, `approval/rejected`

---

# 部署指南

## 前置准备

### 1. 创建 Telegram Bot

1. 在 Telegram 中找到 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot`，按提示设置名称
3. 记录获得的 **Bot Token**
4. 将 Bot 添加到目标群组，并设为管理员
5. 获取群组 ID（可通过 [@userinfobot](https://t.me/userinfobot) 或 API 获取）

### 2. 创建 Lark/飞书应用

1. 登录 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 开启以下权限：
   - `im:message` — 发送消息
   - `im:message.receive_v1` — 接收消息
   - `im:chat` — 获取群信息
4. 记录 **App ID** 和 **App Secret**
5. 配置事件订阅：
   - 请求地址: `https://your-domain.com/lark/event`
   - 订阅事件: `im.message.receive_v1`
6. 配置卡片请求地址: `https://your-domain.com/lark/card`
7. 将应用 Bot 添加到目标群组

### 3. 创建 GitHub Token

1. 前往 [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)
2. 创建 Fine-grained token，权限选择：
   - **Issues**: Read and write
   - **Labels**: Read and write
   - **Metadata**: Read
3. 记录生成的 Token
4. 准备一个 GitHub 仓库作为需求池

### 4. 获取 LLM API Key

**Claude (推荐)**:
1. 前往 [Anthropic Console](https://console.anthropic.com/)
2. 创建 API Key

**OpenAI (可选)**:
1. 前往 [OpenAI Platform](https://platform.openai.com/)
2. 创建 API Key

## 本地部署

### Step 1: 克隆并安装依赖

```bash
git clone <repo-url> lark-TG-BOT
cd lark-TG-BOT

# 必须使用 Python 3.12（pydantic-core 与 3.13+ 不兼容）
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> **依赖说明**
> - `lark-oapi==1.5.3`：使用官方 SDK 最新版，1.4.x 在 PyPI 不存在
> - `aiohttp`：Lark Webhook 服务使用 aiohttp，SDK 的 aiohttp adapter 已在 1.5.x 移除，本项目直接解析 JSON
> - Redis 需提前启动：`brew install redis && brew services start redis`（macOS）

### Step 2: 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入实际值：

```env
# 必填 - Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_GROUP_ID=-1001234567890

# 必填 - GitHub
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_REPO=your-org/game-requirements

# 必填 - LLM (至少配置一个)
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx

# 可选 - Lark (不配置则跳过 Lark 功能)
LARK_APP_ID=cli_xxxxxxxxxxxx
LARK_APP_SECRET=xxxxxxxxxxxx
LARK_VERIFICATION_TOKEN=xxxxxxxxxxxx
LARK_ENCRYPT_KEY=xxxxxxxxxxxx
LARK_GROUP_CHAT_ID=oc_xxxxxxxxxxxx

# 可选 - Webhook (Lark 需要公网地址)
WEBHOOK_HOST=https://your-domain.com
WEBHOOK_PORT=8443
```

### Step 3: 配置管理员白名单

编辑 `config/whitelist.yaml`：

```yaml
telegram:
  admin_ids:
    - 123456789      # 你的 Telegram user ID
    - 987654321      # 其他管理员
  allowed_groups:
    - -1001234567890  # 运营群组 ID

lark:
  admin_ids:
    - "ou_xxxxxxxxxxxx"  # Lark 管理员 user ID
  allowed_chats:
    - "oc_xxxxxxxxxxxx"  # Lark 开发群 chat ID
```

### Step 4: 初始化 GitHub Labels

```bash
python scripts/setup_github_labels.py
```

这会在目标仓库中创建 20 个分类标签（类型、优先级、状态、来源、审批）。

### Step 5: 启动系统

```bash
python -m src.main
```

启动后你会看到：

```
2026-03-15 10:00:00 [INFO] src.main: Starting Ops-Dev Requirement Bridge System...
2026-03-15 10:00:00 [INFO] src.core.event_bus: EventBus started
2026-03-15 10:00:01 [INFO] src.main: GitHub labels initialized
2026-03-15 10:00:01 [INFO] src.main: Telegram bot started
2026-03-15 10:00:01 [INFO] src.main: Lark webhook server started
2026-03-15 10:00:01 [INFO] src.main: Scheduler started (digest at 10:00, escalation every 4h)
2026-03-15 10:00:01 [INFO] src.main: System is running. Press Ctrl+C to stop.
```

## 本地开发调试（ngrok）

Lark Webhook 需要公网 HTTPS 地址，本地开发可使用 [ngrok](https://ngrok.com) 做隧道：

```bash
# 安装 ngrok（macOS）
brew install ngrok

# 配置 authtoken（注册免费账号后获取）
ngrok config add-authtoken <your-authtoken>

# 启动隧道（暴露本地 8443 端口）
ngrok http 8443
```

ngrok 启动后会显示类似 `https://xxxx.ngrok-free.app` 的公网地址，将其填入 `.env`：

```env
WEBHOOK_HOST=https://xxxx.ngrok-free.app
WEBHOOK_PORT=8443
```

并在飞书开放平台配置：
- **事件订阅请求地址**: `https://xxxx.ngrok-free.app/lark/event`
- **卡片请求地址**: `https://xxxx.ngrok-free.app/lark/card`

> **注意**: ngrok 免费版每次重启地址会变化，需重新配置飞书回调地址。付费版可绑定固定域名。

## Docker 部署

### Step 1: 准备配置

```bash
cp .env.example .env
# 编辑 .env 填入实际值（同上）
# 编辑 config/whitelist.yaml 填入管理员 ID
```

### Step 2: 构建并启动

```bash
docker-compose up -d
```

### Step 3: 查看日志

```bash
docker-compose logs -f bot
```

### Step 4: 停止服务

```bash
docker-compose down
```

## 生产部署建议

### 反向代理 (Nginx)

Lark Webhook 需要 HTTPS 公网地址。配置 Nginx：

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate     /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /lark/ {
        proxy_pass http://127.0.0.1:8443;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /health {
        proxy_pass http://127.0.0.1:8443;
    }
}
```

### 系统服务 (systemd)

```ini
[Unit]
Description=Ops-Dev Requirement Bridge
After=network.target redis.service

[Service]
Type=simple
User=deploy
WorkingDirectory=/opt/lark-TG-BOT
ExecStart=/opt/lark-TG-BOT/.venv/bin/python -m src.main
Restart=always
RestartSec=10
EnvironmentFile=/opt/lark-TG-BOT/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo cp ops-dev-bridge.service /etc/systemd/system/
sudo systemctl enable ops-dev-bridge
sudo systemctl start ops-dev-bridge
```

## 自定义配置

### 修改触发关键词

编辑 `config/settings.yaml`：

```yaml
telegram:
  trigger_keywords:
    - "需求"
    - "bug"
    - "紧急"
    # 添加更多关键词...
```

### 修改定时任务

```yaml
scheduling:
  daily_digest_hour: 10     # 日报发送小时 (24h)
  daily_digest_minute: 0    # 日报发送分钟
  escalation_timeout_hours: 48  # 超时升级阈值
```

### 切换 LLM Provider

在 `.env` 中修改：

```env
LLM_PROVIDER=openai     # 切换为 OpenAI
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-4o
```

### 调整 LLM 温度参数

```yaml
llm:
  temperatures:
    requirement_extract: 0.3  # 需求提取（低温度 = 更精确）
    priority_assess: 0.2      # 优先级评估
    summarize: 0.5            # 摘要生成
    report: 0.4               # 报告生成
```

## 测试

```bash
# 运行所有测试
pytest

# 详细输出
pytest -v

# 带覆盖率
pytest --cov=src

# 运行特定测试
pytest tests/test_event_bus.py
pytest -k test_extract_requirement
```

## 验证清单

部署完成后，按以下顺序验证：

1. **TG Bot 基础**: 在群组中发送 `/help`，确认 Bot 响应
2. **需求提交**: 在群组讨论后发送 `/submit`，确认 Bot 返回需求摘要
3. **管理员审批**: 回复审批消息 `approve`，确认 GitHub Issue 创建
4. **GitHub 检查**: 验证 Issue 标签正确（type、priority、status、source）
5. **Lark 推送**: 确认 Lark 群收到交互式卡片
6. **Lark 交互**: 点击卡片按钮，确认 GitHub Issue 状态更新
7. **状态同步**: 修改 GitHub Issue 标签，确认 TG 和 Lark 收到通知
8. **日报**: 等待定时触发或手动验证日报格式

## 常见问题

### Lark 配置

**Q: 飞书事件回调一直提示 Challenge 验证失败？**

A: 确认飞书应用「安全设置」中的 Encrypt Key 已清空（留空），并将 `.env` 中 `LARK_ENCRYPT_KEY=` 也设置为空值。加密模式下需要正确的解密逻辑，开发阶段建议关闭加密。

**Q: 飞书机器人发消息提示权限不足？**

A: 在飞书开放平台 → 权限管理，开通以下权限并重新发版：
- `im:message` — 获取与发送单聊、群组消息
- `im:message:send_as_bot` — 以应用的身份发消息

**Q: 在群组中找不到刚创建的机器人？**

A: 进入飞书开放平台 → 应用详情 → 版本管理与发布，将应用可见范围设为「全员」并发布版本。

**Q: 点击卡片按钮提示「出错了 code 200304」？**

A: 需要在飞书开放平台配置「卡片请求地址」：
- 路径：消息卡片 → 卡片搭建工具 → 配置 → 请求地址
- 填入：`https://your-domain.com/lark/card`

### Python 环境

**Q: 安装依赖时 pydantic-core 编译失败？**

A: 使用 Python 3.12，不支持 Python 3.13+。

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Q: 启动提示 Redis 连接失败？**

A: 启动 Redis 服务：

```bash
# macOS
brew services start redis

# Linux
sudo systemctl start redis
```

### Telegram Bot

**Q: Bot 不响应群组消息？**

A: 确认 Bot 已被设为群管理员，或在 BotFather 中关闭 Privacy Mode（`/setprivacy` → `Disable`）。

**Q: 发送 `/submit` 后 Telegram 管理员收不到审批消息？**

A: 检查 `config/whitelist.yaml` 中 `admin_ids` 是否填入了正确的 Telegram 用户数字 ID（不是用户名）。可通过 [@userinfobot](https://t.me/userinfobot) 获取。

## License

MIT
