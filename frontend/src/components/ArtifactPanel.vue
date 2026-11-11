<template>
  <aside class="artifact" :class="{ full: panelFull }">
    <header class="panel-header">
      <div class="phase-nav">
        <button
          v-for="item in phaseNav"
          :key="item.phase"
          class="phase-chip"
          :class="{ active: activePhase === item.phase, locked: item.locked }"
          :disabled="item.locked"
          :title="item.locked ? `阶段未开始：${item.label}` : item.label"
          @click="selectPhase(item.phase)"
        >
          <span v-if="item.phase" class="phase-no">{{ item.phase }}</span>
          {{ item.label }}
        </button>
      </div>
      <button class="expand" @click="panelFull = !panelFull">
        {{ panelFull ? '收起' : '展开' }}
      </button>
    </header>

    <div v-if="phaseTabs.length > 1" class="sub-tabs">
      <button
        v-for="tab in phaseTabs"
        :key="tab.key"
        class="tab"
        :class="{ active: activeType === tab.key }"
        @click="activeType = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <div class="panel-body">
      <div v-if="loading" class="state">正在加载…</div>
      <div v-else-if="error" class="state error">{{ error }}</div>

      <template v-else>
        <div v-if="activeType === 'facts'" class="stack">
          <div v-if="isPm" class="toolbar">
            <button :disabled="busy" @click="extractFacts">
              {{ busy ? '处理中…' : '提取事实' }}
            </button>
            <button :disabled="busy" @click="generateQuestions">生成追问</button>
          </div>

          <div v-if="questions.length" class="question-list">
            <h4>追问清单（按影响排序）</h4>
            <div v-for="question in questions" :key="question.text" class="question-item">
              <span>{{ question.text }}</span>
              <small>影响 {{ (question.impact_tasks || []).join('、') }}</small>
            </div>
          </div>

          <div v-if="!raw?.length" class="state">暂无事实，先上传资料或提取事实。</div>
          <article v-for="fact in raw" :key="fact.id" class="fact">
            <div class="fact-top">
              <span class="fact-key">{{ fact.key }}</span>
              <span class="pill" :class="fact.status">{{ statusLabel(fact.status) }}</span>
            </div>
            <p class="fact-value">{{ fact.value }}</p>
            <button
              v-if="fact.citation"
              class="citation"
              @click="openCitation(fact.citation)"
            >
              来源 · {{ fact.citation.filename }}
            </button>
          </article>
        </div>

        <div v-else-if="activeType === 'tasks'" class="stack">
          <div v-if="isPm" class="toolbar">
            <button
              :class="{ selected: scenario === 'lease' }"
              :disabled="busy"
              @click="refreshTasks('lease')"
            >
              租厂房
            </button>
            <button
              :class="{ selected: scenario === 'land_purchase' }"
              :disabled="busy"
              @click="refreshTasks('land_purchase')"
            >
              园区外买地
            </button>
          </div>

          <div v-if="graphDiff" class="diff">
            <template v-if="graphDiff.first_generation">首次生成任务地图</template>
            <template v-else>
              <span v-if="graphDiff.added?.length">新增 {{ graphDiff.added.join('、') }}</span>
              <span v-if="graphDiff.removed?.length">移除 {{ graphDiff.removed.join('、') }}</span>
              <span v-if="graphDiff.changed?.length">变更 {{ graphDiff.changed.join('、') }}</span>
              <span v-if="!graphDiff.added?.length && !graphDiff.removed?.length && !graphDiff.changed?.length">
                与上一版一致
              </span>
            </template>
          </div>

          <TaskGraph v-if="graphData?.tasks?.length" :graph="graphData" />

          <div v-if="!raw?.length" class="state">暂无任务地图，点击上方场景生成。</div>
          <div v-else class="graph-summary">
            关键路径：{{ (graphData?.critical_path || []).join(' → ') }} ·
            总周期 {{ graphData?.total_days || 0 }} 天
          </div>
          <section v-for="group in taskGroups" :key="group.stage" class="task-group">
            <h4>阶段 {{ group.stage }}<span>{{ group.items.length }} 项</span></h4>
            <div
              v-for="task in group.items"
              :key="task.id"
              class="task"
              :class="{ locked: task.locked }"
            >
              <span class="code">{{ task.code }}</span>
              <span class="task-name">{{ task.name }}</span>
              <span v-if="task.is_critical" class="star">关键</span>
              <span v-if="task.locked" class="lock">锁定</span>
            </div>
          </section>
        </div>

        <div v-else-if="activeType === 'proposal'" class="stack">
          <div class="toolbar">
            <button v-if="isPm" :disabled="busy" @click="generateProposal">
              {{ raw ? '重新生成' : '生成建议书' }}
            </button>
            <select
              v-if="proposalVersions.length"
              v-model="selectedVersionId"
              class="version-select"
              @change="selectVersion"
            >
              <option
                v-for="version in proposalVersions"
                :key="version.id"
                :value="version.id"
              >
                v{{ version.version }} · {{ proposalStatusLabel(version.status) }}
              </option>
            </select>
            <button
              v-if="isPm && raw && raw.status === 'generated'"
              :disabled="busy"
              @click="reviewProposal"
            >
              PM 审核
            </button>
            <button
              v-if="isPm && raw && raw.status === 'pm_reviewed'"
              :disabled="busy"
              @click="sendProposal"
            >
              发送客户
            </button>
            <button v-if="isPm && raw" :disabled="busy" @click="createProposalLink">
              客户链接
            </button>
            <button v-if="raw" @click="printPanel">打印</button>
            <button
              v-if="raw && proposalVersions.length > 1"
              :disabled="busy"
              @click="compareProposal"
            >
              对比上一版
            </button>
          </div>

          <div v-if="comparison" class="diff">
            与 v{{ comparison.fromVersion }} 相比：
            <template v-if="comparison.changed.length">
              变更章节 {{ comparison.changed.join('、') }}
            </template>
            <template v-else>章节内容一致</template>
          </div>

          <div v-if="!raw" class="state">
            {{ isPm ? '暂无建议书，点击“生成建议书”。' : '暂无建议书。' }}
          </div>
          <template v-else>
            <div class="proposal-head">
              <h3>{{ raw.content?.title || '项目建议书' }}</h3>
              <span class="pill">{{ proposalStatusLabel(raw.status) }}</span>
            </div>
            <p class="muted">
              版本 v{{ raw.version }}
            </p>

            <div class="chapter-nav">
              <button
                v-for="chapter in raw.content?.chapters || []"
                :key="chapter.id"
                @click="scrollToChapter(chapter.id)"
              >
                {{ chapter.id }}
              </button>
            </div>

            <article
              v-for="chapter in raw.content?.chapters || []"
              :id="`proposal-chapter-${chapter.id}`"
              :key="chapter.id"
              class="chapter"
            >
              <h4>{{ chapter.id }}. {{ chapter.title }}</h4>
              <p>{{ chapter.content }}</p>
            </article>

            <div v-if="raw.content?.budget" class="budget">
              <strong>预算区间</strong>
              <span>
                低 {{ money(raw.content.budget.low_cents) }} / 中
                {{ money(raw.content.budget.mid_cents) }} / 高
                {{ money(raw.content.budget.high_cents) }}
              </span>
              <small>{{ raw.content.budget.basis }}</small>
              <small class="warn">{{ raw.content.disclaimer }}</small>
            </div>

            <div v-if="raw.content?.references?.length" class="references">
              <h4>平台资料引用</h4>
              <button
                v-for="reference in raw.content.references"
                :key="reference.chunk_id"
                class="citation"
                :class="{ stale: reference.stale }"
                @click="openChunk(reference.chunk_id)"
              >
                {{ reference.doc_code }} · {{ reference.heading_path }}
              </button>
            </div>

            <div v-if="proposalLink" class="client-link">
              <input :value="proposalLink" readonly />
              <button @click="copyProposalLink">复制</button>
            </div>
          </template>
        </div>

        <div v-else-if="activeType === 'selection'" class="stack">
          <div class="toolbar">
            <button v-if="isPm || isClient" :disabled="busy" @click="saveSelection">
              保存选择
            </button>
            <button v-if="isPm" :disabled="busy" @click="createSelectionLink">
              客户选择链接
            </button>
            <button v-if="isPm" :disabled="busy" @click="activeType = 'candidates'">
              下一步：候选服务商
            </button>
            <button @click="printPanel">打印</button>
          </div>

          <p class="muted">勾选需要的服务项；缺少前置服务时只提示，不阻断。</p>

          <section v-for="stage in catalog?.stages || []" :key="stage.stage" class="task-group">
            <h4>
              {{ stage.stage }} · {{ stage.stage_label }}
              <span>{{ stage.items.length }} 项</span>
            </h4>
            <label
              v-for="item in stage.items"
              :key="item.code"
              class="service-item"
              :class="{ checked: selectedCodes.includes(item.code) }"
            >
              <input v-model="selectedCodes" type="checkbox" :value="item.code" />
              <span class="code">{{ item.code }}</span>
              <span class="service-name">{{ item.name }}</span>
              <span class="service-fee">
                {{ money(item.fee_min_cents) }}–{{ money(item.fee_max_cents) }}
              </span>
            </label>
          </section>

          <div v-if="selectionWarnings.length" class="diff">
            <span v-for="warning in selectionWarnings" :key="warning">
              {{ warning }}
            </span>
          </div>

          <input
            v-if="isPm"
            v-model="overrideReason"
            class="reason-input"
            placeholder="PM 代选原因（内部保存必填）"
          />

          <div v-if="isPm && selectionLink" class="client-link">
            <input :value="selectionLink" readonly />
            <button @click="copySelectionLink">复制</button>
          </div>
        </div>

        <div v-else-if="activeType === 'candidates'" class="stack">
          <div class="toolbar">
            <button :disabled="busy" @click="generateCandidates">生成候选</button>
            <button v-if="isPm" :disabled="busy" @click="activeType = 'quotes'">
              下一步：查看报价
            </button>
          </div>

          <div v-if="!candidateGroups.length" class="state">
            暂无候选。先在“选服务”中勾选服务，再生成候选。
          </div>

          <section v-for="group in candidateGroups" :key="group.task_code" class="task-group">
            <h4>
              {{ group.task_code }} {{ group.task_name }}
              <span>{{ group.candidates.length }} 家</span>
            </h4>
            <article
              v-for="candidate in group.candidates"
              :key="candidate.id"
              class="candidate"
              :class="{ rejected: candidate.status === 'rejected' }"
            >
              <div class="fact-top">
                <span class="fact-key">{{ candidate.provider_name }}</span>
                <span class="pill">{{ candidate.match_score }} 分</span>
              </div>
              <p class="muted">
                {{ candidate.provider_type }} · {{ candidate.city || '—' }} ·
                {{ candidate.source_type }} · {{ candidate.evidence_level }}
              </p>
              <p class="candidate-reason">{{ candidate.reason }}</p>
              <p v-if="candidate.evidence?.qualification" class="muted">
                资质：{{ candidate.evidence.qualification }}
              </p>
              <button
                v-if="candidate.status !== 'rejected'"
                class="small-btn"
                @click="rejectCandidate(candidate)"
              >
                标记不合适
              </button>
              <span v-else class="muted">已拒绝：{{ candidate.reject_reason }}</span>
            </article>
          </section>
        </div>

        <div v-else-if="activeType === 'quotes'" class="stack">
          <div v-if="isPm" class="toolbar">
            <button :disabled="busy" @click="createRfps">生成询价书</button>
          </div>

          <h4 class="section-title">询价书</h4>
          <div v-if="!raw?.rfps?.length" class="state">暂无询价书。</div>
          <article v-for="rfp in raw?.rfps || []" :key="rfp.id" class="rfp">
            <div class="fact-top">
              <span class="fact-key">
                {{ rfp.task_code }} · {{ rfp.provider_name }}
              </span>
              <span class="pill">{{ rfp.status }}</span>
            </div>
            <p class="muted">
              打开时间：{{ rfp.opened_at || '未打开' }} · 发送时间：{{ rfp.sent_at || '未发送' }}
            </p>
            <div v-if="isPm" class="actions">
              <button v-if="rfp.status === 'draft'" class="small-btn" @click="approveRfp(rfp)">
                批准
              </button>
              <button v-if="rfp.status === 'approved'" class="small-btn" @click="sendRfp(rfp)">
                发送
              </button>
              <button
                v-if="['sent', 'replied'].includes(rfp.status)"
                class="small-btn"
                @click="copyRfpLink(rfp)"
              >
                复制服务商链接
              </button>
            </div>
          </article>

          <h4 class="section-title">比价</h4>
          <div v-if="!raw?.comparison?.tasks?.length" class="state">暂无报价。</div>
          <section
            v-for="task in raw?.comparison?.tasks || []"
            :key="task.task_code"
            class="task-group"
          >
            <h4>
              {{ task.task_code }} {{ task.task_name }}
              <span>价差 {{ task.spread_percent }}%</span>
            </h4>
            <article
              v-for="quote in task.quotes"
              :key="quote.id"
              class="quote-row"
              :class="{ lowest: quote.is_lowest }"
            >
              <div class="fact-top">
                <span>{{ quote.provider_name }}</span>
                <span class="amount">{{ money(quote.amount_cents) }}</span>
              </div>
              <p v-if="quote.assumptions" class="muted">假设：{{ quote.assumptions }}</p>
              <p v-if="quote.exclusions" class="muted">不含：{{ quote.exclusions }}</p>
              <span v-if="quote.is_lowest" class="pill confirmed">最低价</span>
            </article>
          </section>

          <h4 class="section-title">客户总报价</h4>
          <div v-if="isPm" class="quote-form">
            <label>
              服务商费用（元）
              <input v-model="quoteForm.providerYuan" type="number" min="0" />
            </label>
            <label>
              律所费用（元）
              <input v-model="quoteForm.lawyerYuan" type="number" min="0" />
            </label>
            <label>
              管理费率（%）
              <input v-model="quoteForm.feeRate" type="number" min="0" max="100" step="0.1" />
            </label>
            <button class="small-btn" :disabled="busy" @click="createClientQuote">
              生成新版本
            </button>
          </div>

          <article
            v-for="quote in clientQuotes"
            :key="quote.id"
            class="client-quote"
          >
            <div class="fact-top">
              <span class="fact-key">v{{ quote.version }} · {{ quote.status }}</span>
              <span class="amount">{{ money(quote.total_cents) }}</span>
            </div>
            <p class="muted">
              服务商 {{ money(quote.provider_amount_cents) }} · 律所
              {{ money(quote.lawyer_amount_cents) }} · 管理费
              {{ money(quote.management_fee_cents) }}（{{ quote.fee_percent }}%）
            </p>
            <div class="actions">
              <button
                v-if="isPm && quote.status === 'draft'"
                class="small-btn"
                @click="sendClientQuote(quote)"
              >
                发送客户
              </button>
            </div>
          </article>

          <div class="toolbar">
            <button v-if="isPm" :disabled="busy" @click="createClientQuoteLink">
              生成客户确认链接
            </button>
            <button @click="printPanel">打印</button>
          </div>
          <div v-if="isPm && clientQuoteLink" class="client-link">
            <input :value="clientQuoteLink" readonly />
            <button @click="copyClientQuoteLink">复制</button>
          </div>
        </div>

        <div v-else-if="activeType === 'contract'" class="stack">
          <div class="toolbar">
            <button v-if="isPm" :disabled="busy" @click="generateContract">
              {{ raw ? '重新生成合同' : '生成合同与节点' }}
            </button>
            <button
              v-if="isPm && raw && raw.status === 'draft'"
              :disabled="busy"
              @click="reviewContract"
            >
              PM 复核
            </button>
            <button v-if="isPm && raw" :disabled="busy" @click="createContractClientLink">
              客户确认链接
            </button>
            <button v-if="raw" @click="printPanel">打印</button>
          </div>

          <div v-if="!raw" class="state">
            {{ isPm ? '暂无合同。需先完成客户总报价确认、服务选择与询价报价。' : '暂无合同。' }}
          </div>
          <template v-else>
            <div class="proposal-head">
              <h3>委托确认单 v{{ raw.version }}</h3>
              <span class="pill">{{ raw.status }}</span>
            </div>
            <p class="muted">
              总价 {{ money(raw.total_cents) }} · 节点 {{ raw.milestones?.length || 0 }} 个
            </p>
            <p class="muted hash">文件哈希：{{ raw.file_hash }}</p>
            <p class="muted">
              客户确认：{{ raw.client_confirmed_at || '未确认' }} · 服务商确认：{{
                raw.provider_confirmed_at || '未确认'
              }}
            </p>

            <h4 class="section-title">SLA 条款</h4>
            <div class="sla">
              <div v-for="(value, key) in raw.terms?.sla || {}" :key="key">
                <span>{{ key }}</span>
                <span>{{ value }}</span>
              </div>
            </div>

            <h4 class="section-title">节点表</h4>
            <article
              v-for="milestone in raw.milestones || []"
              :key="milestone.id"
              class="milestone"
            >
              <div class="fact-top">
                <span class="fact-key">
                  {{ milestone.task_code }} {{ milestone.task_name }}
                </span>
                <span class="pill">{{ milestone.status }}</span>
              </div>
              <p class="muted">
                截止 {{ milestone.due_date }} · 验收人 {{ milestone.acceptor_type }} ·
                服务商 {{ milestone.provider_name || '待定' }}
              </p>
              <p class="muted">交付物：{{ milestone.deliverable || '—' }}</p>
            </article>

            <h4 class="section-title">服务商委托单</h4>
            <article
              v-for="providerContract in raw.provider_contracts || []"
              :key="providerContract.id"
              class="client-quote"
            >
              <div class="fact-top">
                <span class="fact-key">{{ providerContract.provider_name }}</span>
                <span class="amount">{{ money(providerContract.total_cents) }}</span>
              </div>
              <p class="muted">
                状态 {{ providerContract.status }} · 确认
                {{ providerContract.provider_confirmed_at || '未确认' }}
              </p>
              <div v-if="isPm" class="actions">
                <button
                  class="small-btn"
                  :disabled="busy"
                  @click="createProviderContractLink(providerContract)"
                >
                  生成服务商链接
                </button>
                <button
                  v-if="providerContractLinks[providerContract.id]"
                  class="small-btn"
                  @click="copyContractText(providerContractLinks[providerContract.id])"
                >
                  复制链接
                </button>
              </div>
            </article>

            <div v-if="isPm && contractClientLink" class="client-link">
              <input :value="contractClientLink" readonly />
              <button @click="copyContractText(contractClientLink)">复制</button>
            </div>

            <p class="disclaimer">{{ raw.terms?.disclaimer }}</p>
          </template>
        </div>

        <div v-else-if="activeType === 'milestones'" class="stack">
          <div class="board-summary" v-if="board">
            <span>共 {{ board.total }} 个节点</span>
            <span v-for="(count, status) in board.summary" :key="status">
              {{ status }} {{ count }}
            </span>
          </div>
          <div v-if="!raw?.length" class="state">暂无节点。合同确认后生成。</div>
          <article v-for="milestone in raw || []" :key="milestone.id" class="milestone">
            <div class="fact-top">
              <span class="fact-key">
                {{ milestone.task_code }} {{ milestone.task_name }}
              </span>
              <span class="pill">{{ milestone.status }}</span>
            </div>
            <p class="muted">
              截止 {{ milestone.due_date || '—' }} · 验收人 {{ milestone.acceptor_type }} ·
              服务商 {{ milestone.provider_name || '待定' }}
            </p>
            <p v-if="milestone.overdue_days" class="overdue">
              逾期 {{ milestone.overdue_days }} 天
            </p>
            <p v-if="milestone.submission_note" class="muted">
              提交说明：{{ milestone.submission_note }}
            </p>
            <p v-if="milestone.pm_review_note" class="muted">
              PM 意见：{{ milestone.pm_review_note }}
            </p>
            <p v-if="milestone.expert_total" class="muted">
              专家评分：{{ milestone.expert_total }}（{{ milestone.expert_locked ? '已锁定' : '未锁定' }}）
            </p>

            <div v-if="isPm" class="actions">
              <button
                v-if="milestone.status === 'pending_submission'"
                class="small-btn"
                @click="submitMilestoneDemo(milestone)"
              >
                提交交付物（演示）
              </button>
              <template v-if="milestone.status === 'submitted'">
                <button class="small-btn" @click="pmReviewMilestone(milestone, 'accept')">
                  初审通过
                </button>
                <button class="small-btn" @click="pmReviewMilestone(milestone, 'return')">
                  退回补充
                </button>
              </template>
              <button
                v-if="milestone.submission_note"
                class="small-btn"
                :disabled="busy"
                @click="runMilestoneReview(milestone)"
              >
                审查答复
              </button>
              <button
                v-if="milestone.status === 'expert_review'"
                class="small-btn"
                :disabled="busy"
                @click="inviteExpert(milestone)"
              >
                邀请专家
              </button>
              <button
                v-if="expertLinks[milestone.id]"
                class="small-btn"
                @click="copyExpertLink(milestone)"
              >
                复制专家链接
              </button>
              <button
                v-if="milestone.expert_locked && ['client_confirm', 'passed', 'conditional'].includes(milestone.status)"
                class="small-btn"
                :disabled="busy"
                @click="finalizeMilestone(milestone)"
              >
                汇总验收
              </button>
              <button
                v-if="milestone.status === 'failed'"
                class="small-btn"
                @click="rectifyMilestone(milestone)"
              >
                进入整改
              </button>
              <button
                v-if="['passed', 'conditional'].includes(milestone.status) && !milestone.client_confirmed_at"
                class="small-btn"
                :disabled="busy"
                @click="clientConfirmMilestone(milestone)"
              >
                客户确认（代）
              </button>
              <button
                v-if="!['passed', 'conditional'].includes(milestone.status)"
                class="small-btn"
                @click="fetchReminder(milestone)"
              >
                生成催办内容
              </button>
              <button
                v-if="reminderDrafts[milestone.id]"
                class="small-btn"
                @click="copyReminder(milestone)"
              >
                复制催办
              </button>
            </div>
          </article>
        </div>

        <div v-else-if="activeType === 'findings'" class="stack">
          <div v-if="!raw?.length" class="state">暂无审查发现。</div>
          <article v-for="finding in raw" :key="finding.id" class="finding">
            <div class="fact-top">
              <span class="fact-key">{{ finding.category }}</span>
              <span class="pill severity">{{ finding.severity }}</span>
            </div>
            <p class="quote-text">“{{ finding.quote_text }}”</p>
            <p class="muted">{{ finding.reason }}</p>
            <p class="question">{{ finding.question_zh }}</p>
            <div class="badges">
              <span class="pill" :class="finding.conclusion_level">
                {{ conclusionLabel(finding.conclusion_level) }}
              </span>
              <span v-if="finding.is_legal" class="pill legal">法律类</span>
            </div>
          </article>
        </div>

        <div v-else-if="activeType === 'review'" class="stack">
          <div class="review-controls">
            <select v-model="reviewMilestoneId" @change="onReviewMilestoneChange">
              <option value="">选择节点</option>
              <option v-for="item in reviewMilestones" :key="item.id" :value="item.id">
                {{ item.task_code }} {{ item.task_name }}
              </option>
            </select>
            <textarea
              v-model="reviewText"
              rows="4"
              placeholder="粘贴服务商答复或交付物文本，然后运行审查"
            ></textarea>
            <div class="toolbar">
              <button :disabled="busy" @click="runReviewFromPanel">运行审查</button>
              <button :disabled="busy" @click="generateQueryLetter">生成质询函</button>
            </div>
          </div>

          <div class="review-grid">
            <div class="review-pane">
              <h4>原文</h4>
              <pre class="review-text"><span
                v-for="(segment, index) in reviewSegments"
                :key="index"
                :class="{ hit: segment.hit }"
              >{{ segment.text }}</span></pre>
            </div>
            <div class="review-pane">
              <h4>发现（{{ reviewFindings.length }}）</h4>
              <button
                v-for="finding in reviewFindings"
                :key="finding.id"
                class="finding-item"
                :class="{ active: selectedReviewFinding?.id === finding.id }"
                @click="selectedReviewFinding = finding"
              >
                <span class="pill severity">{{ finding.severity }}</span>
                <span>{{ finding.category }}</span>
                <span v-if="finding.is_legal" class="pill legal">法律</span>
              </button>
            </div>
            <div class="review-pane">
              <h4>详情</h4>
              <template v-if="selectedReviewFinding">
                <p class="quote-text">“{{ selectedReviewFinding.quote_text }}”</p>
                <p class="muted">{{ selectedReviewFinding.reason }}</p>
                <p class="question">{{ selectedReviewFinding.question_zh }}</p>
                <div class="badges">
                  <span class="pill" :class="selectedReviewFinding.conclusion_level">
                    {{ conclusionLabel(selectedReviewFinding.conclusion_level) }}
                  </span>
                  <span v-if="selectedReviewFinding.is_legal" class="pill legal">法律类</span>
                  <span class="pill">{{ selectedReviewFinding.citation_status }}</span>
                </div>
              </template>
              <div v-else class="state">点击发现查看详情</div>
            </div>
          </div>

          <h4 class="section-title">质询函</h4>
          <div v-if="!queryLetters.length" class="state">暂未生成质询函。</div>
          <article v-for="letter in queryLetters" :key="letter.id" class="rfp">
            <div class="fact-top">
              <span class="fact-key">质询函 · {{ letter.status }}</span>
              <span class="pill">{{ letter.approval_status }}</span>
            </div>
            <p class="muted">
              发现 {{ letter.findings?.length || 0 }} 条 · 审批人角色
              {{ letter.approved_by_role || '—' }}
            </p>
            <pre class="letter-content">{{ letter.content }}</pre>
            <div class="actions">
              <button
                v-if="auth.user?.role === 'lawyer' && letter.approval_status === 'pending'"
                class="small-btn"
                :disabled="busy"
                @click="approveLetter(letter)"
              >
                批准质询函
              </button>
              <button
                v-if="letter.approval_status === 'approved' && letter.status === 'draft'"
                class="small-btn"
                :disabled="busy"
                @click="sendLetter(letter)"
              >
                发送
              </button>
              <button
                v-if="isPm && letter.status === 'sent'"
                class="small-btn"
                :disabled="busy"
                @click="createQueryLink(letter)"
              >
                生成服务商回复链接
              </button>
              <button
                v-if="queryLinks[letter.id]"
                class="small-btn"
                @click="copyQueryLink(letter)"
              >
                复制回复链接
              </button>
              <button
                v-if="isPm && letter.status === 'replied'"
                class="small-btn"
                :disabled="busy"
                @click="closeLetter(letter)"
              >
                关闭质询
              </button>
            </div>
          </article>
        </div>

        <div v-else-if="activeType === 'client-portal'" class="stack">
          <div v-if="!clientPortal" class="state">正在加载客户确认信息…</div>
          <template v-else>
            <div
              v-if="clientPortal.proposal?.status === 'sent'"
              class="confirm-banner"
            >
              <div>
                <strong>有项目建议书待你确认</strong>
                <p>点击右侧“确认建议书”后项目进入「询价」阶段；确认需求不会推进阶段。</p>
              </div>
              <button
                class="small-btn primary"
                :disabled="busy"
                @click="clientConfirmProposal"
              >
                确认建议书
              </button>
            </div>

            <h4 class="section-title">需求确认</h4>
            <article class="client-quote">
              <template v-if="clientPortal.requirement">
                <div class="fact-top">
                  <span class="fact-key">需求确认书</span>
                  <span class="pill" :class="{ confirmed: clientPortal.requirement.confirmed_at }">
                    {{ clientPortal.requirement.confirmed_at ? '已确认' : '待确认' }}
                  </span>
                </div>
                <p class="muted">{{ clientPortal.requirement.scope_statement }}</p>
                <button
                  v-if="!clientPortal.requirement.confirmed_at"
                  class="small-btn"
                  :disabled="busy"
                  @click="clientConfirmRequirement"
                >
                  确认需求
                </button>
              </template>
              <div v-else class="state">需求确认书尚未生成。</div>
            </article>

            <h4 class="section-title">建议书</h4>
            <article class="client-quote">
              <template v-if="clientPortal.proposal">
                <div class="fact-top">
                  <span class="fact-key">v{{ clientPortal.proposal.version }}</span>
                  <span class="pill">{{ proposalStatusLabel(clientPortal.proposal.status) }}</span>
                </div>
                <article
                  v-for="chapter in clientPortal.proposal.content?.chapters || []"
                  :key="chapter.id"
                  class="chapter"
                >
                  <h4>{{ chapter.id }}. {{ chapter.title }}</h4>
                  <p>{{ chapter.content }}</p>
                </article>
                <div class="actions">
                  <template v-if="clientPortal.proposal.status === 'sent'">
                    <button class="small-btn primary" :disabled="busy" @click="clientConfirmProposal">
                      确认建议书
                    </button>
                    <button class="small-btn" :disabled="busy" @click="clientReviseProposal">
                      提出修改
                    </button>
                  </template>
                  <span v-if="clientPortal.proposal.client_note" class="muted">
                    修改意见：{{ clientPortal.proposal.client_note }}
                  </span>
                </div>
              </template>
              <div v-else class="state">暂无已发送的建议书。</div>
            </article>

            <h4 class="section-title">总报价</h4>
            <article class="client-quote">
              <template v-if="clientPortal.client_quote">
                <div class="fact-top">
                  <span class="fact-key">v{{ clientPortal.client_quote.version }}</span>
                  <span class="amount">{{ money(clientPortal.client_quote.total_cents) }}</span>
                </div>
                <p class="muted">
                  服务商 {{ money(clientPortal.client_quote.provider_amount_cents) }} ·
                  管理费 {{ money(clientPortal.client_quote.management_fee_cents) }}
                </p>
                <button
                  v-if="clientPortal.client_quote.status === 'sent'"
                  class="small-btn"
                  :disabled="busy"
                  @click="clientConfirmQuote"
                >
                  确认总报价
                </button>
                <span v-else class="pill confirmed">已确认</span>
              </template>
              <div v-else class="state">暂无已发送的总报价。</div>
            </article>

            <h4 class="section-title">合同</h4>
            <article class="client-quote">
              <template v-if="clientPortal.contract">
                <div class="fact-top">
                  <span class="fact-key">委托确认单 v{{ clientPortal.contract.version }}</span>
                  <span class="pill">{{ clientPortal.contract.status }}</span>
                </div>
                <p class="muted">
                  总价 {{ money(clientPortal.contract.total_cents) }} · 节点
                  {{ clientPortal.contract.milestones?.length || 0 }} 个
                </p>
                <button
                  v-if="clientPortal.contract.status === 'pending_client'"
                  class="small-btn"
                  :disabled="busy"
                  @click="clientConfirmContract"
                >
                  确认合同
                </button>
              </template>
              <div v-else class="state">暂无待确认合同。</div>
            </article>

            <h4 class="section-title">节点确认</h4>
            <div v-if="!clientPortal.milestones?.length" class="state">暂无节点。</div>
            <article
              v-for="milestone in clientPortal.milestones || []"
              :key="milestone.id"
              class="milestone"
            >
              <div class="fact-top">
                <span class="fact-key">{{ milestone.name }}</span>
                <span class="pill">{{ milestone.status }}</span>
              </div>
              <p class="muted">
                截止 {{ milestone.due_date || '—' }} · 客户确认
                {{ milestone.client_confirmed_at || '未确认' }}
              </p>
              <button
                v-if="['passed', 'conditional'].includes(milestone.status) && !milestone.client_confirmed_at"
                class="small-btn"
                :disabled="busy"
                @click="clientConfirmPortalMilestone(milestone)"
              >
                确认节点
              </button>
            </article>
          </template>
        </div>

        <div v-else-if="activeType === 'requirement'" class="stack">
          <div class="toolbar">
            <button v-if="isPm" :disabled="busy" @click="generateRequirement">
              {{ raw ? '重新生成确认书' : '生成需求确认书' }}
            </button>
            <button v-if="raw" @click="printPanel">打印</button>
            <button v-if="isPm && raw" :disabled="busy" @click="createClientLink">
              生成客户链接
            </button>
          </div>

          <div v-if="!raw" class="state">
            {{ isPm ? '尚未生成需求确认书。' : '需求确认书尚未生成。' }}
          </div>
          <template v-else>
            <div class="proposal-head">
              <h3>{{ raw.title }}</h3>
              <span v-if="raw.confirmed_at" class="pill confirmed">客户已确认</span>
            </div>
            <p class="muted">{{ raw.project_name }} · {{ raw.client_name }}</p>
            <p class="req-scope">{{ raw.scope_statement }}</p>

            <h4 class="req-heading">事实基础</h4>
            <div v-for="fact in raw.facts || []" :key="fact.key" class="req-fact">
              <span class="req-key">{{ fact.key }}</span>
              <span class="req-value">{{ fact.value }}</span>
              <span class="pill" :class="fact.status">{{ statusLabel(fact.status) }}</span>
            </div>

            <h4 class="req-heading">任务范围</h4>
            <p class="muted">
              共 {{ raw.task_summary.total }} 项 · 总周期
              {{ raw.task_summary.total_days }} 天
            </p>
            <p class="muted">
              关键路径：{{ (raw.task_summary.critical_path || []).join(' → ') }}
            </p>

            <p class="disclaimer">{{ raw.disclaimer }}</p>
            <p v-if="raw.confirmed_at" class="muted">
              客户确认时间：{{ raw.confirmed_at }}
            </p>

            <div v-if="isPm && clientLink" class="client-link">
              <input :value="clientLink" readonly />
              <button @click="copyLink">复制</button>
            </div>
          </template>
        </div>

        <div v-else-if="activeType === 'archive'" class="stack">
          <div class="toolbar">
            <button :disabled="busy" @click="generateRetrospective">生成复盘</button>
            <button :disabled="busy || projectInfo?.archived" @click="createArchive">
              {{ projectInfo?.archived ? '已归档' : '生成归档包' }}
            </button>
            <button :disabled="busy" @click="resetDemo">一键重置演示</button>
          </div>

          <div v-if="projectInfo?.archived" class="confirmed">
            项目已归档，当前为只读状态。
          </div>

          <div v-if="archiveData?.metrics" class="metrics-grid">
            <div class="rate-card">
              <span>有效质询率</span>
              <strong>{{ rateText(archiveData.metrics.effective_query_rate) }}</strong>
            </div>
            <div class="rate-card">
              <span>重大事项关闭率</span>
              <strong>{{ rateText(archiveData.metrics.major_close_rate) }}</strong>
            </div>
            <div class="rate-card">
              <span>节点按期率</span>
              <strong>{{ rateText(archiveData.metrics.milestone_on_time_rate) }}</strong>
            </div>
            <div class="rate-card muted-card">
              <span>有效匹配率</span>
              <strong>数据不足</strong>
            </div>
            <div class="rate-card muted-card">
              <span>实际可承接率</span>
              <strong>数据不足</strong>
            </div>
          </div>

          <template v-if="archiveData?.retrospective">
            <h4 class="section-title">复盘报告</h4>
            <div class="retro">
              <p>
                计划预算 {{ money(archiveData.retrospective.budget?.planned_cents) }} ·
                实际 {{ money(archiveData.retrospective.budget?.actual_cents) }} ·
                偏差 {{ archiveData.retrospective.budget?.variance_percent ?? '—' }}%
              </p>
              <p>
                发现 {{ archiveData.retrospective.issues?.total || 0 }} 条，其中重大
                {{ archiveData.retrospective.issues?.major || 0 }} 条，未关闭重大
                {{ archiveData.retrospective.issues?.major_open || 0 }} 条。
              </p>
              <p>
                履约事件 {{ archiveData.retrospective.provider_performance?.events || 0 }} 条；
                专家均分
                {{ archiveData.retrospective.provider_performance?.average_expert_score ?? '—' }}
              </p>
              <p class="muted">
                关键路径计划 {{ archiveData.retrospective.critical_path_variance?.scheduled_days || 0 }} 天
              </p>
            </div>
          </template>

          <h4 class="section-title">报价基准</h4>
          <div v-if="!archiveData?.benchmarks?.length" class="state">暂无报价基准。</div>
          <article
            v-for="benchmark in archiveData?.benchmarks || []"
            :key="benchmark.task_code"
            class="quote-row"
          >
            <div class="fact-top">
              <span class="fact-key">{{ benchmark.task_code }} {{ benchmark.task_name }}</span>
              <span class="pill">{{ benchmark.sample_count }} 个样本</span>
            </div>
            <p class="muted">
              最低 {{ money(benchmark.min_cents) }} · 中位
              {{ money(benchmark.median_cents) }} · 最高 {{ money(benchmark.max_cents) }}
            </p>
            <p v-if="!benchmark.data_sufficient" class="muted">
              数据不足 3 个样本，仅作参考。
            </p>
          </article>

          <h4 class="section-title">归档包</h4>
          <div v-if="!archiveData?.archives?.length" class="state">
            暂无归档包。需所有节点通过、客户确认且无未关闭重大发现。
          </div>
          <article
            v-for="archive in archiveData?.archives || []"
            :key="archive.id"
            class="client-quote"
          >
            <div class="fact-top">
              <span class="fact-key">v{{ archive.version }}</span>
              <span class="pill">{{ archive.retention_until }}</span>
            </div>
            <p class="muted hash">哈希：{{ archive.file_hash }}</p>
            <div class="actions">
              <button class="small-btn" @click="downloadArchive(archive)">下载 zip</button>
            </div>
          </article>
        </div>
        <div v-else class="state">当前阶段暂无你可见的内容。</div>
      </template>
    </div>

    <DocumentDialog v-model="docVisible" :citation="selectedCitation" />
    <KnowledgeDialog v-model="chunkVisible" :chunk-id="selectedChunkId" />
  </aside>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import client from '../api/client'
import { useAuthStore } from '../stores/auth'
import DocumentDialog from './DocumentDialog.vue'
import KnowledgeDialog from './KnowledgeDialog.vue'
import TaskGraph from './TaskGraph.vue'

const props = defineProps({
  projectId: { type: String, default: '' },
  refreshToken: { type: Number, default: 0 },
  phase: { type: Number, default: 1 }
})
const emit = defineEmits(['demo-reset', 'refresh-project'])

const tabs = [
  { key: 'facts', label: '事实' },
  { key: 'tasks', label: '任务' },
  { key: 'proposal', label: '建议书' },
  { key: 'selection', label: '选服务' },
  { key: 'candidates', label: '服务商' },
  { key: 'quotes', label: '报价' },
  { key: 'contract', label: '合同' },
  { key: 'milestones', label: '节点' },
  { key: 'findings', label: '发现' },
  { key: 'review', label: '审查' },
  { key: 'requirement', label: '需求' },
  { key: 'client-portal', label: '客户确认' },
  { key: 'archive', label: '归档' }
]

// 交付按项目阶段分组；phase 为该组所需达到的阶段编号
const phaseGroups = [
  { phase: 1, key: 'p1', label: '调研', keys: ['facts', 'tasks', 'requirement'] },
  { phase: 2, key: 'p2', label: '建议', keys: ['proposal'] },
  { phase: 3, key: 'p3', label: '询价', keys: ['selection', 'candidates'] },
  { phase: 4, key: 'p4', label: '报价', keys: ['quotes'] },
  { phase: 5, key: 'p5', label: '签约', keys: ['contract'] },
  { phase: 6, key: 'p6', label: '履约', keys: ['milestones', 'findings', 'review'] },
  { phase: 7, key: 'p7', label: '归档', keys: ['archive'] }
]
const portalGroup = { phase: 0, key: 'portal', label: '确认', keys: ['client-portal'] }

const activePhase = ref(1)
const activeType = ref('facts')

const tabsByKey = Object.fromEntries(tabs.map((tab) => [tab.key, tab]))

function tabsForPhase(phase) {
  const allowed = new Set(visibleTabs.value.map((tab) => tab.key))
  if (phase === 0) {
    return allowed.has('client-portal') ? [tabsByKey['client-portal']] : []
  }
  const group = phaseGroups.find((item) => item.phase === phase)
  if (!group) return []
  return group.keys
    .filter((key) => allowed.has(key))
    .map((key) => tabsByKey[key])
    .filter(Boolean)
}

function selectPhase(phase) {
  const item = phaseNav.value.find((entry) => entry.phase === phase)
  if (!item || item.locked) return
  activePhase.value = phase
  const list = tabsForPhase(phase)
  activeType.value = list[0]?.key || ''
}

function setTab(key) {
  if (!visibleTabs.value.some((tab) => tab.key === key)) return
  const group =
    key === 'client-portal'
      ? portalGroup
      : phaseGroups.find((item) => item.keys.includes(key))
  if (group) activePhase.value = group.phase
  activeType.value = key
}

defineExpose({ setTab })
const raw = ref(null)
const loading = ref(false)
const error = ref('')
const panelFull = ref(false)
const docVisible = ref(false)
const selectedCitation = ref(null)
const questions = ref([])
const busy = ref(false)
const scenario = ref('lease')
const graphData = ref(null)
const clientLink = ref('')
const proposalVersions = ref([])
const selectedVersionId = ref('')
const comparison = ref(null)
const proposalLink = ref('')
const chunkVisible = ref(false)
const selectedChunkId = ref('')
const catalog = ref(null)
const selectedCodes = ref([])
const overrideReason = ref('')
const selectionLink = ref('')
const candidateGroups = ref([])
const clientQuotes = ref([])
const clientQuoteLink = ref('')
const providerContractLinks = ref({})
const contractClientLink = ref('')
const board = ref(null)
const reviewMilestones = ref([])
const reviewMilestoneId = ref('')
const reviewText = ref('')
const reviewFindings = ref([])
const selectedReviewFinding = ref(null)
const queryLetters = ref([])
const queryLinks = ref({})
const expertLinks = ref({})
const reminderDrafts = ref({})
const archiveData = ref(null)
const projectInfo = ref(null)
const clientPortal = ref(null)
const auth = useAuthStore()
const isClient = computed(() => auth.user?.role === 'client')
const isPm = computed(() => ['pm', 'admin'].includes(auth.user?.role))
const isLawyer = computed(() => auth.user?.role === 'lawyer')
const visibleTabs = computed(() => {
  if (isClient.value) {
    return tabs.filter((tab) =>
      ['facts', 'tasks', 'selection', 'milestones', 'requirement', 'client-portal'].includes(
        tab.key
      )
    )
  }
  if (isLawyer.value) {
    return tabs.filter(
      (tab) =>
        ![
          'selection',
          'candidates',
          'proposal',
          'quotes',
          'contract',
          'archive',
          'client-portal'
        ].includes(tab.key)
    )
  }
  return tabs.filter((tab) => tab.key !== 'client-portal')
})
const currentPhase = computed(() => Number(props.phase) || 1)
const phaseNav = computed(() => {
  const items = phaseGroups.map((group) => ({
    phase: group.phase,
    label: group.label,
    locked: group.phase > currentPhase.value
  }))
  if (visibleTabs.value.some((tab) => tab.key === 'client-portal')) {
    items.push({ phase: 0, label: '确认', locked: false })
  }
  return items
})
const phaseTabs = computed(() => tabsForPhase(activePhase.value))

watch(
  () => props.projectId,
  () => {
    const target = Math.min(Math.max(currentPhase.value, 1), 7)
    const list = tabsForPhase(target)
    if (list.length) {
      activePhase.value = target
      activeType.value = list[0].key
      return
    }
    const fallback = phaseNav.value.find(
      (item) => !item.locked && tabsForPhase(item.phase).length
    )
    if (fallback) {
      activePhase.value = fallback.phase
      activeType.value = tabsForPhase(fallback.phase)[0].key
    }
  }
)
const quoteForm = ref({
  providerYuan: '',
  lawyerYuan: '0',
  feeRate: '17.5'
})

const selectionWarnings = computed(() => {
  const items = (catalog.value?.stages || []).flatMap((stage) => stage.items)
  const byCode = Object.fromEntries(items.map((item) => [item.code, item]))
  const selected = new Set(selectedCodes.value)
  const warnings = []
  for (const code of selectedCodes.value) {
    const item = byCode[code]
    if (!item) continue
    for (const predecessor of item.predecessors || []) {
      if (!selected.has(predecessor)) {
        warnings.push(
          `${code} 需要前置 ${predecessor}，请同时选择或确认平台另行安排`
        )
      }
    }
  }
  return warnings
})

const latestClientQuote = computed(() => clientQuotes.value[0] || null)

const reviewSegments = computed(() => {
  const text = reviewText.value || ''
  const finding = selectedReviewFinding.value
  const quote = finding?.quote_text
  if (!text) return []
  if (!quote) return [{ text, hit: false }]
  const index = text.indexOf(quote)
  if (index < 0) return [{ text, hit: false }]
  return [
    { text: text.slice(0, index), hit: false },
    { text: text.slice(index, index + quote.length), hit: true },
    { text: text.slice(index + quote.length), hit: false }
  ]
})

const graphDiff = computed(() => graphData.value?.diff || null)

const taskGroups = computed(() => {
  const groups = new Map()
  for (const task of raw.value || []) {
    if (!groups.has(task.stage_no)) {
      groups.set(task.stage_no, [])
    }
    groups.get(task.stage_no).push(task)
  }
  return [...groups.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([stage, items]) => ({ stage, items }))
})

function statusLabel(value) {
  return (
    {
      confirmed: '已确认',
      assumption: '客户假设',
      unknown: '未知'
    }[value] || value
  )
}

function conclusionLabel(value) {
  return (
    {
      verified_error: '已核实错误',
      needs_verification: '需进一步核实',
      professional_judgment: '不同专业判断'
    }[value] || value
  )
}

function money(cents) {
  const value = Number(cents || 0) / 100
  return `${value.toLocaleString('zh-CN')} 元`
}

function rateText(item) {
  if (!item || item.value === null || item.value === undefined) return '数据不足'
  return `${item.value}%`
}

function proposalStatusLabel(value) {
  return (
    {
      generated: '待审核',
      pm_reviewed: 'PM 已审核',
      sent: '已发送客户',
      client_confirmed: '客户已确认',
      revision_requested: '客户要求修改'
    }[value] || value
  )
}

function scrollToChapter(id) {
  const element = document.getElementById(`proposal-chapter-${id}`)
  if (element) element.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function openChunk(chunkId) {
  selectedChunkId.value = chunkId
  chunkVisible.value = true
}

function openCitation(citation) {
  selectedCitation.value = citation
  docVisible.value = true
}

async function load() {
  if (!props.projectId) return
  if (!activeType.value) {
    raw.value = null
    graphData.value = null
    loading.value = false
    error.value = ''
    return
  }
  loading.value = true
  error.value = ''
  try {
    if (activeType.value === 'tasks') {
      const response = await client.get(`/projects/${props.projectId}/task-graph`)
      graphData.value = response.data.data
      raw.value = response.data.data.tasks
      scenario.value = response.data.data.scenario || 'lease'
    } else if (activeType.value === 'proposal') {
      const response = await client.get(
        `/projects/${props.projectId}/proposals`
      )
      proposalVersions.value = response.data.data
      if (!proposalVersions.value.length) {
        raw.value = null
        selectedVersionId.value = ''
      } else {
        const selected =
          proposalVersions.value.find(
            (item) => item.id === selectedVersionId.value
          ) || proposalVersions.value[0]
        selectedVersionId.value = selected.id
        const detail = await client.get(`/proposals/${selected.id}`)
        raw.value = detail.data.data
      }
    } else if (activeType.value === 'selection') {
      const response = await client.get(
        `/projects/${props.projectId}/service-catalog`
      )
      catalog.value = response.data.data
      selectedCodes.value = [...(response.data.data.selection.codes || [])]
      overrideReason.value = response.data.data.selection.override_reason || ''
      raw.value = response.data.data
    } else if (activeType.value === 'candidates') {
      const response = await client.get(
        `/projects/${props.projectId}/candidates`
      )
      candidateGroups.value = response.data.data
      raw.value = response.data.data
    } else if (activeType.value === 'quotes') {
      const [rfps, comparison, quotes] = await Promise.all([
        client.get(`/projects/${props.projectId}/rfps`),
        client.get(`/projects/${props.projectId}/quote-comparison`),
        client.get(`/projects/${props.projectId}/client-quotes`)
      ])
      raw.value = {
        rfps: rfps.data.data,
        comparison: comparison.data.data,
        clientQuotes: quotes.data.data
      }
      clientQuotes.value = quotes.data.data
      if (
        !quoteForm.value.providerYuan &&
        comparison.data.data.provider_amount_cents
      ) {
        quoteForm.value.providerYuan = String(
          comparison.data.data.provider_amount_cents / 100
        )
      }
    } else if (activeType.value === 'contract') {
      const response = await client.get(
        `/projects/${props.projectId}/contracts`
      )
      raw.value = response.data.data[0] || null
    } else if (activeType.value === 'milestones') {
      const response = await client.get(
        `/projects/${props.projectId}/board`
      )
      board.value = response.data.data
      raw.value = response.data.data.milestones
    } else if (activeType.value === 'review') {
      const [boardResponse, findingsResponse, lettersResponse] =
        await Promise.all([
          client.get(`/projects/${props.projectId}/board`),
          client.get(`/projects/${props.projectId}/artifacts`, {
            params: { type: 'findings' }
          }),
          client.get(`/projects/${props.projectId}/query-letters`)
        ])
      board.value = boardResponse.data.data
      reviewMilestones.value = boardResponse.data.data.milestones || []
      reviewFindings.value = findingsResponse.data.data
      queryLetters.value = lettersResponse.data.data
      if (!reviewMilestoneId.value && reviewMilestones.value.length) {
        reviewMilestoneId.value = reviewMilestones.value[0].id
      }
      raw.value = findingsResponse.data.data
    } else if (activeType.value === 'archive') {
      const [retrospective, benchmarks, metrics, archives, project] =
        await Promise.all([
          client
            .get(`/projects/${props.projectId}/retrospective`)
            .catch((err) => {
              if (err.response?.status === 404) return { data: { data: null } }
              throw err
            }),
          client.get('/benchmarks'),
          client.get(`/projects/${props.projectId}/metrics`),
          client.get(`/projects/${props.projectId}/archives`),
          client.get(`/projects/${props.projectId}`)
        ])
      archiveData.value = {
        retrospective: retrospective.data.data,
        benchmarks: benchmarks.data.data,
        metrics: metrics.data.data,
        archives: archives.data.data
      }
      projectInfo.value = project.data.data
      raw.value = archiveData.value
    } else if (activeType.value === 'client-portal') {
      const response = await client.get(
        `/projects/${props.projectId}/client-portal`
      )
      clientPortal.value = response.data.data
      raw.value = response.data.data
    } else if (activeType.value === 'requirement') {
      try {
        const response = await client.get(`/projects/${props.projectId}/requirement`)
        raw.value = response.data.data
      } catch (err) {
        if (err.response?.status === 404) {
          raw.value = null
        } else {
          throw err
        }
      }
    } else {
      const response = await client.get(
        `/projects/${props.projectId}/artifacts`,
        { params: { type: activeType.value } }
      )
      raw.value = response.data.data
    }
    emit('refresh-project')
  } catch (err) {
    error.value = err.response?.data?.message || '工作台加载失败'
  } finally {
    loading.value = false
  }
}

async function extractFacts() {
  if (!props.projectId || busy.value) return
  busy.value = true
  try {
    const response = await client.post(
      `/projects/${props.projectId}/facts/extract`
    )
    const data = response.data.data
    raw.value = data.facts
    ElMessage.success(`提取 ${data.facts.length} 条事实，核实 ${data.verified} 条`)
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '事实提取失败')
  } finally {
    busy.value = false
  }
}

async function generateQuestions() {
  if (!props.projectId || busy.value) return
  busy.value = true
  try {
    const response = await client.post(
      `/projects/${props.projectId}/interview`,
      {}
    )
    questions.value = response.data.data.questions
    ElMessage.success(`已生成 ${questions.value.length} 个追问`)
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '追问生成失败')
  } finally {
    busy.value = false
  }
}

async function refreshTasks(nextScenario) {
  if (!props.projectId || busy.value) return
  busy.value = true
  try {
    const response = await client.post(
      `/projects/${props.projectId}/tasks/refresh`,
      { scenario: nextScenario }
    )
    graphData.value = response.data.data
    raw.value = response.data.data.tasks
    scenario.value = nextScenario
    ElMessage.success(
      nextScenario === 'lease' ? '已按租厂房生成任务地图' : '已按园区外买地生成任务地图'
    )
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '任务地图生成失败')
  } finally {
    busy.value = false
  }
}

async function generateRequirement() {
  if (!props.projectId || busy.value) return
  busy.value = true
  try {
    const response = await client.post(
      `/projects/${props.projectId}/requirement`
    )
    raw.value = response.data.data
    ElMessage.success('需求确认书已生成')
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '需求确认书生成失败')
  } finally {
    busy.value = false
  }
}

async function generateProposal() {
  if (!props.projectId || busy.value) return
  busy.value = true
  try {
    await client.post(`/projects/${props.projectId}/proposals`)
    selectedVersionId.value = ''
    comparison.value = null
    proposalLink.value = ''
    await load()
    ElMessage.success('项目建议书已生成')
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '建议书生成失败')
  } finally {
    busy.value = false
  }
}

async function selectVersion() {
  if (!selectedVersionId.value) return
  loading.value = true
  comparison.value = null
  try {
    const response = await client.get(`/proposals/${selectedVersionId.value}`)
    raw.value = response.data.data
  } catch (err) {
    error.value = err.response?.data?.message || '版本加载失败'
  } finally {
    loading.value = false
  }
}

async function reviewProposal() {
  if (!raw.value || busy.value) return
  busy.value = true
  try {
    const response = await client.post(`/proposals/${raw.value.id}/review`)
    raw.value = response.data.data
    ElMessage.success('已审核，可发送客户')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '审核失败')
  } finally {
    busy.value = false
  }
}

async function sendProposal() {
  if (!raw.value || busy.value) return
  busy.value = true
  try {
    const response = await client.post(`/proposals/${raw.value.id}/send`)
    raw.value = response.data.data
    ElMessage.success('建议书已标记为发送')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '发送失败')
  } finally {
    busy.value = false
  }
}

async function createProposalLink() {
  if (!props.projectId || busy.value) return
  busy.value = true
  try {
    const response = await client.post('/access-tokens', {
      project_id: props.projectId,
      role_type: 'client',
      subject_id: 'client'
    })
    proposalLink.value = `${window.location.origin}/proposal-link/${response.data.data.token}`
    ElMessage.success('客户确认链接已生成')
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '链接生成失败')
  } finally {
    busy.value = false
  }
}

async function copyProposalLink() {
  try {
    await navigator.clipboard.writeText(proposalLink.value)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}

async function compareProposal() {
  if (!raw.value || busy.value) return
  const index = proposalVersions.value.findIndex(
    (item) => item.id === raw.value.id
  )
  const previous = proposalVersions.value[index + 1]
  if (!previous) {
    ElMessage.warning('没有更早版本可对比')
    return
  }

  busy.value = true
  try {
    const response = await client.get(`/proposals/${previous.id}`)
    const oldContent = response.data.data.content || {}
    const oldChapters = new Map(
      (oldContent.chapters || []).map((chapter) => [chapter.id, chapter.content])
    )
    const changed = (raw.value.content?.chapters || [])
      .filter((chapter) => oldChapters.get(chapter.id) !== chapter.content)
      .map((chapter) => chapter.id)
    comparison.value = { fromVersion: previous.version, changed }
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '版本对比失败')
  } finally {
    busy.value = false
  }
}

async function saveSelection() {
  if (!props.projectId || busy.value) return
  if (isPm.value && !overrideReason.value.trim()) {
    ElMessage.warning('PM 代选需要填写原因')
    return
  }
  busy.value = true
  try {
    const response = await client.post(
      `/projects/${props.projectId}/selection`,
      {
        codes: selectedCodes.value,
        override_reason: isPm.value ? overrideReason.value : undefined
      }
    )
    catalog.value = response.data.data
    raw.value = response.data.data
    ElMessage.success('服务选择已保存')
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '保存失败')
  } finally {
    busy.value = false
  }
}

async function createSelectionLink() {
  if (!props.projectId || busy.value) return
  busy.value = true
  try {
    const response = await client.post('/access-tokens', {
      project_id: props.projectId,
      role_type: 'client',
      subject_id: 'client'
    })
    selectionLink.value = `${window.location.origin}/selection-link/${response.data.data.token}`
    ElMessage.success('客户选择链接已生成')
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '链接生成失败')
  } finally {
    busy.value = false
  }
}

async function copySelectionLink() {
  try {
    await navigator.clipboard.writeText(selectionLink.value)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}

async function ensureSelection() {
  if (!catalog.value) {
    const response = await client.get(
      `/projects/${props.projectId}/service-catalog`
    )
    catalog.value = response.data.data
    selectedCodes.value = [...(response.data.data.selection.codes || [])]
  }
  return selectedCodes.value
}

async function generateCandidates() {
  if (!props.projectId || busy.value) return
  const codes = await ensureSelection()
  if (!codes.length) {
    ElMessage.warning('请先在“选服务”中勾选服务项')
    return
  }
  busy.value = true
  try {
    const response = await client.post(
      `/projects/${props.projectId}/candidates/generate`,
      { task_codes: codes }
    )
    candidateGroups.value = response.data.data
    raw.value = response.data.data
    ElMessage.success('候选服务商已生成')
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '候选生成失败')
  } finally {
    busy.value = false
  }
}

async function rejectCandidate(candidate) {
  try {
    const { value } = await ElMessageBox.prompt(
      '请填写不合适的原因',
      '标记不合适',
      { inputValidator: (input) => Boolean(input?.trim()) || '原因不能为空' }
    )
    await client.post(`/candidates/${candidate.id}/reject`, { reason: value })
    ElMessage.success('已标记为不合适')
    const response = await client.get(
      `/projects/${props.projectId}/candidates`
    )
    candidateGroups.value = response.data.data
    raw.value = response.data.data
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error(err.response?.data?.message || '操作失败')
    }
  }
}

async function createRfps() {
  if (!props.projectId || busy.value) return
  const codes = await ensureSelection()
  if (!codes.length) {
    ElMessage.warning('请先选择服务')
    return
  }
  busy.value = true
  try {
    const response = await client.post(
      `/projects/${props.projectId}/rfps`,
      { task_codes: codes }
    )
    ElMessage.success(`已生成 ${response.data.data.length} 份询价书`)
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '询价书生成失败')
  } finally {
    busy.value = false
  }
}

async function approveRfp(rfp) {
  busy.value = true
  try {
    await client.post(`/rfps/${rfp.id}/approve`)
    ElMessage.success('已批准')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '批准失败')
  } finally {
    busy.value = false
  }
}

async function sendRfp(rfp) {
  busy.value = true
  try {
    await client.post(`/rfps/${rfp.id}/send`)
    ElMessage.success('询价书已发送')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '发送失败')
  } finally {
    busy.value = false
  }
}

async function copyRfpLink(rfp) {
  const url = `${window.location.origin}${rfp.link}`
  try {
    await navigator.clipboard.writeText(url)
    ElMessage.success('服务商链接已复制')
  } catch {
    ElMessage.warning('复制失败，请手动复制：' + url)
  }
}

async function createClientQuote() {
  if (!props.projectId || busy.value) return
  busy.value = true
  try {
    const response = await client.post(
      `/projects/${props.projectId}/client-quotes`,
      {
        provider_amount_cents: Math.round(
          Number(quoteForm.value.providerYuan || 0) * 100
        ),
        lawyer_amount_cents: Math.round(
          Number(quoteForm.value.lawyerYuan || 0) * 100
        ),
        management_fee_rate: Number(quoteForm.value.feeRate || 17.5) / 100
      }
    )
    ElMessage.success(`已生成总报价 v${response.data.data.version}`)
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '总报价生成失败')
  } finally {
    busy.value = false
  }
}

async function sendClientQuote(quote) {
  busy.value = true
  try {
    await client.post(`/client-quotes/${quote.id}/send`)
    ElMessage.success('总报价已发送')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '发送失败')
  } finally {
    busy.value = false
  }
}

async function createClientQuoteLink() {
  if (!props.projectId || busy.value) return
  busy.value = true
  try {
    const response = await client.post('/access-tokens', {
      project_id: props.projectId,
      role_type: 'client',
      subject_id: 'client'
    })
    clientQuoteLink.value = `${window.location.origin}/client-quote-link/${response.data.data.token}`
    ElMessage.success('客户总报价链接已生成')
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '链接生成失败')
  } finally {
    busy.value = false
  }
}

async function copyClientQuoteLink() {
  try {
    await navigator.clipboard.writeText(clientQuoteLink.value)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}

async function generateContract() {
  if (!props.projectId || busy.value) return
  busy.value = true
  try {
    await client.post(`/projects/${props.projectId}/contracts`)
    ElMessage.success('合同与节点已生成')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '合同生成失败')
  } finally {
    busy.value = false
  }
}

async function reviewContract() {
  if (!raw.value || busy.value) return
  busy.value = true
  try {
    await client.post(`/contracts/${raw.value.id}/review`)
    ElMessage.success('合同已复核，可发客户确认')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '复核失败')
  } finally {
    busy.value = false
  }
}

async function createContractClientLink() {
  if (!props.projectId || busy.value) return
  busy.value = true
  try {
    const response = await client.post('/access-tokens', {
      project_id: props.projectId,
      role_type: 'client',
      subject_id: 'client'
    })
    contractClientLink.value = `${window.location.origin}/contract-link/${response.data.data.token}`
    ElMessage.success('客户合同链接已生成')
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '链接生成失败')
  } finally {
    busy.value = false
  }
}

async function createProviderContractLink(providerContract) {
  if (!props.projectId || busy.value) return
  busy.value = true
  try {
    const response = await client.post('/access-tokens', {
      project_id: props.projectId,
      role_type: 'provider',
      subject_id: providerContract.provider_id
    })
    providerContractLinks.value = {
      ...providerContractLinks.value,
      [providerContract.id]: `${window.location.origin}/contract-link/${response.data.data.token}`
    }
    ElMessage.success('服务商确认链接已生成')
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '链接生成失败')
  } finally {
    busy.value = false
  }
}

async function copyContractText(text) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选择：' + text)
  }
}

async function submitMilestoneDemo(milestone) {
  try {
    const { value } = await ElMessageBox.prompt(
      '填写交付说明或粘贴答复文本',
      '提交交付物（演示）',
      { inputType: 'textarea', inputValidator: (v) => Boolean(v?.trim()) || '请填写内容' }
    )
    await client.post(`/milestones/${milestone.id}/submission`, {
      note: value
    })
    ElMessage.success('交付物已提交')
    await load()
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error(err.response?.data?.message || '提交失败')
    }
  }
}

async function pmReviewMilestone(milestone, decision) {
  try {
    let note = ''
    if (decision === 'return') {
      const result = await ElMessageBox.prompt('请填写退回原因', '退回补充', {
        inputValidator: (v) => Boolean(v?.trim()) || '原因不能为空'
      })
      note = result.value
    }
    await client.post(`/milestones/${milestone.id}/pm-review`, {
      decision,
      note
    })
    ElMessage.success(decision === 'accept' ? '初审通过' : '已退回')
    await load()
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error(err.response?.data?.message || '操作失败')
    }
  }
}

async function runMilestoneReview(milestone) {
  busy.value = true
  try {
    const response = await client.post(`/milestones/${milestone.id}/review`, {})
    reviewMilestoneId.value = milestone.id
    activeType.value = 'review'
    ElMessage.success(`审查完成，发现 ${response.data.data.length} 条`)
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '审查失败')
  } finally {
    busy.value = false
  }
}

function onReviewMilestoneChange() {
  const milestone = reviewMilestones.value.find(
    (item) => item.id === reviewMilestoneId.value
  )
  reviewText.value = milestone?.submission_note || ''
  selectedReviewFinding.value = null
}

async function runReviewFromPanel() {
  if (!reviewMilestoneId.value) {
    ElMessage.warning('请选择节点')
    return
  }
  busy.value = true
  try {
    const response = await client.post(
      `/milestones/${reviewMilestoneId.value}/review`,
      { text: reviewText.value }
    )
    ElMessage.success(`审查完成，发现 ${response.data.data.length} 条`)
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '审查失败')
  } finally {
    busy.value = false
  }
}

async function inviteExpert(milestone) {
  busy.value = true
  try {
    const response = await client.post(
      `/milestones/${milestone.id}/expert-invite`
    )
    expertLinks.value = {
      ...expertLinks.value,
      [milestone.id]: `${window.location.origin}/expert-link/${response.data.data.token}`
    }
    ElMessage.success('专家评审链接已生成')
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '邀请失败')
  } finally {
    busy.value = false
  }
}

async function copyExpertLink(milestone) {
  const link = expertLinks.value[milestone.id]
  if (!link) return
  try {
    await navigator.clipboard.writeText(link)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选择：' + link)
  }
}

async function finalizeMilestone(milestone) {
  busy.value = true
  try {
    const response = await client.post(`/milestones/${milestone.id}/finalize`)
    const result = response.data.data
    ElMessage.success(
      `验收结论：${result.status}${
        result.unlocked_tasks?.length
          ? `，已解锁 ${result.unlocked_tasks.join('、')}`
          : ''
      }`
    )
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '汇总失败')
  } finally {
    busy.value = false
  }
}

async function rectifyMilestone(milestone) {
  busy.value = true
  try {
    await client.post(`/milestones/${milestone.id}/rectify`)
    ElMessage.success('已进入整改，可重新提交')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '操作失败')
  } finally {
    busy.value = false
  }
}

async function clientConfirmMilestone(milestone) {
  busy.value = true
  try {
    await client.post(`/milestones/${milestone.id}/client-confirm`)
    ElMessage.success('客户确认已记录')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '确认失败')
  } finally {
    busy.value = false
  }
}

async function generateQueryLetter() {
  if (!props.projectId || busy.value) return
  busy.value = true
  try {
    await client.post(`/projects/${props.projectId}/query-letters`, {
      milestone_id: reviewMilestoneId.value || undefined
    })
    ElMessage.success('质询函已生成')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '生成失败')
  } finally {
    busy.value = false
  }
}

async function approveLetter(letter) {
  busy.value = true
  try {
    await client.post(`/query-letters/${letter.id}/approve`)
    ElMessage.success('已批准')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '批准失败')
  } finally {
    busy.value = false
  }
}

async function createQueryLink(letter) {
  busy.value = true
  try {
    const response = await client.post('/access-tokens', {
      project_id: props.projectId,
      role_type: 'provider',
      subject_id: letter.provider_id
    })
    queryLinks.value = {
      ...queryLinks.value,
      [letter.id]: `${window.location.origin}/query-link/${response.data.data.token}`
    }
    ElMessage.success('服务商回复链接已生成')
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '链接生成失败')
  } finally {
    busy.value = false
  }
}

async function copyQueryLink(letter) {
  const link = queryLinks.value[letter.id]
  if (!link) return
  try {
    await navigator.clipboard.writeText(link)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选择：' + link)
  }
}

async function sendLetter(letter) {
  busy.value = true
  try {
    await client.post(`/query-letters/${letter.id}/send`)
    ElMessage.success('质询函已发送')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '发送失败')
  } finally {
    busy.value = false
  }
}

async function closeLetter(letter) {
  busy.value = true
  try {
    await client.post(`/query-letters/${letter.id}/close`)
    ElMessage.success('质询函已关闭')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '关闭失败')
  } finally {
    busy.value = false
  }
}

async function fetchReminder(milestone) {
  try {
    const response = await client.post(
      `/milestones/${milestone.id}/reminder-draft`
    )
    reminderDrafts.value = {
      ...reminderDrafts.value,
      [milestone.id]: response.data.data
    }
    ElMessage.success('催办内容已生成')
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '生成失败')
  }
}

async function copyReminder(milestone) {
  const draft = reminderDrafts.value[milestone.id]
  if (!draft) return
  const text = `${draft.provider_en}\n\n${draft.client_zh}`
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}

async function generateRetrospective() {
  if (!props.projectId || busy.value) return
  busy.value = true
  try {
    await client.post(`/projects/${props.projectId}/retrospective`)
    ElMessage.success('复盘报告已生成')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '生成失败')
  } finally {
    busy.value = false
  }
}

async function createArchive() {
  if (!props.projectId || busy.value) return
  busy.value = true
  try {
    await client.post(`/projects/${props.projectId}/archives`)
    ElMessage.success('归档包已生成')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '归档失败')
  } finally {
    busy.value = false
  }
}

async function downloadArchive(archive) {
  try {
    const response = await client.get(archive.download_url, {
      responseType: 'blob'
    })
    const url = URL.createObjectURL(response.data)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `archive-v${archive.version}.zip`
    anchor.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '下载失败')
  }
}

async function resetDemo() {
  try {
    await ElMessageBox.confirm(
      '将清空演示项目并重建初始数据，是否继续？',
      '一键重置',
      { type: 'warning' }
    )
  } catch {
    return
  }
  busy.value = true
  try {
    await client.post('/admin/demo/reset')
    ElMessage.success('演示数据已重置')
    emit('demo-reset')
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '重置失败（需要管理员账号）')
  } finally {
    busy.value = false
  }
}

async function clientConfirmRequirement() {
  busy.value = true
  try {
    await client.post(
      `/projects/${props.projectId}/client-portal/requirement/confirm`
    )
    ElMessage.success('需求已确认')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '确认失败')
  } finally {
    busy.value = false
  }
}

async function clientConfirmProposal() {
  busy.value = true
  try {
    await client.post(
      `/projects/${props.projectId}/client-portal/proposal/confirm`
    )
    ElMessage.success('建议书已确认')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '确认失败')
  } finally {
    busy.value = false
  }
}

async function clientReviseProposal() {
  try {
    const { value } = await ElMessageBox.prompt(
      '请填写修改意见',
      '提交修改意见',
      { inputType: 'textarea', inputValidator: (v) => Boolean(v?.trim()) || '请填写意见' }
    )
    await client.post(
      `/projects/${props.projectId}/client-portal/proposal/revision`,
      { note: value }
    )
    ElMessage.success('修改意见已提交')
    await load()
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error(err.response?.data?.message || '提交失败')
    }
  }
}

async function clientConfirmQuote() {
  busy.value = true
  try {
    await client.post(
      `/projects/${props.projectId}/client-portal/quote/confirm`
    )
    ElMessage.success('总报价已确认')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '确认失败')
  } finally {
    busy.value = false
  }
}

async function clientConfirmContract() {
  busy.value = true
  try {
    await client.post(
      `/projects/${props.projectId}/client-portal/contract/confirm`
    )
    ElMessage.success('合同已确认')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '确认失败')
  } finally {
    busy.value = false
  }
}

async function clientConfirmPortalMilestone(milestone) {
  busy.value = true
  try {
    await client.post(
      `/projects/${props.projectId}/client-portal/milestones/${milestone.id}/confirm`
    )
    ElMessage.success('节点已确认')
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '确认失败')
  } finally {
    busy.value = false
  }
}

async function createClientLink() {
  if (!props.projectId || busy.value) return
  busy.value = true
  try {
    const response = await client.post('/access-tokens', {
      project_id: props.projectId,
      role_type: 'client',
      subject_id: 'client'
    })
    clientLink.value = `${window.location.origin}/link/${response.data.data.token}`
    ElMessage.success('客户确认链接已生成')
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '链接生成失败')
  } finally {
    busy.value = false
  }
}

async function copyLink() {
  try {
    await navigator.clipboard.writeText(clientLink.value)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}

function printPanel() {
  window.print()
}

watch(activeType, load)
watch(
  () => [props.projectId, props.refreshToken],
  () => {
    raw.value = null
    graphData.value = null
    questions.value = []
    clientLink.value = ''
    proposalVersions.value = []
    selectedVersionId.value = ''
    comparison.value = null
    proposalLink.value = ''
    catalog.value = null
    selectedCodes.value = []
    overrideReason.value = ''
    selectionLink.value = ''
    candidateGroups.value = []
    clientQuotes.value = []
    clientQuoteLink.value = ''
    providerContractLinks.value = {}
    contractClientLink.value = ''
    board.value = null
    reviewMilestones.value = []
    reviewMilestoneId.value = ''
    reviewText.value = ''
    reviewFindings.value = []
    selectedReviewFinding.value = null
    queryLetters.value = []
    queryLinks.value = {}
    expertLinks.value = {}
    reminderDrafts.value = {}
    archiveData.value = null
    projectInfo.value = null
    clientPortal.value = null
    quoteForm.value = { providerYuan: '', lawyerYuan: '0', feeRate: '17.5' }
    load()
  },
  { immediate: true }
)
</script>

<style scoped>
.artifact {
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: 100%;
  border-left: 1px solid var(--border);
  background: #fff;
}

.artifact.full {
  position: fixed;
  inset: 16px;
  z-index: 60;
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.18);
}

.panel-header {
  padding: 8px 12px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  border-bottom: 1px solid var(--border);
}

.phase-nav {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.phase-chip {
  height: 30px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fff;
  color: var(--text-2);
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  white-space: nowrap;
  cursor: pointer;
}

.phase-chip:hover:not(:disabled) {
  border-color: #c9ced6;
  color: var(--text);
}

.phase-chip.active {
  border-color: var(--accent);
  background: var(--accent);
  color: #fff;
  font-weight: 650;
}

.phase-chip.locked {
  color: #c2c7d0;
  background: #fafbfc;
  cursor: not-allowed;
}

.phase-no {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: #f3f4f6;
  color: var(--text-3);
  font-size: 10px;
}

.phase-chip.active .phase-no {
  background: rgba(255, 255, 255, 0.24);
  color: #fff;
}

.sub-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  padding: 0 12px 8px;
  border-bottom: 1px solid var(--border);
}

.tab {
  height: 30px;
  padding: 0 10px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--text-2);
  font-size: 12px;
  white-space: nowrap;
  cursor: pointer;
}

.tab:hover {
  background: #f3f4f6;
}

.tab.active {
  background: #eef1ff;
  color: var(--accent);
  font-weight: 650;
}

.tab.disabled {
  color: #c2c7d0;
  cursor: not-allowed;
}

.tab.disabled:hover {
  background: transparent;
}

.expand {
  flex: none;
}

.expand {
  height: 28px;
  padding: 0 8px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: #fff;
  color: var(--text-2);
  font-size: 12px;
  cursor: pointer;
}

.panel-body {
  flex: 1;
  overflow: auto;
  padding: 14px;
}

.stack {
  display: grid;
  gap: 10px;
}

.state {
  padding: 40px 12px;
  text-align: center;
  font-size: 12px;
  color: var(--text-3);
}

.state.error {
  color: #dc2626;
}

.fact,
.quote,
.milestone,
.finding,
.chapter {
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 9px;
}

.fact-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.fact-key {
  font-size: 13px;
  font-weight: 650;
}

.fact-value {
  margin: 6px 0 8px;
  font-size: 13px;
}

.pill {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 7px;
  border-radius: 999px;
  background: #f3f4f6;
  color: var(--text-2);
  font-size: 11px;
}

.pill.confirmed {
  background: #e8f7ee;
  color: #15803d;
}

.pill.assumption {
  background: #fff7e6;
  color: #b45309;
}

.pill.unknown {
  background: #f3f4f6;
  color: var(--text-2);
}

.pill.severity {
  background: #fef2f2;
  color: #b91c1c;
}

.pill.legal {
  background: #eef1ff;
  color: var(--accent);
}

.pill.verified_error {
  background: #fef2f2;
  color: #b91c1c;
}

.pill.needs_verification {
  background: #fff7e6;
  color: #b45309;
}

.pill.professional_judgment {
  background: #eef1ff;
  color: var(--accent);
}

.citation {
  height: 25px;
  max-width: 100%;
  padding: 0 8px;
  border: 1px solid #dbe1ff;
  border-radius: 6px;
  background: #f6f8ff;
  color: var(--accent);
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.citation:hover {
  background: #eef1ff;
}

.task-group h4 {
  margin: 4px 0 6px;
  font-size: 12px;
  color: var(--text-2);
  display: flex;
  justify-content: space-between;
}

.task {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 0;
  border-bottom: 1px dashed #eef0f3;
  font-size: 12px;
}

.task:last-child {
  border-bottom: 0;
}

.task.locked {
  opacity: 0.55;
}

.code {
  color: var(--text-3);
  font-size: 11px;
}

.task-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.star {
  color: #b45309;
  font-size: 10px;
}

.lock {
  color: var(--text-3);
  font-size: 10px;
}

.proposal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.proposal-head h3 {
  margin: 0;
  font-size: 14px;
}

.chapter h4 {
  margin: 0 0 6px;
  font-size: 12px;
}

.chapter p {
  margin: 0;
  font-size: 12px;
  line-height: 1.7;
  color: var(--text-2);
}

.budget {
  display: grid;
  gap: 4px;
  padding: 12px;
  border-radius: 9px;
  background: #f7f8fa;
  font-size: 12px;
}

.budget small {
  color: var(--text-3);
}

.budget .warn {
  color: #b45309;
}

.amount {
  font-size: 13px;
  font-weight: 650;
}

.muted {
  margin: 6px 0 0;
  font-size: 11px;
  color: var(--text-3);
}

.items {
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
  font-size: 12px;
}

.items li {
  display: flex;
  justify-content: space-between;
  padding: 3px 0;
  color: var(--text-2);
}

.total {
  display: grid;
  gap: 6px;
  padding: 12px;
  border-radius: 9px;
  background: #f7f8fa;
  font-size: 12px;
}

.total div {
  display: flex;
  justify-content: space-between;
}

.total .grand {
  padding-top: 6px;
  border-top: 1px solid var(--border);
  font-weight: 650;
  color: var(--text);
}

.quote-text {
  margin: 8px 0 6px;
  font-size: 12px;
  line-height: 1.7;
}

.question {
  margin: 8px 0 0;
  padding: 8px;
  border-radius: 7px;
  background: #f7f8fa;
  font-size: 12px;
  line-height: 1.7;
}

.badges {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.toolbar {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.toolbar button,
.client-link button {
  height: 28px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: #fff;
  color: var(--text-2);
  font-size: 11px;
  cursor: pointer;
}

.toolbar button:hover:not(:disabled) {
  border-color: #c9ced6;
  color: var(--text);
}

.toolbar button.selected {
  border-color: #c9d1ff;
  background: #eef1ff;
  color: var(--accent);
  font-weight: 650;
}

.toolbar button:disabled {
  opacity: 0.5;
  cursor: default;
}

.question-list {
  padding: 10px;
  border-radius: 9px;
  background: #f7f8fa;
}

.question-list h4 {
  margin: 0 0 8px;
  font-size: 12px;
}

.question-item {
  display: grid;
  gap: 2px;
  padding: 7px 0;
  border-top: 1px dashed var(--border);
  font-size: 12px;
  line-height: 1.6;
}

.question-item:first-of-type {
  border-top: 0;
}

.question-item small {
  color: var(--text-3);
  font-size: 10px;
}

.diff {
  padding: 8px 10px;
  border-radius: 8px;
  background: #fff7e6;
  color: #92400e;
  font-size: 11px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.graph-summary {
  font-size: 11px;
  line-height: 1.7;
  color: var(--text-3);
}

.req-scope {
  margin: 8px 0;
  padding: 9px;
  border-radius: 8px;
  background: #f7f8fa;
  font-size: 12px;
  line-height: 1.7;
}

.req-heading {
  margin: 12px 0 6px;
  font-size: 12px;
  color: var(--text-2);
}

.req-fact {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px dashed #eef0f3;
  font-size: 12px;
}

.req-key {
  width: 90px;
  flex: none;
  color: var(--text-2);
}

.req-value {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.disclaimer {
  margin: 10px 0 0;
  padding: 9px;
  border-radius: 8px;
  background: #fff7e6;
  color: #92400e;
  font-size: 11px;
  line-height: 1.6;
}

.client-link {
  display: flex;
  gap: 6px;
  margin-top: 10px;
}

.version-select {
  height: 28px;
  max-width: 150px;
  padding: 0 6px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: #fff;
  color: var(--text-2);
  font-size: 11px;
}

.chapter-nav {
  display: flex;
  gap: 4px;
  overflow-x: auto;
}

.chapter-nav button {
  width: 24px;
  height: 24px;
  flex: none;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: #fff;
  color: var(--text-2);
  font-size: 11px;
  cursor: pointer;
}

.chapter-nav button:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.references {
  display: grid;
  gap: 6px;
  padding-top: 6px;
}

.references h4 {
  margin: 0;
  font-size: 12px;
  color: var(--text-2);
}

.references .citation {
  text-align: left;
}

.references .citation.stale {
  border-color: #f5d7a1;
  background: #fff7e6;
  color: #b45309;
}

.service-item {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 7px 6px;
  border-radius: 7px;
  font-size: 12px;
  cursor: pointer;
}

.service-item:hover {
  background: #f7f8fa;
}

.service-item.checked {
  background: #eef1ff;
}

.service-item input {
  accent-color: var(--accent);
}

.service-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.service-fee {
  color: var(--text-3);
  font-size: 10px;
  white-space: nowrap;
}

.reason-input {
  height: 32px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 12px;
  outline: none;
}

.reason-input:focus {
  border-color: var(--accent);
}

.candidate {
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 9px;
}

.candidate.rejected {
  opacity: 0.55;
}

.candidate-reason {
  margin: 6px 0;
  font-size: 12px;
  line-height: 1.6;
}

.small-btn {
  height: 26px;
  padding: 0 9px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: #fff;
  color: var(--text-2);
  font-size: 11px;
  cursor: pointer;
}

.small-btn:hover:not(:disabled) {
  border-color: #c9ced6;
  color: var(--text);
}

.small-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.small-btn.primary {
  border-color: var(--accent);
  background: var(--accent);
  color: #fff;
  font-weight: 650;
}

.small-btn.primary:hover:not(:disabled) {
  background: #3f5cf0;
  color: #fff;
}

.confirm-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid #c9d1ff;
  border-radius: 10px;
  background: #f5f7ff;
}

.confirm-banner strong {
  font-size: 13px;
}

.confirm-banner p {
  margin: 4px 0 0;
  font-size: 11px;
  color: var(--text-3);
  line-height: 1.5;
}

.section-title {
  margin: 12px 0 4px;
  font-size: 12px;
  color: var(--text-2);
}

.hash {
  word-break: break-all;
  font-size: 10px;
}

.sla {
  display: grid;
  gap: 5px;
  padding: 10px;
  border-radius: 9px;
  background: #f7f8fa;
  font-size: 11px;
}

.sla div {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.sla span:first-child {
  flex: none;
  color: var(--text-3);
}

.sla span:last-child {
  text-align: right;
}

.board-summary {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  padding: 9px;
  border-radius: 8px;
  background: #f7f8fa;
  font-size: 11px;
  color: var(--text-2);
}

.overdue {
  margin: 6px 0 0;
  color: #b91c1c;
  font-size: 11px;
}

.review-controls {
  display: grid;
  gap: 8px;
}

.review-controls select {
  height: 30px;
  padding: 0 8px;
  border: 1px solid var(--border);
  border-radius: 7px;
  font-size: 12px;
  background: #fff;
}

.review-controls textarea {
  padding: 9px;
  border: 1px solid var(--border);
  border-radius: 8px;
  resize: vertical;
  font-size: 12px;
  line-height: 1.7;
  outline: none;
}

.review-controls textarea:focus {
  border-color: var(--accent);
}

.review-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
  min-height: 280px;
}

.review-pane {
  min-width: 0;
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: auto;
}

.review-pane h4 {
  margin: 0 0 6px;
  font-size: 11px;
  color: var(--text-2);
}

.review-text {
  margin: 0;
  font-family: inherit;
  font-size: 11px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}

.review-text .hit {
  background: #fff1a8;
}

.finding-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px;
  border: 0;
  border-bottom: 1px solid #f1f2f4;
  background: transparent;
  font-size: 11px;
  text-align: left;
  cursor: pointer;
}

.finding-item.active {
  background: #eef1ff;
}

.letter-content {
  max-height: 120px;
  overflow: auto;
  margin: 6px 0 0;
  padding: 8px;
  border-radius: 7px;
  background: #fafbfc;
  font-family: inherit;
  font-size: 11px;
  line-height: 1.6;
  white-space: pre-wrap;
}

@media (max-width: 900px) {
  .review-grid {
    grid-template-columns: 1fr;
  }
}

.metrics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.rate-card {
  display: grid;
  gap: 3px;
  padding: 9px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 10px;
  color: var(--text-3);
}

.rate-card strong {
  font-size: 15px;
  color: var(--text);
}

.rate-card.muted-card strong {
  font-size: 12px;
  color: var(--text-3);
}

.retro {
  padding: 10px;
  border-radius: 9px;
  background: #f7f8fa;
  font-size: 11px;
  line-height: 1.7;
}

.retro p {
  margin: 0 0 4px;
}

.rfp,
.quote-row,
.client-quote {
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 9px;
}

.quote-row.lowest {
  border-color: #b7e4c7;
  background: #f4fcf7;
}

.actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.quote-form {
  display: grid;
  gap: 7px;
  padding: 10px;
  border-radius: 9px;
  background: #f7f8fa;
}

.quote-form label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
  color: var(--text-2);
}

.quote-form input {
  width: 110px;
  height: 27px;
  padding: 0 8px;
  border: 1px solid var(--border);
  border-radius: 7px;
  font-size: 12px;
  text-align: right;
  outline: none;
}

.quote-form input:focus {
  border-color: var(--accent);
}

.client-link input {
  flex: 1;
  min-width: 0;
  height: 28px;
  padding: 0 8px;
  border: 1px solid var(--border);
  border-radius: 7px;
  font-size: 11px;
  color: var(--text-2);
}

@media print {
  .artifact {
    position: static;
    height: auto;
    border: 0;
  }

  .artifact.full {
    position: static;
    inset: auto;
    border: 0;
    box-shadow: none;
  }

  .panel-header {
    display: none;
  }

  .panel-body {
    overflow: visible;
    padding: 0;
  }
}
</style>
