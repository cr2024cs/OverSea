DEMO_PROJECT_NAME = "泰国春武里汽车零部件工厂"
DEMO_COMPLETED_PROJECT_NAME = "泰国春武里汽车零部件工厂（完结版）"

DEMO_PROJECT = {
    "name": DEMO_PROJECT_NAME,
    "client_name": "长三角民营汽车零部件制造企业",
    "contact_name": "王经理",
    "contact_email": "wang@demo-client.local",
    "contact_phone": "+86 138 0000 0000",
    "country": "TH",
    "industry": "manufacturing",
    "entry_mode": "greenfield",
    "goal_text": (
        "我们是一家汽车零部件制造企业，计划在泰国东部经济走廊设厂，"
        "投资约 3,000 万美元，其中约 800 万美元为国内在用设备实物出资，"
        "目标第 14 个月试产、第 15 个月量产。"
    ),
    "investment_cents": 3_000_000_000,
    "currency": "USD",
    "phase": 1,
    "status": "diagnosing",
}

DEMO_DOCUMENTS = [
    {
        "key": "odi-filing",
        "filename": "ODI备案通知书（演示）.txt",
        "mime": "text/plain",
        "text": (
            "境外投资项目备案通知书（演示）\n"
            "投资主体：长三角民营汽车零部件制造企业\n"
            "投资目的地：泰国\n"
            "投资总额 3,000 万美元，其中设备实物出资 800 万美元。\n"
            "项目主要内容：在泰国东部经济走廊设立汽车零部件制造工厂。\n"
        ),
    },
    {
        "key": "articles",
        "filename": "公司章程摘要（演示）.txt",
        "mime": "text/plain",
        "text": (
            "泰国公司章程摘要（演示）\n"
            "公司名称：Thai Chonburi Auto Parts Co., Ltd.\n"
            "注册资本 1 亿泰铢。\n"
            "股东：由中国母公司 100% 持股。\n"
        ),
    },
    {
        "key": "equipment-list",
        "filename": "设备清单（演示）.txt",
        "mime": "text/plain",
        "text": (
            "设备主数据（演示）\n"
            "设备合计 10 台，总功率 1,250 kW。\n"
            "设备制造年份 2018–2023 年，评估价值合计 800 万美元。\n"
            "其中冲压设备 4 台、焊接设备 3 台、检测设备 3 台。\n"
        ),
    },
    {
        "key": "lease",
        "filename": "厂房租赁意向书（演示）.txt",
        "mime": "text/plain",
        "text": (
            "厂房租赁意向书（演示）\n"
            "出租方：春武里工业园区开发有限公司。\n"
            "租赁期限 30 年，到期后自动续期 30 年。\n"
            "承租方需在签约后 30 日内完成租赁登记。\n"
        ),
    },
    {
        "key": "rfp-questions",
        "filename": "RFP问题清单（演示）.txt",
        "mime": "text/plain",
        "text": (
            "RFP 问题清单（演示）\n"
            "1. BOI 优惠的适用活动类别与条件是什么？\n"
            "2. 二手设备进口需要满足哪些条件？\n"
            "3. 工作许可办理期间中方人员能否入境开展筹建工作？\n"
            "4. 工厂经营许可的办理周期与前提是什么？\n"
        ),
    },
]

DEMO_FACTS = [
    {"key": "投资总额", "value": "3,000 万美元", "status": "confirmed", "doc_key": "odi-filing", "quote": "投资总额 3,000 万美元"},
    {"key": "设备实物出资", "value": "800 万美元", "status": "confirmed", "doc_key": "odi-filing", "quote": "设备实物出资 800 万美元"},
    {"key": "注册资本", "value": "1 亿泰铢", "status": "assumption", "doc_key": "articles", "quote": "注册资本 1 亿泰铢"},
    {"key": "厂房方案", "value": "园区内租赁 30 年", "status": "assumption", "doc_key": "lease", "quote": "租赁期限 30 年，到期后自动续期 30 年"},
    {"key": "设备总功率", "value": "1,250 kW", "status": "confirmed", "doc_key": "equipment-list", "quote": "总功率 1,250 kW"},
]

DEMO_RFP_ZH = """询价书（演示）

项目：泰国春武里汽车零部件工厂
客户名称：已隐去
工作范围：BOI 投资优惠申请与取证
交付物：BOI 批复函、投资优惠证书、优惠与义务对照表
回复截止：发送后 14 天
报价格式：分项报价，注明币种、假设与不含项
利益冲突：请披露与本项目相关的利益冲突
"""

DEMO_RFP_EN = """Request for Proposal (Demo)

Project: Chonburi Auto Parts Factory, Thailand
Client: Withheld
Scope: BOI investment promotion application and certification
Deliverables: BOI approval letter, investment promotion certificate, incentives and obligations matrix
Response deadline: 14 days after sending
Pricing format: itemized, with currency, assumptions and exclusions
Conflicts of interest: please disclose any conflict related to this project
"""

DEMO_QUOTE_ITEMS = [
    {"name": "BOI 活动类别与可行性分析", "amount_cents": 8_000_000},
    {"name": "BOI 申请材料准备与提交", "amount_cents": 18_000_000},
    {"name": "面谈支持与取证跟进", "amount_cents": 14_000_000},
]

DEMO_TOTAL_QUOTE = {
    "version": 1,
    "provider_amount_cents": 40_000_000,
    "lawyer_amount_cents": 0,
    "management_fee_cents": 7_000_000,
    "management_fee_rate": 0.175,
    "total_cents": 47_000_000,
    "currency": "CNY",
    "status": "confirmed",
}
