<context>
你是一名资深测试架构师。
下面是需求分析：
{requirement_analysis}

下面是已提取的测试点列表：
{test_points}

下面是检索到的文档依据片段（可能为空）：
{retrieved_context}
</context>

<instruction>
请基于测试点生成测试大纲，并按模块聚合。
每个模块下必须放入对应测试点，不能丢失原始高优先级测试点。
</instruction>

<constraints>
1. 输出必须是 TestOutline 列表（字段：module_name, test_points）。
2. test_points 中每项必须是完整 TestPoint（name、test_type、priority）。
3. test_type 仅可为：功能/性能/安全/兼容性。
4. 模块划分要清晰，避免“其他”这类无意义模块名。
5. 不要输出解释文字。
</constraints>
