import json

SYSTEM_PROMPT = (
    "你是「AI 原生专业服务总包平台」的专业服务分析助手。"
    "你的职责是整理事实、提出问题、指出矛盾与缺失，不替客户、服务商或律师下最终专业结论。"
    "只输出一个合法 JSON 对象，不要 Markdown 代码块，不要额外解释。"
)

STEP_INSTRUCTIONS = {
    "interview": (
        "根据项目事实、任务和模板所需信息，生成最多 5 个最影响任务或报价的追问。"
        "按优先级 1 开始排序。"
        '输出 JSON：{"questions":[{"text":"问题","impact_tasks":["T01"],"priority":1}]}'
    ),
    "extract_facts": (
        "从 documents[].text 中抽取事实。source_doc 必须等于某份文档的 filename；"
        "quote 必须是该文档中的原文片段；status 只能是 confirmed、assumption、unknown。"
        '输出 JSON：{"facts":[{"key":"事实名","value":"值","status":"confirmed","source_doc":"文件名","quote":"原文片段"}]}'
    ),
    "propose": (
        "生成中文项目建议书，必须包含 8 章，chapters 的 id 从 1 到 8。"
        "不要出现任何具体服务商名称。预算字段可留空对象，由系统按模板计算。"
        '输出 JSON：{"title":"建议书标题","chapters":[{"id":1,"title":"章节名","content":"正文"}]}'
    ),
    "draft_rfp": (
        "生成中英双语询价书，默认隐去客户名称，包含范围、交付物、期限、报价格式、假设与不含项、利益冲突问题。"
        '输出 JSON：{"zh":"中文全文","en":"英文全文"}'
    ),
    "parse_quote": (
        "把 raw_text 解析为结构化报价。金额单位为分（整数）。无法确定的字段用 null。"
        '输出 JSON：{"currency":"CNY","amount_cents":0,"items":[{"name":"项目","amount_cents":0}],'
        '"assumptions":null,"exclusions":null,"payment_terms":null}'
    ),
    "review_answer": (
        "对照 source_text 审查服务商答复，覆盖七类检查：覆盖度、依据、条件、事实一致性、"
        "失败路径与替代方案、跨专业冲突、内部一致性。"
        "每条发现必须引用 source_text 原文。只有 source_text 直接矛盾且能提供可点击来源时，"
        "conclusion_level 才能为 verified_error；服务商之间的不同判断用 professional_judgment；"
        "其余用 needs_verification。severity 只能是 重大、一般、提示。"
        '输出 JSON：{"findings":[{"category":"条件","severity":"重大","conclusion_level":"needs_verification",'
        '"quote_text":"原文","reason":"理由","question_zh":"中文追问","question_en":"English follow-up",'
        '"is_legal":true,"sources":[{"type":"official","label":"来源","url":"https://...","clickable":true}]}]}'
    ),
    "acceptance_summary": (
        "根据交付物、验收标准和专家评分，生成客户可读的中文摘要。"
        '输出 JSON：{"conclusion":"结论","conditions":["条件"],"risks":["风险"],"todos":["待办"]}'
    ),
    "retrospective": (
        "根据项目全过程数据生成复盘报告草稿，只引用给定数据，不虚构。"
        '输出 JSON：{"timeline":["事件"],"budget":{},"issues":["问题"],'
        '"provider_performance":"服务商表现","critical_path_variance":"关键路径偏差"}'
    ),
}


def build_messages(step, payload):
    instruction = STEP_INSTRUCTIONS.get(step, "请处理输入并输出 JSON。")
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"任务步骤：{step}\n{instruction}\n\n"
                f"输入数据：\n{json.dumps(payload, ensure_ascii=False)}"
            ),
        },
    ]


def chat_messages(system_prompt, history):
    return [{"role": "system", "content": system_prompt}] + history
