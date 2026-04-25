优化后路线（Phase 1 + Phase 2，4天，可直接执行）

下面这版是“先可用、再增强、全程可验收”的落地方案，按你当前项目结构定制，避免过度设计。

一、目标与边界

目标1：把 RAG 接入现有生成链路，让每个节点都能基于“当前文档证据”生成结果。
目标2：提升召回覆盖率（Multi-Query）和前排相关性（Rerank）。
目标3：前端可看到“每阶段依据片段”，提升可解释性。
边界1：不引入复杂评测框架，只做脚本级离线评测。
边界2：先保证稳定与可观测，再做模型级精调。
二、总体实施原则（按 karpathy-guidelines）

只改必须改的文件，先跑通最短链路，再复制到其余节点。
每一步都有“可执行验收命令”，没有验收就不进入下一步。
所有增强功能可开关、可回退（尤其 rerank）。
所有关键中间产物可观测（chunk 数、命中列表、引用）。
三、文件变更清单（最终版）

新增 rag/config.py。
新增 rag/schemas.py。
新增 rag/store.py。
新增 rag/ingest.py。
新增 rag/retriever.py。
新增 rag/query_expander.py。
新增 rag/reranker.py。
新增 rag/eval_offline.py。
修改 workflow/state.py。
修改 workflow/nodes.py。
修改 skills/analyze_requirement_skill.md。
修改 skills/extract_test_points_skill.md。
修改 skills/generate_outline_skill.md。
修改 skills/generate_cases_skill.md。
修改 app/app.py。
四、数据结构设计（先定死，减少返工）

Chunk 字段：chunk_id, doc_id, source_name, section_path, paragraph_index, text, char_len。
RetrievedChunk 字段：chunk_id, doc_id, source_name, section_path, text, score, query。
Citation 字段：chunk_id, section_path, source_name, score。
RetrievalLog 字段：phase, query, expanded_queries, top_k, hits, citations, latency_ms, rerank_enabled。
State 新增字段：doc_id: str, retrieval_logs: list[dict]。
五、Phase 1（2天）

Day 1：入库与检索打通

在 rag/config.py 固化参数。
建议默认值：persist_directory=./data/chroma, chunk_size=500, chunk_overlap=80, retriever_top_k=8, fetch_k=20, max_context_chars=6000。
在 rag/store.py 实现 Chroma 初始化。
collection 建议命名固定，如 test_case_rag_v1，减少多集合管理复杂度。
在 rag/ingest.py 实现 index_document(doc_id, source_name, structured_doc) -> int。
切块策略：先 DFS 遍历 DocumentSection 生成 section_path，再对 content 按字符窗口切分。
表格策略：把每行序列化成文本并并入切块，避免丢信息。
在 rag/retriever.py 实现 retrieve_context(query, doc_id, top_k=5)。
必须强制 filter={"doc_id": doc_id}。
在 rag/eval_offline.py 做离线脚本评测。
验收命令：执行脚本后打印 indexed_chunks > 0。
验收命令：给定 query 返回至少含 chunk_id/section_path/text。
Day 2：注入 4 个节点 + Prompt 改造 + 最小可视化

修改 workflow/state.py 增加 doc_id/retrieval_logs。
修改 app/app.py 上传后立即执行 index_document。
doc_id 生成建议：web_{uuid}，写入状态。
在 workflow/nodes.py 的四个节点统一调用 retrieve_context。
四个节点 query 规则先固定模板。
analyze query：请提取需求核心流程、依赖、约束。
extract query：{requirement_analysis} + 请覆盖正常/边界/异常。
outline query：{requirement_analysis} + {test_points摘要}。
cases query：{requirement_analysis} + {outline摘要}。
统一格式化函数把召回片段拼成 <retrieved_context> 文本块。
每条格式：[chunk_id] [section_path] text。
对 retrieved_context 做总长度截断（例如 6000 chars）。
修改四个 skills/*.md，增加 {retrieved_context} 占位符。
空召回时传空字符串，不抛错。
把每节点检索结果写入 retrieval_logs。
在 app/app.py 每个审核页加“依据片段”折叠区（先展示前 3 条）。
Day 2 验收：4 节点都能看到命中 chunk 和 section_path。
Day 2 验收：结果较无 RAG 版本更贴近文档细节（人工对比）。
六、Phase 2（2天）

Day 3：Multi-Query（轻量规则版）

在 rag/query_expander.py 实现规则改写，不依赖额外 LLM。
固定输出 3 条 query：原 query + 2 条改写。
规则1：同义替换，如“异常/错误/失败”。
规则2：子意图改写，如“流程/约束/边界/兼容性”。
在 rag/retriever.py 加 multi_query=True 分支。
每条 query 召回 top_k=3。
合并后按 chunk_id 去重。
去重保留最高分那条记录。
统一排序后截断到最终 top_k=8。
写日志字段：expanded_queries, pre_dedup_count, post_dedup_count。
Day 3 验收：同一问题覆盖面更广。
Day 3 验收：流程/异常/边界角度均能命中。
Day 4：Rerank + 引用可视化增强

在 rag/reranker.py 实现重排器接口。
接口定义：rerank(query, candidates) -> reranked_candidates。
先做可开关：enable_rerank。
关闭 rerank 时直接返回原排序（fail-open）。
开启 rerank 时：候选建议 12，保留前 5。
如果依赖模型不可用，自动降级，不影响主流程。
在 retrieval_logs 记录 rerank_enabled/rerank_latency_ms。
前端折叠区增强：显示 citations（chunk_id/section_path/source_name/score）。
点击查看时只展示摘要（每条 200-300 字）+ 可展开全文。
Day 4 验收：每阶段都可看到“结论依据”。
Day 4 验收：前 3 条引用人工评估相关性明显提升。
七、关键参数（首版建议）

Embedding：text-embedding-3-small。
Chunk：chunk_size=500, chunk_overlap=80。
Retriever：search_type=mmr, top_k=8, fetch_k=20。
Multi-query：query_count=3, per_query_top_k=3。
Rerank：candidate_pool=12, final_top_n=5。
Prompt 注入长度：max_context_chars=6000。
八、离线评测脚本（不引入框架）

python rag/eval_offline.py --input utils/document_parser/test.md --query "登录异常处理"。
输出指标1：indexed_chunks。
输出指标2：retrieved_count。
输出指标3：unique_section_paths。
输出指标4：top_hits（含 chunk_id/section_path/score）。
输出指标5：latency_ms（index/retrieve/rerank）。
通过标准：indexed_chunks>0 且 retrieved_count>0。
九、风险与回退策略

风险1：依赖不可用导致 rerank 失败。
回退1：enable_rerank=false 自动降级。
风险2：上下文过长导致 token 增长和超时。
回退2：强截断 + 仅前 N 引用。
风险3：跨文档串召回。
回退3：强制 doc_id filter，日志监控 doc_id。
风险4：性能抖动。
回退4：降低 top_k/fetch_k，暂关 multi-query。
十、Definition of Done（完成标准）

上传文档后必有入库日志，chunk 数可见。
4 个节点都能检索并把依据注入 prompt。
4 个阶段页面都能看到依据片段折叠区。
retrieval_logs 字段完整、结构一致。
Multi-query 开关有效，开启后覆盖面提升。
Rerank 开关有效，关闭不影响主流程。
离线脚本可一键跑通并输出关键指标。
十一、建议的实际执行顺序（最稳）

先完成 Day 1 全部内容并冻结接口。
Day 2 先接 analyze，跑通后复制到另外 3 节点。
Day 3 仅做 multi-query，不碰 rerank。
Day 4 再加 rerank 和 UI增强。
每天收尾都跑离线脚本 + 一次端到端手工上传验证。
如果你愿意，我可以下一步直接给你“按这个路线拆好的实施任务单（精确到每个文件要加哪些函数签名）”，你拿去就能直接编码。