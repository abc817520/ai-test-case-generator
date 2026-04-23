很好，这里给你一版更“工程可落地”的 RAG 路线，细到技术栈、模块拆分、接口、验收。

推荐主栈（与你现有 LangChain/LangGraph 最兼容）

向量库：Chroma（本地持久化，开发快）
Embedding：OpenAI text-embedding-3-small（先控成本），后续可切 -large
文本切分：RecursiveCharacterTextSplitter + 你现有 DocumentSection 结构化路径
检索：VectorStoreRetriever（MMR）
重排（阶段2）：sentence-transformers 的 cross-encoder/ms-marco-MiniLM-L-6-v2（本地）
配置：.env + pydantic-settings
评估：先做脚本级离线评测（不引入复杂框架）
阶段 1（优化版）：RAG 基础接入（建议 2 天）
Day 1 - 入库与检索打通
新建目录结构
rag/ingest.py：文档切块与入库
rag/retriever.py：统一检索接口
rag/schemas.py：Chunk/引用结构定义
rag/store.py：Chroma 初始化与集合管理
rag/config.py：RAG 参数（chunk_size/top_k 等）
Chunk 设计（关键）
每个 chunk 字段：
chunk_id（UUID）
doc_id（上传会话文档ID）
source_name（文件名）
section_path（如 ROOT > 登录模块 > 异常处理）
paragraph_index
text
切分策略：
先按 DocumentSection 遍历，拿到 section_path
再对 section content 做字符级切分（如 chunk_size=500, overlap=80）
入库接口
index_document(doc_id: str, source_name: str, structured_doc: dict) -> int
返回入库 chunk 数
Chroma persist_directory: ./data/chroma
检索接口（统一）
retrieve_context(query: str, doc_id: str, top_k: int = 5) -> list[RetrievedChunk]
只检索当前文档：filter={"doc_id": doc_id}
验收
上传后打印入库 chunk 数 > 0
给定 query，能返回 chunk 文本 + section_path + chunk_id
Day 2 - 注入 4 个节点
状态扩展（workflow/state.py）
增加：
doc_id: str
retrieval_logs: list[dict]（可选）
节点注入策略
在 analyze/extract/outline/cases 各节点调用 retrieve_context
把检索结果拼进 prompt 前置块：
<retrieved_context>
每条含：[chunk_id] [section_path] text...
Query 生成建议（先简单）
analyze："请提取需求核心流程、依赖、约束"
extract：requirement_analysis + "请覆盖正常/边界/异常"
outline：requirement_analysis + test_points摘要
cases：requirement_analysis + outline摘要
Prompt 改造（你已外置 md 很适合）
在 4 个 skills/*.md 增加 {retrieved_context} 占位符
没检索到时传空字符串，避免报错
验收
UI/日志可看到每节点检索了哪些 chunk
结果与文档细节更贴近（可人工对比）
阶段 2（优化版）：RAG 质量增强（建议 2 天）
Day 3 - 多查询检索（Multi-Query）
新增 query 改写器
rag/query_expander.py
输入原 query，输出 2-4 条改写 query
先用轻量规则+模板（不依赖额外 LLM）：
同义替换：异常=错误=失败
目标改写：流程、约束、边界、兼容性等子意图
检索策略
每条 query 各取 top_k=3
合并去重（按 chunk_id）
以相似度排序截断到最终 top_k（如 8）
验收
同一问题召回片段覆盖更广
不同视角（流程/异常/边界）都能命中
Day 4 - 重排 + 引用可视化
Rerank（可选但推荐）
rag/reranker.py
对合并候选做 Cross-Encoder 打分
取前 N（建议 5）
输出附引用
每节点结果附 citations：
chunk_id
section_path
source_name
存入 state.retrieval_logs，前端展示“本阶段依据”
UI 展示（app）
在每个审核页下方增加 依据片段 折叠区
点击可看 chunk 文本摘要
验收
每阶段都能看到“结论依据”
前3条引用相关性明显提升（人工评估）
关键参数建议（首版）
Embedding
text-embedding-3-small（先快后优）
Chunk
chunk_size=500
chunk_overlap=80
Retriever
search_type="mmr"
top_k=6~8
fetch_k=20
Multi-query
改写数：3
每改写召回：3
Rerank
候选 12 -> 保留 5
你项目里建议先改的文件
新增
rag/config.py
rag/schemas.py
rag/store.py
rag/ingest.py
rag/retriever.py
rag/query_expander.py
rag/reranker.py（阶段2）
修改
workflow/state.py（加 doc_id/retrieval_logs）
workflow/nodes.py（4节点注入 retrieve）
skills/*.md（加入 {retrieved_context}）
app/app.py（上传后触发 index + 展示引用）
最小可行顺序（避免过度设计）
先做 ingest + retrieve_context + analyze 节点注入
跑通后复制到另外 3 个节点
最后再加 multi-query 与 rerank
如果你愿意，我下一步可以直接按这个方案给你落第一版代码骨架（rag/ 目录 + analyze 节点先接通）。
