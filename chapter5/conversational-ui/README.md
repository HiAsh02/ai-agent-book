# 实验 5-11：对话式界面定制系统（★★）

用户用**自然语言**提出 UI 定制需求（颜色 / 字体 / 文案 / 布局 / 组件位置），
Agent 自主**定位并修改前端源码**，开发模式下的**热加载（HMR）**让改动即时生效，
支持多轮迭代定制。

## 目的

把"一刀切"的标准前端，变成"千人千面"的可对话定制界面：

- 基础 chatbot 应用 = **React(Vite) 前端 + FastAPI 后端**；
- 前后端都跑在开发模式：前端 Vite **HMR**、后端 uvicorn **--reload**；
- 用户说"把发送按钮改成蓝色 / 换成等宽字体 / 标题改成 XXX"，
  Agent（OpenAI，默认 `gpt-4o-mini`）读懂需求 → 改 `frontend/src` 里的源码文件；
- 热加载检测到文件变化，浏览器无需整页刷新即可看到界面变化。

## 关于热加载（HMR）

- **前端**：`npm run dev` 启动的 Vite dev server 自带 HMR。Agent 一改 `src/*.jsx`
  或 `src/theme.css`，浏览器局部热替换、保留应用状态，界面即时更新。
- **后端**：`uvicorn main:app --reload` 监听 `.py` 变化自动重启。
- 本实验的定制主要作用于前端源码，所以视觉效果靠前端 HMR 体现。

## 目录结构

```
conversational-ui/
├── frontend/                 # React + Vite 前端（基础 chatbot 界面）
│   ├── src/App.jsx           #   界面与 UI 文案（Agent 改"文案/组件"）
│   ├── src/theme.css         #   颜色/字体/布局样式（Agent 改"样式"）
│   ├── src/main.jsx
│   ├── index.html
│   ├── vite.config.js        #   开启 HMR + /api 代理到后端
│   └── package.json
├── backend/
│   ├── main.py               # FastAPI 后端（/api/chat）
│   └── requirements.txt
├── baseline/src/             # 前端源码初始快照（demo 每次运行前恢复，保证可重复）
├── agent.py                  # 定制 Agent：NL 需求 → 用 OpenAI 改写源码
├── demo.py                   # 端到端演示 + 自动验证（NL→代码→断言→构建）
├── requirements.txt          # 后端 + Agent 依赖
├── env.example
└── .gitignore                # node_modules / dist / .env 均已忽略
```

## 运行方式

### 1) 准备环境

```bash
# Python 依赖（Agent + 后端）
pip install -r requirements.txt

# 前端依赖（首次 npm install 较慢属正常）
cd frontend && npm install && cd ..

# 配置 OpenAI Key
cp env.example .env   # 然后填入 OPENAI_API_KEY
```

### 2) 自动验证闭环（无需浏览器）

```bash
python demo.py
```

`demo.py` 会连续跑 3 轮自然语言定制，每轮：
调用真实 OpenAI 改写源码 → 打印改动 diff → 读回源码断言"改动符合需求" →
`vite build` 验证"没破坏应用"。

### 3) 手动体验真实 HMR（可选，需要浏览器）

```bash
# 终端 A：后端（热加载）
cd backend && uvicorn main:app --reload --port 8000

# 终端 B：前端（HMR）
cd frontend && npm run dev
# 打开 http://localhost:5173

# 终端 C：跑一条定制需求，回到浏览器即可看到界面即时变化
python -c "import agent,pathlib; c,m=agent.build_client_and_model(); \
r=agent.customize(c,m,pathlib.Path('frontend'),'把发送按钮改成橙色'); \
[pathlib.Path('frontend',f['path']).write_text(f['content']) for f in r['files']]"
```

## 验证方式与局限

- **本 demo 自动验证的是**：自然语言 → 代码修改被**正确应用**且**不破坏构建**的闭环。
  - 读回源码断言：如"改成蓝色 #2563eb"→ 源码里确实出现该色值；
    "换成等宽字体"→ 出现 `monospace`；"标题改成 XXX"→ 出现该文案。
  - 每轮改动后 `vite build` 必须编译通过，证明改动没破坏应用。
- **本 demo 不做的**：真实浏览器内 HMR 的**视觉**即时刷新。
  本机无 Playwright/浏览器，无法自动截图验证视觉效果——
  这部分需手动 `npm run dev` + 打开浏览器查看（见上文第 3 步）。
- Agent 只被允许改写白名单文件（`src/App.jsx`、`src/theme.css`），
  降低改错文件的风险；改写采用"整文件重写"，对小文件比零散替换更稳。

## 真实运行输出（节选）

```
第 1 轮 NL 定制需求：把发送按钮和用户消息气泡的主题色从绿色改成蓝色，用 #2563eb 这个蓝。
[改动文件] src/theme.css
  - --color-primary: #16a34a;   /* 初始为绿色 */
  + --color-primary: #2563eb;   /* 改为蓝色 */
断言：源码中出现蓝色值 #2563eb -> 通过 ✅
构建结果：通过 ✅

第 2 轮 NL 定制需求：把整个界面的字体换成等宽字体（monospace）。
[改动文件] src/theme.css
  - --font-family: system-ui, "PingFang SC", ... sans-serif;
  + --font-family: monospace;
断言：源码中出现 monospace 等宽字体 -> 通过 ✅
构建结果：通过 ✅

第 3 轮 NL 定制需求：把顶部的标题文案改成"我的专属客服"。
[改动文件] src/App.jsx
  - const HEADER_TITLE = "智能助手";
  + const HEADER_TITLE = "我的专属客服";
断言：源码中出现新标题文案"我的专属客服" -> 通过 ✅
构建结果：通过 ✅

多轮定制总结：全部通过 ✅
```

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `OPENAI_API_KEY` | 必填，本实验读取此项 |
| `OPENAI_BASE_URL` | 可选，切换到兼容 OpenAI 协议的服务端点 |
| `MODEL` | 可选，默认 `gpt-4o-mini` |
