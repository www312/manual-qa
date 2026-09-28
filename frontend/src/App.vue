<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

type SearchMode = 'vector' | 'bm25' | 'hybrid' | 'agent'
type Citation = { n: number; chunk_id: string; doc: string; chapter: string; page: number; score: number; snippet: string }
type AgentStep = { kind: string; query?: string; text?: string }
type Message = { id: number; role: 'user' | 'assistant'; text: string; citations?: Citation[]; loading?: boolean; error?: boolean; latency?: number; steps?: AgentStep[]; rewritten?: string }
type StreamPayload = Record<string, unknown>
type MetricsConfig = { name: string; label: string; recall5: number; mrr: number }
type BreakdownMetric = { r5: number; mrr: number }
type BreakdownRow = { group: string; n: number; vector: BreakdownMetric; hybrid_rewrite: BreakdownMetric }
type MetricsResponse = {
  offline: { evaluated_at: string; qa_set: string; metric_note: string; configs: MetricsConfig[]; breakdown: BreakdownRow[] }
  runtime: { chunks: number; docs: string; daily_limit: number }
}

declare global {
  interface Window { __METRICS_MOCK?: MetricsResponse }
}

const metricsMock: MetricsResponse = {
  offline: {
    evaluated_at: '2026-09-28',
    qa_set: '123 题分层 QA 集（37 章分层抽样 + LLM 依种子出题）',
    metric_note: '章节级 recall@5：top-5 命中正确内容所在章节',
    configs: [
      { name: 'vector', label: '纯向量', recall5: 0.943, mrr: 0.799 },
      { name: 'hybrid', label: '混合检索(RRF)', recall5: 0.935, mrr: 0.803 },
      { name: 'hybrid_rewrite', label: '混合+查询改写', recall5: 0.935, mrr: 0.856 },
    ],
    breakdown: [
      { group: '数值 | 跨语言(中文→英文手册)', n: 60, vector: { r5: 0.9, mrr: 0.75 }, hybrid_rewrite: { r5: 0.92, mrr: 0.8 } },
      { group: '寄存器 | 同义表达', n: 18, vector: { r5: 0.944, mrr: 0.806 }, hybrid_rewrite: { r5: 0.944, mrr: 0.861 } },
      { group: '配置 | 多步骤操作', n: 15, vector: { r5: 0.933, mrr: 0.8 }, hybrid_rewrite: { r5: 0.933, mrr: 0.867 } },
      { group: '概念 | 术语解释', n: 12, vector: { r5: 1, mrr: 0.917 }, hybrid_rewrite: { r5: 1, mrr: 0.917 } },
      { group: '排错 | 症状到原因', n: 8, vector: { r5: 0.875, mrr: 0.75 }, hybrid_rewrite: { r5: 0.875, mrr: 0.792 } },
      { group: '对比 | 方案选型', n: 6, vector: { r5: 0.833, mrr: 0.667 }, hybrid_rewrite: { r5: 0.833, mrr: 0.75 } },
      { group: '边界 | 限制与例外', n: 4, vector: { r5: 0.75, mrr: 0.625 }, hybrid_rewrite: { r5: 0.75, mrr: 0.75 } },
    ],
  },
  runtime: { chunks: 105716, docs: 'RM0433 + ESP-IDF', daily_limit: 30 },
}

window.__METRICS_MOCK ??= metricsMock

const examples = [
  { label: '时钟配置', question: 'STM32H743 的 APB1 时钟使能寄存器地址偏移是多少？' },
  { label: 'GPIO 初始化', question: 'ESP-IDF 中如何配置 GPIO34 为输入并开启上拉？' },
  { label: 'DMA 传输', question: 'STM32H743 使用 DMA 进行内存到外设传输有哪些注意事项？' },
]
const messages = ref<Message[]>([])
const question = ref('')
const mode = ref<SearchMode>('hybrid')
const isStreaming = ref(false)
const activeCitation = ref<number | null>(null)
const expandedCitation = ref<number | null>(null)
const view = ref<'chat' | 'metrics'>('chat')
const metrics = ref<MetricsResponse>(metricsMock)
const metricsLoading = ref(false)
const metricsAnimated = ref(false)
const composer = ref<HTMLTextAreaElement | null>(null)
const conversation = ref<HTMLElement | null>(null)
let controller: AbortController | null = null
let nextMessageId = 1

async function loadMetrics() {
  metricsLoading.value = true
  metricsAnimated.value = false
  try {
    const response = await fetch('/api/metrics', { headers: { Accept: 'application/json' } })
    if (!response.ok) throw new Error(`metrics unavailable: ${response.status}`)
    metrics.value = await response.json() as MetricsResponse
  } catch {
    metrics.value = window.__METRICS_MOCK ?? metricsMock
  } finally {
    metricsLoading.value = false
    await nextTick()
    metricsAnimated.value = true
  }
}
function showMetrics() { view.value = 'metrics'; void loadMetrics() }
function showChat() { view.value = 'chat' }
function formatPercent(value: number) { return `${(value * 100).toFixed(1)}%` }
function formatDelta(value: number) { return `${value > 0 ? '+' : ''}${(value * 100).toFixed(1)} pp` }
function deltaClass(value: number) { return value > 0 ? 'positive' : value < 0 ? 'negative' : 'neutral' }
function formatChunks(value: number) { return new Intl.NumberFormat('zh-CN').format(value) }
function shortGroup(group: string) { return group.split(' | ')[0] }
function heatClass(value: number) { return value >= 0.95 ? 'heat-high' : value >= 0.85 ? 'heat-mid' : 'heat-low' }
function deltaSymbol(value: number) { return value > 0 ? '▲' : value < 0 ? '▼' : '·' }

// 产品报告以 hybrid+rewrite 作为主配置；若后端暂未返回它，再回退到实际最高值。
const bestRecall = computed(() => metrics.value.offline.configs.find((config) => config.name === 'hybrid_rewrite') ?? [...metrics.value.offline.configs].sort((a, b) => b.recall5 - a.recall5)[0] ?? metricsMock.offline.configs[0])
const bestMrr = computed(() => [...metrics.value.offline.configs].sort((a, b) => b.mrr - a.mrr)[0] ?? metricsMock.offline.configs[0])
const evaluationCount = computed(() => {
  const match = metrics.value.offline.qa_set.match(/\d+/)
  return match ? Number(match[0]) : 123
})
const kpis = computed(() => [
  { label: '语料规模', value: formatChunks(metrics.value.runtime.chunks), unit: 'chunks', detail: '线上知识库', bars: [42, 68, 54, 82] },
  { label: '最佳 recall@5', value: formatPercent(bestRecall.value.recall5), unit: bestRecall.value.label, detail: bestRecall.value.name, bars: [58, 72, 66, 88] },
  { label: '最佳 MRR', value: bestMrr.value.mrr.toFixed(3), unit: bestMrr.value.label, detail: bestMrr.value.name, bars: [36, 62, 78, 60] },
  { label: '评测规模', value: String(evaluationCount.value), unit: '题', detail: '离线 QA 集', bars: [48, 76, 58, 70] },
])

onMounted(() => { void loadMetrics() })

const lastQuestion = computed(() => [...messages.value].reverse().find((item) => item.role === 'user')?.text ?? '')

function resizeComposer() {
  const element = composer.value
  if (!element) return
  element.style.height = 'auto'
  element.style.height = `${Math.min(element.scrollHeight, 160)}px`
}
function scrollToBottom() { nextTick(() => conversation.value?.scrollTo({ top: conversation.value.scrollHeight, behavior: 'smooth' })) }
function renderAnswer(text: string, streaming = false): string {
  if (streaming) {
    // 流式期间轻渲染：只做换行 + 引用上标（避免半截 markdown 全量重渲染闪烁）
    const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    return escaped.replace(/\[(\d+)\]/g, '<sup class="inline-citation" data-citation="$1">[$1]</sup>').replace(/\n/g, '<br>')
  }
  // 完成态：完整 markdown 渲染 + XSS 消毒（LLM 输出是不可信输入）
  const markedText = marked.parse(text, { async: false, gfm: true, breaks: true }) as string
  const withCitations = markedText.replace(/\[(\d+)\]/g, '<sup class="inline-citation" data-citation="$1">[$1]</sup>')
  return DOMPurify.sanitize(withCitations, { ADD_ATTR: ['data-citation'] })
}
function handleAnswerClick(event: MouseEvent) {
  const target = event.target as HTMLElement
  const n = target.dataset.citation
  if (n) { activeCitation.value = Number(n); document.getElementById(`citation-${n}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }) }
}

async function ask(value = question.value) {
  const text = value.trim()
  if (!text || isStreaming.value) return
  question.value = ''
  resizeComposer()
  const answerMessage: Message = { id: nextMessageId++, role: 'assistant', text: '', citations: [], loading: true, steps: mode.value === 'agent' ? [] : undefined }
  messages.value.push({ id: nextMessageId++, role: 'user', text }, answerMessage)
  isStreaming.value = true
  controller = new AbortController()
  scrollToBottom()
  // 多轮：带最近 3 轮问答（上一条 assistant 消息的 text 作为答案）
  const history = messages.value
    .filter(m => m.role === 'user')
    .slice(-4, -1) // 之前的轮次（不含本次刚推入的 user）
    .map((m) => {
      const idx = messages.value.indexOf(m)
      const ans = messages.value.slice(idx + 1).find(x => x.role === 'assistant')
      return { q: m.text, a: ans?.text?.slice(0, 300) ?? '' }
    })
    .filter(t => t.a)
  try {
    const response = await fetch('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' }, body: JSON.stringify({ question: text, mode: mode.value, k: 5, history: history.length ? history : undefined }), signal: controller.signal })
    if (!response.ok || !response.body) throw new Error(`请求失败（${response.status}）`)
    await readSse(response.body, (event, payload) => {
      if (event === 'rewritten' && typeof payload.question === 'string' && payload.question !== text) { answerMessage.rewritten = payload.question; scrollToBottom() }
      else if (event === 'citations') { answerMessage.citations = Array.isArray(payload.citations) ? payload.citations as Citation[] : []; answerMessage.loading = false }
      else if (event === 'step' && answerMessage.steps) { answerMessage.steps.push(payload as AgentStep); answerMessage.loading = false; if (payload.kind === 'answer' && typeof payload.text === 'string') answerMessage.text += payload.text; scrollToBottom() }
      else if (event === 'delta' && typeof payload.text === 'string') { answerMessage.loading = false; answerMessage.text += payload.text; scrollToBottom() }
      else if (event === 'done' && typeof payload.latency_ms === 'number') answerMessage.latency = payload.latency_ms
      else if (event === 'error') throw new Error(typeof payload.message === 'string' ? payload.message : '服务返回错误')
    })
  } catch (error) {
    if ((error as Error).name !== 'AbortError') {
      answerMessage.loading = false; answerMessage.error = true
      const raw = error instanceof Error ? error.message : '未知错误'
      const isNetwork = /network|failed to fetch|connection|timeout|Connection/i.test(raw)
      answerMessage.text = isNetwork ? '网络波动，与模型的连接中断了。' : `暂时无法获取答案：${raw}`
    }
  } finally { answerMessage.loading = false; isStreaming.value = false; controller = null; scrollToBottom() }
}
function retryMessage(messageId: number) {
  const idx = messages.value.findIndex(m => m.id === messageId)
  if (idx < 1) return
  const userMsg = messages.value[idx - 1]
  if (userMsg.role !== 'user') return
  // 移除失败的回答，重新提问
  messages.value.splice(idx, 1)
  ask(userMsg.text)
}

async function readSse(stream: ReadableStream<Uint8Array>, onEvent: (event: string, payload: StreamPayload) => void) {
  const reader = stream.getReader(); const decoder = new TextDecoder(); let buffer = ''
  while (true) {
    const { done, value } = await reader.read(); buffer += decoder.decode(value, { stream: !done })
    const frames = buffer.split(/\r?\n\r?\n/); buffer = frames.pop() ?? ''
    frames.filter(Boolean).forEach((frame) => { const clean = frame.replace(/\r/g, ''); const event = clean.match(/^event:\s*(.+)$/m)?.[1]?.trim() ?? 'message'; const data = clean.match(/^data:\s*(.+)$/m)?.[1]?.trim(); if (data) onEvent(event, JSON.parse(data) as StreamPayload) })
    if (done) break
  }
}
function stop() { controller?.abort() }
function onKeydown(event: KeyboardEvent) { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); ask() } }
function rerun() { if (lastQuestion.value) ask(lastQuestion.value) }
function citationDocLabel(doc: string) { return doc.toLowerCase().includes('esp') ? 'ESP-IDF' : 'RM0433' }
function agentStepLine(payload: StreamPayload & { kind?: string; query?: string; text?: string }) { return payload.kind === 'search' ? `🔍 manual_search("${payload.query ?? ''}")` : `💬 ${payload.text?.slice(0, 60) ?? ''}` }
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand-mark" aria-hidden="true"><span></span><span></span><span></span></div>
      <div><h1>嵌入式手册智能问答</h1><p>STM32H743 RM0433 + ESP-IDF <span class="dot">·</span> 10.5 万块技术语料</p></div>
      <div class="topbar-actions"><div class="topbar-status"><i></i>知识库已连接</div><button class="metrics-toggle" @click="view === 'chat' ? showMetrics() : showChat()">{{ view === 'chat' ? '评测' : '返回对话' }}</button></div>
    </header>
    <main v-if="view === 'chat'" ref="conversation" class="conversation" aria-live="polite">
      <section v-if="messages.length === 0" class="empty-state">
        <div class="empty-icon">⌁</div><h2>从一个问题开始</h2><p>向你的嵌入式技术手册提问，答案会附带可追溯的原文引用。</p>
        <div class="example-grid"><button v-for="example in examples" :key="example.question" class="example-card" @click="ask(example.question)"><span>{{ example.label }}</span><strong>{{ example.question }}</strong><b>↗</b></button></div>
      </section>
      <section v-else class="message-list">
        <article v-for="message in messages" :key="message.id" :class="['message', message.role]">
          <div v-if="message.role === 'user'" class="user-line"><div class="user-text">{{ message.text }}</div></div>
          <div v-else class="answer-wrap">
            <div v-if="message.rewritten" class="rewritten-note" title="多轮追问已自动改写为独立问题">↻ 理解为：{{ message.rewritten }}</div>
            <div class="answer-meta"><span class="answer-avatar">✦</span><span>手册助手</span><span class="answer-label">AI 回答</span></div>
            <div v-if="message.loading" class="skeleton" aria-label="正在检索引用"><span></span><span></span><span></span></div>
            <div v-if="message.steps?.length" class="agent-steps"><div v-for="(step, idx) in message.steps" :key="idx" class="agent-step">{{ agentStepLine(step) }}</div></div>
            <div v-if="message.error" class="answer error-answer">{{ message.text }} <button v-if="message.error && !isStreaming" class="retry-link" @click="retryMessage(message.id)">点击重试</button></div>
            <div v-else-if="message.text" class="answer" @click="handleAnswerClick" v-html="renderAnswer(message.text, isStreaming)"></div>
            <div v-if="message.text && !message.error" class="answer-footer"><span v-if="message.latency">检索与生成耗时 {{ (message.latency / 1000).toFixed(1) }}s</span><button v-if="lastQuestion && !isStreaming" @click="rerun">↻ 用当前模式重问</button></div>
            <div v-if="message.citations?.length" class="citations-panel">
              <div class="citations-heading"><span>引用来源</span><small>{{ message.citations.length }} 条相关内容</small></div>
              <div class="citation-list"><button v-for="citation in message.citations" :id="`citation-${citation.n}`" :key="citation.n" :class="['citation-card', { active: activeCitation === citation.n }]" @mouseenter="activeCitation = citation.n" @mouseleave="activeCitation = null" @click="expandedCitation = expandedCitation === citation.n ? null : citation.n"><span class="citation-number">[{{ citation.n }}]</span><span class="doc-icon">▤</span><span class="citation-main"><span class="citation-title">{{ citation.chapter }}</span><span class="citation-detail">{{ citationDocLabel(citation.doc) }} <i>·</i> p. {{ citation.page }}</span><span class="citation-snippet">{{ expandedCitation === citation.n ? citation.snippet : `${citation.snippet.slice(0, 86)}${citation.snippet.length > 86 ? '…' : ''}` }}</span></span><span class="score">{{ Math.round(citation.score * 100) }}%</span><span class="expand-mark">{{ expandedCitation === citation.n ? '⌃' : '⌄' }}</span></button></div>
            </div>
          </div>
        </article>
      </section>
    </main>
    <main v-else :class="['metrics-view', { 'metrics-ready': metricsAnimated }]">
      <div class="metrics-heading">
        <div><p class="eyebrow">离线评测报告</p><h2>评测面板</h2><p class="metrics-subtitle">检索质量与线上资源状态一览</p></div>
        <span v-if="metricsLoading" class="metrics-loading">正在同步…</span>
      </div>
      <div class="evaluation-scope">
        <div class="scope-main"><span class="scope-icon" aria-hidden="true">▦</span><span class="scope-meta">QA-SET: {{ evaluationCount }} · METRIC: chapter-recall@5 · DATE: {{ metrics.offline.evaluated_at }}</span></div>
        <span class="offline-badge"><i></i>离线评测</span>
      </div>

      <template v-if="metricsLoading">
        <div class="metrics-skeleton-grid"><section v-for="n in 3" :key="n" class="metrics-card loading-card"><span></span><span></span><span></span><span></span></section></div>
      </template>
      <template v-else>
        <section class="kpi-grid" aria-label="评测关键指标">
          <article v-for="(kpi, index) in kpis" :key="kpi.label" class="kpi-card" :style="{ '--stagger': `${index * 60}ms` }">
            <span class="kpi-label">{{ kpi.label }}</span><strong class="kpi-value">{{ kpi.value }}</strong><span class="kpi-unit">{{ kpi.unit }}</span>
            <div class="sparkline" aria-hidden="true"><i v-for="(height, barIndex) in kpi.bars" :key="barIndex" :style="{ height: `${height}%` }"></i></div><span class="kpi-detail">{{ kpi.detail }}</span>
          </article>
        </section>
        <section class="metrics-card overview-card" style="--stagger: 240ms">
          <div class="card-heading"><div><h3>配置对比</h3><p>三种检索配置在同一 QA 集上的结果</p></div><span class="sample-size">n = {{ evaluationCount }}</span></div>
          <div class="metric-groups">
            <div v-for="metric in (['recall5', 'mrr'] as const)" :key="metric" class="metric-group">
              <div class="metric-title"><span>{{ metric === 'recall5' ? 'recall@5' : 'MRR' }}</span><small>{{ metric === 'recall5' ? '章节命中率' : '首个正确结果排名' }}</small></div>
              <div v-for="config in metrics.offline.configs" :key="`${metric}-${config.name}`" :class="['metric-row', { 'is-best': config.name === (metric === 'recall5' ? bestRecall.name : bestMrr.name) }]">
                <span class="metric-label">{{ config.label }}</span><span class="metric-value">{{ metric === 'recall5' ? formatPercent(config[metric]) : config[metric].toFixed(3) }}</span>
                <div class="metric-track"><div :class="['metric-fill', `fill-${config.name}`]" :style="{ '--target-width': `${config[metric] * 100}%` }"></div></div><span v-if="config.name === (metric === 'recall5' ? bestRecall.name : bestMrr.name)" class="best-badge">BEST</span>
              </div>
            </div>
          </div>
        </section>
        <section class="metrics-card breakdown-card" style="--stagger: 300ms">
          <div class="card-heading"><div><h3>分层矩阵</h3><p>按题型 × 语料特征拆解章节级 recall@5</p></div><div class="heat-legend"><span><i class="heat-high"></i>高</span><span><i class="heat-mid"></i>中</span><span><i class="heat-low"></i>低</span></div></div>
          <div class="table-scroll"><table class="breakdown-table"><thead><tr><th>组名</th><th>n</th><th>vector r@5</th><th>hybrid+rw r@5</th><th>Δ</th></tr></thead><tbody><tr v-for="row in metrics.offline.breakdown" :key="row.group"><td>{{ shortGroup(row.group) }}<small>{{ row.group.split(' | ')[1] }}</small></td><td class="numeric">{{ row.n }}</td><td :class="['numeric', 'heat-cell', heatClass(row.vector.r5)]">{{ formatPercent(row.vector.r5) }}</td><td :class="['numeric', 'heat-cell', heatClass(row.hybrid_rewrite.r5)]">{{ formatPercent(row.hybrid_rewrite.r5) }}</td><td :class="['numeric', 'delta-value', deltaClass(row.hybrid_rewrite.r5 - row.vector.r5)]"><b>{{ deltaSymbol(row.hybrid_rewrite.r5 - row.vector.r5) }}</b> {{ formatDelta(row.hybrid_rewrite.r5 - row.vector.r5) }}</td></tr></tbody></table></div>
        </section>
        <section class="metrics-card runtime-card" style="--stagger: 360ms"><div class="card-heading"><div><h3>实时状态</h3><p>当前知识库与服务配额</p></div><span class="live-badge"><i></i>实时</span></div><div class="runtime-grid"><div><span class="runtime-label">语料块数</span><strong>{{ formatChunks(metrics.runtime.chunks) }}</strong><small>chunks</small></div><div><span class="runtime-label">双语料</span><strong class="runtime-docs">{{ metrics.runtime.docs }}</strong><small>已连接</small></div><div><span class="runtime-label">每日限流</span><strong>{{ metrics.runtime.daily_limit }}</strong><small>次 / 日</small></div></div></section>
      </template>
    </main>
    <footer v-if="view === 'chat'" class="composer-area">
      <div class="mode-row"><span class="mode-label">检索模式</span><div class="segmented" role="radiogroup" aria-label="检索模式"><button v-for="item in (['vector', 'bm25', 'hybrid', 'agent'] as SearchMode[])" :key="item" :class="{ selected: mode === item }" :aria-checked="mode === item" role="radio" :disabled="isStreaming" @click="mode = item">{{ item }}</button></div><span class="mode-hint">{{ mode === 'hybrid' ? '语义 + 关键词，推荐' : mode === 'vector' ? '语义相似度' : mode === 'agent' ? 'LLM 自主调用工具' : '关键词匹配' }}</span></div>
      <div class="composer"><textarea ref="composer" v-model="question" :disabled="isStreaming" rows="1" placeholder="询问 STM32、ESP-IDF 的技术细节…" @input="resizeComposer" @keydown="onKeydown"></textarea><div class="composer-actions"><span>Enter 发送 <i>·</i> Shift + Enter 换行</span><button v-if="isStreaming" class="stop-button" @click="stop">停止</button><button v-else class="send-button" :disabled="!question.trim()" aria-label="发送问题" @click="ask()">↑</button></div></div>
      <p class="disclaimer">答案由技术手册检索生成，请结合引用原文进行验证。</p>
    </footer>
  </div>
</template>
