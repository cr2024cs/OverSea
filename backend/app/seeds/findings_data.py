OFFICIAL_BOI = {
    "type": "official",
    "label": "BOI Investment Promotion Guide 2026",
    "url": "https://www.boi.go.th/index.php?language=zh&page=guides",
    "clickable": True,
}
OFFICIAL_BOI_MACHINE = {
    "type": "official",
    "label": "BOI 机器与原材料进口优惠",
    "url": "https://www.boi.go.th/upload/content/2_BOI%20Incentives%20on%20Importing%20Machinery%20&%20Raw%20Materials.pdf",
    "clickable": True,
}
OFFICIAL_LAND_LEASE = {
    "type": "official",
    "label": "One Asia Lawyers：泰国长期租赁",
    "url": "https://oneasia.legal/en/7202",
    "clickable": True,
}

DEMO_FINDINGS = [
    {
        "category": "条件",
        "severity": "重大",
        "conclusion_level": "needs_verification",
        "quote_text": "贵司项目原则上可以获得 BOI 优惠。",
        "reason": "只给结论，未说明对应活动类别、优惠等级、最低投资额、外资持股条件与适用政策版本。",
        "question_zh": "对应哪一项鼓励活动与优惠等级？最低投资额与外资持股条件是什么？是否适用 2026 年新措施？预计审批周期多长？",
        "question_en": "Which promoted activity and incentive tier applies? What are the minimum investment and foreign shareholding conditions? Do the 2026 measures apply? What is the expected approval timeline?",
        "is_legal": True,
        "sources_json": [OFFICIAL_BOI],
        "citation_status": "verified",
    },
    {
        "category": "失败路径与替代方案",
        "severity": "一般",
        "conclusion_level": "needs_verification",
        "quote_text": "可签 30 年租约，合同约定到期自动续期 30 年。",
        "reason": "未说明自动续期条款能否对抗出租人、地块是否符合 50 年工商业租赁的区域条件，以及登记安排。",
        "question_zh": "自动续期条款能否对抵出租人执行？地块是否符合 50 年工商业租赁的区域条件？如何安排登记？",
        "question_en": "Is the automatic renewal enforceable against the landlord? Does the plot qualify for the 50-year industrial lease? How will registration be arranged?",
        "is_legal": True,
        "sources_json": [OFFICIAL_LAND_LEASE],
        "citation_status": "verified",
    },
    {
        "category": "条件",
        "severity": "重大",
        "conclusion_level": "needs_verification",
        "quote_text": "二手设备都可以免税进口。",
        "reason": "未区分设备制造年份、性能证书、是否计入投资额，也未与评估报告清单核对。",
        "question_zh": "每台设备从制造年到进口年各是多少年？需要哪类性能证书？是否计入投资额？与评估报告清单是否一致？",
        "question_en": "How old is each machine from manufacturing year to import year? What performance certificates are required? Are they counted toward investment? Do they match the appraisal list?",
        "is_legal": True,
        "sources_json": [OFFICIAL_BOI_MACHINE],
        "citation_status": "verified",
    },
    {
        "category": "条件",
        "severity": "重大",
        "conclusion_level": "needs_verification",
        "quote_text": "中方 20 人都可以走 BOI 通道办工作许可。",
        "reason": "未说明每人月收入是否达到 BOI 门槛、岗位是否获批、安装人员是否适用短期安排。",
        "question_zh": "每人月收入是否达到 BOI 门槛？岗位是否已获批？安装人员是否走 6 个月以内的短期安排？取证前入泰的筹建人员怎么办？",
        "question_en": "Does each expatriate meet the BOI minimum monthly income? Are the positions approved? Do installation staff qualify for the under-six-month arrangement? How should pre-certificate setup staff enter Thailand?",
        "is_legal": True,
        "sources_json": [
            {
                "type": "official",
                "label": "DFDL：BOI 外籍员工新规",
                "url": "https://www.dfdl.com/?p=64995",
                "clickable": True,
            }
        ],
        "citation_status": "verified",
    },
    {
        "category": "事实一致性",
        "severity": "重大",
        "conclusion_level": "verified_error",
        "quote_text": "章程写明注册资本 1 亿泰铢。",
        "reason": "与 ODI 备案的中方投资额折算后不一致，需按备案金额调整或说明差额安排。",
        "question_zh": "请按备案金额调整注册资本，或说明差额的安排。",
        "question_en": "Please align the registered capital with the ODI filing, or explain the arrangement for the difference.",
        "is_legal": True,
        "sources_json": [
            {
                "type": "project_document",
                "label": "ODI 备案通知书（演示）",
                "url": "demo://doc/odi-filing",
                "clickable": True,
            },
            {
                "type": "project_document",
                "label": "公司章程摘要（演示）",
                "url": "demo://doc/articles",
                "clickable": True,
            },
        ],
        "citation_status": "verified",
    },
    {
        "category": "跨专业冲突",
        "severity": "重大",
        "conclusion_level": "professional_judgment",
        "quote_text": "泰国会计师按全部现金出资做注资计划。",
        "reason": "ODI 备案含 800 万美元设备实物出资，与会计师的现金出资假设冲突，需要中泰两地专业方对齐。",
        "question_zh": "实物出资在泰国如何入账、由谁出具出资确认？请泰国律所、会计师与关联律所对齐方案。",
        "question_en": "How should the in-kind contribution be booked in Thailand and who issues the capital confirmation? Please align the Thai law firm, accountant and PRC counsel.",
        "is_legal": False,
        "sources_json": [
            {
                "type": "project_document",
                "label": "ODI 备案通知书（演示）",
                "url": "demo://doc/odi-filing",
                "clickable": True,
            }
        ],
        "citation_status": "verified",
    },
    {
        "category": "内部一致性",
        "severity": "重大",
        "conclusion_level": "verified_error",
        "quote_text": "申请文件中的机器总功率与设备清单合计不符。",
        "reason": "工厂许可申请填写总功率与设备清单合计不一致，可能影响工厂类别判断。",
        "question_zh": "请核对并更正总功率，并确认工厂类别是否变化。",
        "question_en": "Please verify and correct the total power and confirm whether the factory category changes.",
        "is_legal": False,
        "sources_json": [
            {
                "type": "project_document",
                "label": "设备清单（演示）",
                "url": "demo://doc/equipment-list",
                "clickable": True,
            }
        ],
        "citation_status": "verified",
    },
    {
        "category": "覆盖度",
        "severity": "重大",
        "conclusion_level": "verified_error",
        "quote_text": "答复未回应工作许可办理期间中方人员能否入境开展筹建工作。",
        "reason": "询价书明确提问，服务商答复遗漏该问题，属于漏答。",
        "question_zh": "请补充该问题的答复，并说明哪些活动不构成“工作”。",
        "question_en": "Please answer the omitted question and clarify which activities do not constitute work.",
        "is_legal": True,
        "sources_json": [
            {
                "type": "project_document",
                "label": "RFP 问题清单（演示）",
                "url": "demo://doc/rfp-questions",
                "clickable": True,
            }
        ],
        "citation_status": "verified",
    },
]
