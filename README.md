# AI Test Case Generator

一个基于 `Streamlit + LangGraph + LangChain + Chroma + OpenAI-Compatible LLM` 的 AI 测试用例生成工具。

它的目标是把“需求文档 -> 需求分析 -> 测试点 -> 测试大纲 -> 测试用例 -> Excel 导出”这一整条链路串起来，并且允许你在关键阶段做人审和修改。

这份 README 面向零基础同学编写。你不需要先懂 LangGraph、RAG、向量库、Prompt Engineering，也可以按步骤把项目跑起来，并理解代码每一部分在做什么。

---

## 1. 项目能做什么

这个项目当前已经具备以下核心能力：

- 上传需求文档，支持 `Markdown(.md)` 和 `Word(.docx)`
- 自动解析文档结构
- 将需求文档切块并写入本地向量库
- 基于 RAG 检索需求依据
- 支持混合检索：向量召回 + BM25 召回 + RRF 融合
- 用大模型生成需求分析
- 从需求分析中提取测试点
- 基于测试点生成测试大纲
- 基于测试大纲生成测试用例
- 支持上传历史测试用例知识库，辅助生成新用例
- 支持对每个阶段结果进行人工审核和修改
- 导出 Excel 测试用例文件
- 展示每个阶段的检索依据、引用、rerank 状态和降级原因

---

## 2. 项目整体流程

从产品视角看，这个项目的执行流程是：

1. 用户上传需求文档
2. 系统解析文档结构
3. 系统把解析后的文档切块并入库
4. 系统检索与“需求分析”相关的文档片段
5. LLM 生成需求分析
6. 用户审核需求分析
7. 系统检索与“测试点提取”相关的文档片段
8. LLM 生成测试点
9. 用户审核测试点
10. 系统检索与“测试大纲”相关的文档片段
11. LLM 生成测试大纲
12. 用户审核测试大纲
13. 系统检索需求依据和历史用例依据
14. LLM 生成测试用例
15. 用户审核测试用例
16. 系统导出 Excel

从代码视角看，这条链路主要由下面几部分组成：

- Web 界面：`app/app.py`
- 工作流编排：`workflow/workflow.py`
- 工作流节点：`workflow/nodes.py`
- 文档解析：`utils/document_parser/`
- 向量入库：`rag/ingest.py`
- 文档检索：`rag/retriever.py`
- 重排 rerank：`rag/reranker.py`
- Prompt + 结构化输出：`skills/test_design_skills.py`
- Excel 导出：`utils/excel_exporter/excel_exporter.py`

### 2.1 架构图

```mermaid
flowchart LR
    ENV[Environment<br/>需求文档 / 历史测试用例 / 人工审核反馈]

    subgraph SYS["AI Test Case Generator"]
        direction TB

        P[Perception<br/>文档解析 / 状态读取 / 审核输入]
        PLAN[Planning<br/>LangGraph Workflow]
        CORE[The "Augmented" LLM<br/>需求分析 / 测试点 / 大纲 / 用例生成]
        A[Action<br/>阶段推进 / 结果输出 / Excel 导出]

        TOOLS[Tools<br/>Query 扩展 / 向量召回 / BM25 / RRF / Rerank]
        MEM[Memory<br/>Chroma 向量库 / 历史用例知识库]

        P --> CORE
        PLAN --> CORE
        CORE --> A
        CORE --- TOOLS
        CORE --- MEM
        PLAN -.循环迭代.-> CORE
    end

    ENV --> P
    A --> ENV
    MEM --> CORE
    A --> MEM
```

---

## 3. 适合谁使用

这个项目适合：

- 测试工程师
- 测试开发工程师
- 产品经理
- 希望用 AI 辅助测试设计的开发者
- 想学习 LangGraph + RAG 实战项目的人

---

## 4. 项目目录结构

```text
ai-test-case-generator/
├─ app/
│  └─ app.py                         # Streamlit Web 入口
├─ data/
│  └─ chroma/                        # Chroma 向量库持久化目录
├─ output/                           # 导出的 Excel 文件
├─ rag/
│  ├─ config.py                      # RAG 配置
│  ├─ ingest.py                      # 文档入库
│  ├─ query_expander.py              # Query 扩展
│  ├─ reranker.py                    # Rerank 排序
│  ├─ retriever.py                   # 检索逻辑
│  ├─ schemas.py                     # Chunk / Citation 数据结构
│  ├─ store.py                       # 向量库与 Embedding 初始化
│  ├─ index_testcase_kb.py           # 历史测试用例批量入库脚本
│  └─ eval_offline.py                # 离线检索验证脚本
├─ skills/
│  ├─ analyze_requirement_skill.md   # 需求分析 Prompt
│  ├─ extract_test_points_skill.md   # 测试点提取 Prompt
│  ├─ generate_outline_skill.md      # 测试大纲 Prompt
│  ├─ generate_cases_skill.md        # 测试用例 Prompt
│  └─ test_design_skills.py          # Prompt 调用与结构化输出封装
├─ utils/
│  ├─ document_parser/
│  │  ├─ parser.py                   # 文档结构基础数据结构
│  │  ├─ md_parser.py                # Markdown 解析
│  │  ├─ docx_parser.py              # DOCX 解析
│  │  └─ run_parser_demo.py          # 文档解析演示脚本
│  └─ excel_exporter/
│     └─ excel_exporter.py           # Excel 导出工具
├─ workflow/
│  ├─ state.py                       # LangGraph 状态定义
│  ├─ schemas.py                     # TestPoint / TestOutline / TestCase 结构
│  ├─ nodes.py                       # 各工作流节点实现
│  ├─ workflow.py                    # LangGraph 工作流定义
│  └─ main_test.py                   # 工作流验证脚本
├─ .env                              # 你的本地环境变量
├─ .env.example                      # 环境变量模板
└─ README.md                         # 当前文档
```

---

## 5. 运行前你需要准备什么

### 5.1 Python 环境

建议：

- Python 3.10+
- Windows / macOS / Linux 都可以

当前你的环境里已经用的是 Python 3.12，所以 Python 3.12 是可以跑的。

### 5.2 模型 API

你至少需要一个 OpenAI 兼容接口：

- OpenAI 官方接口
- 或者 OpenAI-Compatible 接口
- 或者公司内部兼容 OpenAI 的代理服务

项目里用到两个模型能力：

- 聊天模型：生成需求分析、测试点、大纲、测试用例
- Embedding 模型：做向量检索

注意：

- 聊天模型必须可用，否则工作流会卡在 LLM 调用阶段
- Embedding 模型不可用时，项目有本地兜底 `LocalHashEmbeddings`

### 5.3 可选的本地 rerank 模型

当前默认 `rerank` 配置是：

- `RERANK_MODE = "cross_encoder"`
- `RERANK_CROSS_ENCODER_MODEL = "BAAI/bge-reranker-v2-m3"`

这表示系统会优先使用本地 cross-encoder 重排。

如果模型：

- 本地没有缓存
- 无法联网下载
- 加载失败
- 推理超时

系统会自动回退到 `lite` 模式。

---

## 6. 安装与启动

### 6.1 安装依赖

如果你有 `requirements.txt`，通常可以：

```bash
pip install -r requirements.txt
```

如果项目里没有整理好的依赖文件，你至少需要这些核心依赖：

```bash
pip install streamlit python-dotenv langchain langchain-openai langgraph chromadb openpyxl mistune python-docx sentence-transformers
```

### 6.2 配置环境变量

复制 `.env.example` 为 `.env`：

```bash
copy .env.example .env
```

然后编辑 `.env`：

```env
# OpenAI API Key（请替换为你自己的真实密钥）
OPENAI_API_KEY=your_openai_api_key_here

# OpenAI / OpenAI-Compatible Base URL（官方默认可用 https://api.openai.com/v1）
OPENAI_BASE_URL=your_openai_base_url_here
```

### 6.3 启动 Web 应用

在项目根目录执行：

```bash
streamlit run app/app.py
```

启动后，浏览器会自动打开一个本地页面。

---

## 7. 如何使用这个系统

### 7.1 第一步：上传需求文档

在 Web 页面点击上传，支持：

- `.md`
- `.docx`

点击“开始生成”后，系统会：

1. 解析文档
2. 生成 `doc_id`
3. 把结构化文档写入向量库
4. 进入“需求分析”阶段

### 7.2 第二步：审核需求分析

系统会生成一段需求分析文本。

你可以：

- 直接通过
- 手动修改后再通过
- 点击“重新生成需求分析”

通过后系统进入“测试点提取”阶段。

### 7.3 第三步：审核测试点

系统会生成测试点表格，每条包含：

- 测试点名称
- 测试类型
- 优先级

你可以：

- 新增测试点
- 删除测试点
- 修改优先级
- 修改类型

### 7.4 第四步：审核测试大纲

系统会把测试点整理成按模块分组的测试大纲。

你可以调整：

- 模块名称
- 模块下的测试点
- 优先级和类型

### 7.5 第五步：审核测试用例

系统会生成结构化测试用例。

每条用例包括：

- `case_id`
- `directory`
- `case_level`
- `test_point`
- `precondition`
- `steps`
- `expected_result`

### 7.6 第六步：导出 Excel

审核完成后，点击导出。

系统会把用例写入 `output/` 目录，并提供下载按钮。

### 7.7 可选：上传历史测试用例知识库

在侧边栏可以上传历史测试用例文档，用于帮助新用例生成。

支持：

- 多文件上传
- `md` 和 `docx`
- 附加元数据：
  - `module`
  - `test_type`
  - `priority`

---

## 8. 关键配置说明

配置主要在 [rag/config.py]

### 8.1 向量库配置

- `PERSIST_DIRECTORY`
  向量库存储目录，默认是 `data/chroma`

- `COLLECTION_NAME`
  Chroma 的集合名称

### 8.2 文本切块配置

- `CHUNK_SIZE = 500`
  每个 chunk 最大字符数

- `CHUNK_OVERLAP = 80`
  chunk 之间的重叠字符数

### 8.3 检索配置

- `RETRIEVER_TOP_K = 8`
  默认最多拿多少条结果

- `FETCH_K = 20`
  MMR 搜索时先取多少候选

- `SEARCH_TYPE = "mmr"`
  当前使用最大边际相关性搜索

- `HYBRID_SEARCH_ENABLED = True`
  是否启用混合检索。开启后会同时执行向量召回和 BM25 召回，再做融合

- `BM25_TOP_K = 8`
  BM25 路径最多保留多少条候选结果

- `RRF_K = 60`
  RRF 融合参数。值越大，不同召回路数之间的排名差异会被拉平一些

### 8.4 Query 扩展配置

- `MULTI_QUERY_ENABLED = True`
  是否启用多 query 扩展

- `QUERY_COUNT = 3`
  最多生成多少条 query

- `PER_QUERY_TOP_K = 3`
  每条扩展 query 分别召回多少条结果

### 8.5 Rerank 配置

- `ENABLE_RERANK = True`
  是否启用 rerank

- `RERANK_MODE = "cross_encoder"`
  默认优先用强 rerank

- `RERANK_CROSS_ENCODER_MODEL = "BAAI/bge-reranker-v2-m3"`
  cross-encoder 模型名

- `RERANK_CROSS_ENCODER_LOCAL_FILES_ONLY = True`
  是否只从本地缓存加载模型

- `RERANK_TIMEOUT_MS = 30000`
  rerank 超时时间

- `RERANK_CANDIDATE_POOL = 12`
  重排前最多放多少候选

- `RERANK_FINAL_TOP_N = 5`
  重排后最终保留多少条

---

## 9. 核心模块详细说明

## 9.1 Web 层：`app/app.py`

这个文件是整个项目的 Web 入口，负责：

- 页面展示
- 用户操作
- 会话状态
- 调工作流
- 展示检索证据
- 展示导出结果

### 核心函数说明

#### `get_graph_and_llm()`

作用：

- 读取 `.env`
- 初始化 `ChatOpenAI`
- 创建 LangGraph 工作流

它是整个系统的启动入口之一。

#### `_ensure_session()`

作用：

- 初始化 `st.session_state`
- 保证页面刷新时必要状态仍然存在

主要初始化：

- 当前阶段
- 当前线程 ID
- 当前源文档
- 当前表格数据
- rerank / multi-query 开关

#### `_parse_uploaded_document(uploaded_file)`

作用：

- 判断上传文件是 `md` 还是 `docx`
- 调用对应解析器
- 返回：
  - 原始文档表示
  - 结构化文档 `structured_doc`

#### `_run_with_progress(task_label, fn)`

作用：

- 包一层 Streamlit 进度条
- 在执行耗时任务时给用户反馈

这能避免用户误以为系统卡死。

#### `_replay_to_phase(graph, llm, target_phase)`

作用：

- 从已上传文档重新推演到某个阶段

例如刚上传完文档后，它会按顺序把前几个节点跑完，直到进入指定阶段。

#### `_rerun_current_phase(graph, llm, phase)`

作用：

- 针对当前阶段单独重跑

例如：

- 只重跑需求分析
- 只重跑测试点
- 只重跑测试大纲
- 只重跑测试用例

#### `_render_upload_page()`

作用：

- 渲染上传页面
- 接收上传文件
- 调用文档入库
- 进入下一阶段

#### `_render_testcase_kb_uploader()`

作用：

- 上传历史测试用例知识库
- 给历史用例打元数据标签
- 调用 `index_testcase_knowledge_file()`

#### `_render_retrieval_evidence()`

作用：

- 展示当前阶段的检索证据

包括：

- query
- expanded queries
- 候选数
- rerank 模式
- rerank 耗时
- 是否降级
- 降级原因
- 命中的 citations
- 命中的全文片段

这是调试和解释 AI 行为最重要的页面函数之一。

#### `_render_requirement_page()`

作用：

- 展示需求分析结果
- 支持人工编辑
- 通过后进入测试点提取

#### `_render_test_points_page()`

作用：

- 展示测试点表格
- 支持人工编辑
- 通过后进入测试大纲

#### `_render_outline_page()`

作用：

- 展示测试大纲
- 支持人工编辑
- 通过后进入测试用例生成

#### `_render_case_page()`

作用：

- 展示测试用例表格
- 支持人工编辑
- 通过后导出 Excel

#### `_render_download_page()`

作用：

- 提供 Excel 下载按钮
- 支持开始新一轮生成

#### `main()`

作用：

- Streamlit 程序主入口
- 初始化页面
- 加载工作流
- 根据当前阶段渲染不同页面

---

## 9.2 工作流层：`workflow/workflow.py`

这个文件定义 LangGraph 工作流。

### `create_workflow()`

作用：

- 创建一个有状态流程图
- 注册 5 个节点
- 指定节点执行顺序
- 指定在哪些节点前允许中断，等待人工审核

执行顺序：

1. `analyze_requirement_node`
2. `extract_test_points_node`
3. `generate_outline_node`
4. `generate_cases_node`
5. `export_excel_node`

中断点：

- 提取测试点前
- 生成大纲前
- 生成测试用例前
- 导出前

也就是说，系统是“AI 先生成，用户审核，再继续”。

---

## 9.3 状态层：`workflow/state.py`

### `TestCaseState`

这是 LangGraph 的共享状态对象，所有节点都通过它交换数据。

关键字段：

- `document`
  原始文档内容

- `structured_doc`
  结构化文档树

- `doc_id`
  当前文档在向量库中的唯一 ID

- `requirement_analysis`
  需求分析文本

- `test_points`
  测试点列表

- `test_outline`
  测试大纲

- `modified_outline`
  人工修改后的测试大纲

- `test_cases`
  AI 生成的测试用例

- `modified_test_cases`
  人工修改后的测试用例

- `retrieval_logs`
  所有阶段的检索日志

- `excel_output_path`
  最终导出的文件路径

---

## 9.4 结构定义：`workflow/schemas.py`

### `TestPoint`

一个测试点包含：

- `name`
- `test_type`
- `priority`

### `TestOutline`

一个测试大纲模块包含：

- `module_name`
- `test_points`

### `TestCase`

一条测试用例包含：

- `case_id`
- `directory`
- `case_level`
- `test_point`
- `precondition`
- `steps`
- `expected_result`

这些 Pydantic 模型的作用是：

- 约束 LLM 输出结构
- 保证前后端处理一致
- 降低脏数据带来的风险

---

## 9.5 节点层：`workflow/nodes.py`

这个文件定义了工作流中每个阶段实际要做什么。

### `_append_retrieval_log(...)`

作用：

- 把一次检索过程记录成日志

日志内容包括：

- 当前阶段
- query
- expanded queries
- 候选数
- hits
- citations
- rerank 模式
- rerank 是否降级
- rerank 降级原因

### `_truncate_for_query(text, limit=600)`

作用：

- 截断过长文本
- 避免 query 过长导致检索质量下降

### `_build_retrieval_for_phase(...)`

作用：

- 给当前阶段发起一次标准检索
- 获取检索片段
- 记录检索日志
- 返回可直接注入 Prompt 的上下文字符串

### `analyze_requirement_node(...)`

作用：

- 先检索与“业务流程 / 约束 / 依赖 / 异常 / 非功能”相关的内容
- 再调用 `analyze_requirement_skill()`
- 输出需求分析文本

### `extract_test_points_node(...)`

作用：

- 先检索与“正常流程 / 边界 / 异常 / 权限 / 校验”相关内容
- 再调用 `extract_test_points_skill()`
- 输出测试点列表

### `generate_outline_node(...)`

作用：

- 先检索与“模块 / 用户路径 / 状态流转 / 异常分支”相关内容
- 再调用 `generate_outline_skill()`
- 输出测试大纲

### `generate_cases_node(...)`

作用：

- 分两路检索：
  - 一路从需求库检索“测什么”
  - 一路从历史用例库检索“怎么写”
- 把两路上下文拼接后传给 `generate_cases_skill()`
- 输出测试用例

这是整个系统里最复杂、也最关键的一个节点。

### `export_excel_node(...)`

作用：

- 取出最终测试用例
- 调用 Excel 导出器
- 返回 Excel 路径

---

## 9.6 Skill 层：`skills/test_design_skills.py`

这个文件是“Prompt + LLM + Pydantic 输出”的核心封装。

### `RequirementAnalysisOutput`

定义需求分析结构输出，字段：

- `requirement_analysis`

### `TestPointListOutput`

定义测试点列表结构输出，字段：

- `test_points`

### `TestOutlineListOutput`

定义测试大纲结构输出，字段：

- `test_outline`

### `TestCaseListOutput`

定义测试用例结构输出，字段：

- `test_cases`

### `_load_prompt_template(file_name)`

作用：

- 从 `skills/*.md` 读取 Prompt 模板

### `_extract_text_content(content)`

作用：

- 兼容不同模型返回格式
- 把返回值统一抽成纯文本

### `_extract_json_object(raw_text)`

作用：

- 从模型输出中提取最像 JSON 对象的那一段

### `_sanitize_json_text(json_text)`

作用：

- 对常见脏 JSON 做轻量清洗

当前主要处理：

- 中文弯引号
- BOM
- 字符串内未转义双引号

它的目标不是做通用 JSON 解析器，而是降低大模型偶发输出坏 JSON 的失败率。

### `_repair_json_with_llm(...)`

作用：

- 如果 JSON 仍然不合法，调用 LLM 把坏 JSON 修复成合法 JSON

### `_invoke_json_fallback(...)`

作用：

- 当 `with_structured_output()` 不兼容时，降级到“纯 JSON 文本输出 + 手工解析”

处理顺序：

1. 调模型拿原始 JSON 文本
2. 提取 JSON 对象
3. 轻量清洗
4. 直接解析
5. 如果还失败，就让 LLM 进行 repair

### `_invoke_structured_output(...)`

作用：

- 优先走 LangChain 的 `with_structured_output`
- 如果失败，自动走 `_invoke_json_fallback`

### `analyze_requirement_skill(...)`

作用：

- 调用需求分析 Prompt
- 返回字符串形式的需求分析

### `extract_test_points_skill(...)`

作用：

- 调用测试点提取 Prompt
- 返回 `TestPoint` 列表

### `generate_outline_skill(...)`

作用：

- 调用测试大纲 Prompt
- 返回 `TestOutline` 列表

### `generate_cases_skill(...)`

作用：

- 调用测试用例生成 Prompt
- 返回 `TestCase` 列表

---

## 9.7 文档解析层：`utils/document_parser/`

### `parser.py`

#### `DocumentSection`

这是整个文档解析的基础数据结构。

一个 `DocumentSection` 包含：

- `level`
  标题层级

- `title`
  标题名

- `content`
  正文内容

- `tables`
  表格内容

- `children`
  子章节

### `md_parser.py`

#### `parse_markdown(markdown_text)`

作用：

- 使用 `mistune` 把 Markdown 转成 AST
- 按标题层级组装成 `DocumentSection` 树
- 保留表格内容

辅助函数：

- `_append_text()`
  追加正文文本

- `_render_text_from_children()`
  从 token 子节点还原文本

- `_token_to_text()`
  把 mistune token 转成普通文本

- `_extract_markdown_table()`
  抽取 Markdown 表格内容

### `docx_parser.py`

#### `parse_docx(docx_file)`

作用：

- 使用 `python-docx` 读取 Word 文件
- 识别标题样式
- 按标题层级构建 `DocumentSection` 树
- 保留表格内容

辅助函数：

- `_append_text()`
  追加正文内容

- `_heading_level_from_style()`
  根据 Word 样式名判断标题级别

- `_iter_docx_blocks()`
  顺序遍历 Word 中的段落和表格

---

## 9.8 入库层：`rag/ingest.py`

这个文件负责把结构化文档变成向量库里的 chunk。

### `_chunk_text(text, chunk_size, chunk_overlap)`

作用：

- 把长文本按固定长度切块
- 控制重叠区间

### `_join_path(path_parts)`

作用：

- 把章节路径拼成：
  `ROOT > 一级标题 > 二级标题`

### `_table_to_lines(table)`

作用：

- 把二维表格转成一行行文本

### `_walk_sections(...)`

作用：

- 递归遍历 `structured_doc`
- 把正文和表格都转成 `Chunk`

### `_build_documents(chunks)`

作用：

- 把内部 `Chunk` 对象转成 LangChain 的 `Document`
- 附带 metadata

### `index_document(...)`

作用：

- 把一个结构化文档写入向量库
- 返回写入的 chunk 数

### `index_document_from_json(...)`

作用：

- 从 JSON 字符串反序列化后再入库

### `index_testcase_knowledge_file(...)`

作用：

- 把历史测试用例文件入库到 `testcase` 类型知识库

---

## 9.9 向量库层：`rag/store.py`

### `LocalHashEmbeddings`

作用：

- 本地 deterministic embedding 兜底
- 当远程 embedding 不可用时，仍能保持 RAG 可运行

### `_build_openai_embeddings()`

作用：

- 构造 OpenAI Embeddings

### `FallbackEmbeddings`

作用：

- 优先用远程 embedding
- 如果失败，自动切换成本地 embedding

### `_build_embeddings()`

作用：

- 统一选择最终 embedding 实现

### `get_vector_store()`

作用：

- 返回 Chroma 向量库对象

---

## 9.10 检索层：`rag/retriever.py`

### `RetrievalMeta`

记录一次检索的元数据：

- expanded queries
- 去重前数量
- 去重后数量
- rerank 模式
- rerank 耗时
- 是否降级
- 降级原因

### `_search_once(...)`

作用：

- 对一个 query 做一次实际检索
- 支持 requirement / testcase 两类库
- 支持额外 metadata 过滤

当前默认会执行：

- 向量召回
- BM25 召回
- 用 RRF 对两路结果做融合

如果 `HYBRID_SEARCH_ENABLED = False`，则退回为原来的纯向量检索

### `_dedup_keep_best(chunks)`

作用：

- 按 `chunk_id` 去重
- 保留得分更高的一条

### `retrieve_context_with_meta(...)`

作用：

- 统一检索入口

处理流程：

1. 处理空 query
2. 判断是否启用 multi-query
3. 生成扩展 query
4. 对每条 query 检索
5. 每条 query 内部执行“向量召回 + BM25 召回 + RRF 融合”
6. 汇总候选
7. 去重
8. rerank
9. 返回最终结果和元数据

### `retrieve_context(...)`

作用：

- 不关心元数据时的简化版检索接口

### `retrieve_testcase_context_with_meta(...)`

作用：

- 专门检索历史测试用例库

### `format_retrieved_context(...)`

作用：

- 把检索出来的 chunk 变成可直接注入 Prompt 的上下文字符串

### `build_citations(...)`

作用：

- 把 chunk 列表转成引用列表，用于页面展示

---

## 9.11 Query 扩展层：`rag/query_expander.py`

这个文件负责对 query 做轻量扩写。

当前思路不是“大模型重写”，而是：

- 原 query
- 同义词替换 query
- 意图补充 query

作用是尽量提升召回覆盖率，但保持实现简单。

---

## 9.12 Rerank 层：`rag/reranker.py`

这个文件负责把初检索结果重新排序。

### `RerankResult`

记录：

- 重排后的 items
- 实际使用的 rerank 模式
- 是否启用
- 耗时
- 是否降级
- 降级原因

### `_rerank_lite(...)`

作用：

- 基于 token overlap 的轻量重排
- 作为默认保底方案

### `_load_cross_encoder(...)`

作用：

- 加载 cross-encoder 模型
- 使用缓存避免重复加载

### `_rerank_cross_encoder(...)`

作用：

- 用强 rerank 模型重排候选

### `rerank(...)`

作用：

- 统一 rerank 入口
- 支持：
  - `lite`
  - `cross_encoder`
- 如果 `cross_encoder` 失败，会自动回退到 `lite`

这是当前项目“检索质量增强”的关键模块。

---

## 9.13 Excel 导出层：`utils/excel_exporter/excel_exporter.py`

### `_write_header(worksheet)`

作用：

- 写入表头
- 设置加粗、边框、居中、自动换行

### `_normalize_cell_value(field_name, test_case)`

作用：

- 统一单元格文本
- 特别处理 `steps` 列表

### `_write_data_rows(worksheet, test_cases)`

作用：

- 写入所有测试用例行

### `_auto_adjust_layout(worksheet)`

作用：

- 自动调整列宽和行高

### `export_test_cases_to_excel(...)`

作用：

- 把测试用例写成 Excel 文件
- 返回导出后的绝对路径

---

## 10. RAG 是怎么工作的

这个项目的 RAG 可以理解成 4 步：

1. 解析文档
   把 `md/docx` 变成层级化结构

2. 切块入库
   把章节正文和表格拆成多个 chunk，写入 Chroma

3. 检索
   根据当前阶段 query，同时做向量召回和 BM25 召回，并用 RRF 融合相关片段

4. 重排
   用 `cross_encoder` 或 `lite` rerank，把更相关的片段排前面

最终这些片段会被拼成一个大字符串，注入给大模型。

---

## 11. 工作流是怎么“暂停等待人工审核”的

LangGraph 里有一个很重要的能力叫：

- `interrupt_before`

当前配置是：

- 在提取测试点前中断
- 在生成大纲前中断
- 在生成测试用例前中断
- 在导出前中断

这意味着：

- AI 先生成当前阶段结果
- 前端把结果展示给用户
- 用户修改后再继续往下走

所以它不是“全自动黑盒”，而是“AI + 人工审核”的协作流程。

---

## 12. 如何调试问题

### 12.1 看页面里的检索依据

每个阶段都能展开“依据片段”，重点看：

- `Query`
- `Expanded Queries`
- `候选数`
- `Rerank: mode / latency / degraded`
- `Rerank fallback reason`
- `Citations`

### 12.2 如果 `pre_dedup=0, post_dedup=0`

说明根本没召回到候选。

优先排查：

- 文档是否成功入库
- `chunk 数` 是否为 0
- 当前 `doc_id` 是否匹配
- query 是否过长或过偏

### 12.3 如果 `mode=lite, degraded=True`

说明本来想用强 rerank，但失败回退了。

再看：

- `Rerank fallback reason`

常见原因：

- 本地没有模型缓存
- 无法联网下载
- 模型加载超时
- 推理报错

### 12.4 如果生成测试用例时报 JSON 解析失败

当前项目已经做了三层保护：

1. `with_structured_output`
2. fallback JSON 解析
3. LLM repair JSON

如果还失败，多半是：

- 模型输出结构太脏
- 字符串里有未转义双引号

现在代码里已经加入了轻量 JSON 清洗逻辑，用来降低这类失败率。

---

## 13. 常见问题

### Q1：为什么 Markdown 能跑，DOCX 有时不行？

可能原因：

- DOCX 标题样式不规范
- 文档内容太少
- 表格内容过多、正文过少
- Word 文件本身格式不标准

### Q2：为什么某阶段没检索到依据片段？

这不一定是 bug。

可能是：

- query 太抽象
- 当前阶段上下文太少
- 文档里对应关键词太弱
- 历史知识库为空

### Q3：为什么 score 经常是 0.0？

因为当前 `SEARCH_TYPE = "mmr"` 时，代码里对 MMR 返回文档的 score 没有真实打分值，暂时统一记成 `0.0`。

这不等于“不相关”。

另外，开启混合检索后，召回阶段还会把向量结果和 BM25 结果做 RRF 融合。
这时最终返回的 `score` 可能是融合分，不一定直接表示某一路原始检索分数。

### Q4：为什么 rerank 显示 `cross_encoder`，但有时还是回退？

因为系统默认优先用 `cross_encoder`，失败就自动回退到 `lite`。

只要主流程能继续跑，这就是设计上的正常行为。

### Q5：为什么工作流测试脚本有时跑不通？

`workflow/main_test.py` 依赖真实 LLM 调用。

如果：

- 没有 API Key
- 接口不可达
- 网络被限制

它就会在大模型阶段失败。

---

## 14. 常用脚本

### 文档解析演示

```bash
python utils/document_parser/run_parser_demo.py
```

### 工作流验证脚本

```bash
python workflow/main_test.py
```

### 历史测试用例批量入库

```bash
python rag/index_testcase_kb.py --dir your_testcase_dir
```

### 离线检索验证

```bash
python rag/eval_offline.py --input your_file.md --query "你的问题"
```

---

## 15. 给第一次看这个项目的人一个阅读顺序

如果你完全是第一次接触这个项目，建议按下面顺序读代码：

1. `app/app.py`
   先理解用户界面和整体流程

2. `workflow/workflow.py`
   看工作流节点顺序

3. `workflow/nodes.py`
   看每个阶段真正做了什么

4. `skills/test_design_skills.py`
   看 Prompt 和结构化输出是怎么实现的

5. `rag/retriever.py`
   看检索是怎么做的

6. `rag/reranker.py`
   看重排逻辑

7. `rag/ingest.py`
   看文档如何切块入库

8. `utils/document_parser/`
   看原始文档如何变成结构化树

9. `utils/excel_exporter/excel_exporter.py`
   看最终导出

---

## 16. 当前项目的设计特点

这个项目有几个明显特点：

- 不是一次性大模型直出，而是带 RAG 的
- 不是全自动黑盒，而是分阶段人工审核
- 不是只支持一种文档格式，而是支持 `md/docx`
- 不是只靠远程 embedding，也有本地 fallback
- 不是只靠单一路径解析 JSON，而是有 structured output + fallback + repair
- 不是只做生成，还展示“为什么这么生成”的检索依据

---

## 17. 你可以从哪里开始二次开发

如果你后面想继续改这个项目，最常见的入口有：

- 改界面：`app/app.py`
- 改 Prompt：`skills/*.md`
- 改结构化输出逻辑：`skills/test_design_skills.py`
- 改检索：`rag/retriever.py`
- 改 rerank：`rag/reranker.py`
- 改切块：`rag/ingest.py`
- 改 DOCX/MD 解析：`utils/document_parser/`
- 改 Excel 模板：`utils/excel_exporter/excel_exporter.py`

---

## 18. 最后一句

如果你把这个项目看成一条流水线，那么它的本质是：

- `文档解析` 负责把原始资料变干净
- `RAG` 负责把相关依据找出来
- `LLM` 负责把依据转成测试设计结果
- `LangGraph` 负责把每一步串起来并允许人工介入
- `Streamlit` 负责把整个流程交给用户操作

也就是说，这不是一个单文件小脚本，而是一套完整的“AI 测试设计工作台”。
