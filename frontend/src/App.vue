<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

type SearchMode = 'vector' | 'bm25' | 'hybrid'
type Citation = { n: number; chunk_id: string; doc: string; chapter: string; page: number; score: number; snippet: string }
type Message = { id: number; role: 'user' | 'assistant'; text: string; citations?: Citation[]; loading?: boolean; error?: boolean; latency?: number }
type StreamPayload = Record<string, unknown>

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
const composer = ref<HTMLTextAreaElement | null>(null)
const conversation = ref<HTMLElement | null>(null)
let controller: AbortController | null = null
let nextMessageId = 1

const lastQuestion = computed(() => [...messages.value].reverse().find((item) => item.role === 'user')?.text ?? '')

function resizeComposer() {
  const element = composer.value
  if (!element) return
  element.style.height = 'auto'
  element.style.height = `${Math.min(element.scrollHeight, 160)}px`
}
function scrollToBottom() { nextTick(() => conversation.value?.scrollTo({ top: conversation.value.scrollHeight, behavior: 'smooth' })) }
function renderAnswer(text: string): string { return text.replace(/\[(\d+)\]/g, '<sup class="inline-citation" data-citation="$1">[$1]</sup>') }
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
  const answerMessage: Message = { id: nextMessageId++, role: 'assistant', text: '', citations: [], loading: true }
  messages.value.push({ id: nextMessageId++, role: 'user', text }, answerMessage)
  isStreaming.value = true
  controller = new AbortController()
  scrollToBottom()
  try {
    const response = await fetch('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' }, body: JSON.stringify({ question: text, mode: mode.value, k: 5 }), signal: controller.signal })
    if (!response.ok || !response.body) throw new Error(`请求失败（${response.status}）`)
    await readSse(response.body, (event, payload) => {
      if (event === 'citations') { answerMessage.citations = Array.isArray(payload.citations) ? payload.citations as Citation[] : []; answerMessage.loading = false }
      else if (event === 'delta' && typeof payload.text === 'string') { answerMessage.loading = false; answerMessage.text += payload.text; scrollToBottom() }
      else if (event === 'done' && typeof payload.latency_ms === 'number') answerMessage.latency = payload.latency_ms
      else if (event === 'error') throw new Error(typeof payload.message === 'string' ? payload.message : '服务返回错误')
    })
  } catch (error) {
    if ((error as Error).name !== 'AbortError') { answerMessage.loading = false; answerMessage.error = true; answerMessage.text = `暂时无法获取答案：${error instanceof Error ? error.message : '未知错误'}` }
  } finally { answerMessage.loading = false; isStreaming.value = false; controller = null; scrollToBottom() }
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
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand-mark" aria-hidden="true"><span></span><span></span><span></span></div>
      <div><h1>嵌入式手册智能问答</h1><p>STM32H743 RM0433 + ESP-IDF <span class="dot">·</span> 21.7 万块技术语料</p></div>
      <div class="topbar-status"><i></i>知识库已连接</div>
    </header>
    <main ref="conversation" class="conversation" aria-live="polite">
      <section v-if="messages.length === 0" class="empty-state">
        <div class="empty-icon">⌁</div><h2>从一个问题开始</h2><p>向你的嵌入式技术手册提问，答案会附带可追溯的原文引用。</p>
        <div class="example-grid"><button v-for="example in examples" :key="example.question" class="example-card" @click="ask(example.question)"><span>{{ example.label }}</span><strong>{{ example.question }}</strong><b>↗</b></button></div>
      </section>
      <section v-else class="message-list">
        <article v-for="message in messages" :key="message.id" :class="['message', message.role]">
          <div v-if="message.role === 'user'" class="user-bubble">{{ message.text }}</div>
          <div v-else class="answer-wrap">
            <div class="answer-meta"><span class="answer-avatar">✦</span><span>手册助手</span><span class="answer-label">AI 回答</span></div>
            <div v-if="message.loading" class="skeleton" aria-label="正在检索引用"><span></span><span></span><span></span></div>
            <div v-else-if="message.error" class="answer error-answer">{{ message.text }}</div>
            <div v-else class="answer" @click="handleAnswerClick" v-html="renderAnswer(message.text)"></div>
            <div v-if="message.text && !message.error" class="answer-footer"><span v-if="message.latency">检索与生成耗时 {{ (message.latency / 1000).toFixed(1) }}s</span><button v-if="lastQuestion && !isStreaming" @click="rerun">↻ 用当前模式重问</button></div>
            <div v-if="message.citations?.length" class="citations-panel">
              <div class="citations-heading"><span>引用来源</span><small>{{ message.citations.length }} 条相关内容</small></div>
              <div class="citation-list"><button v-for="citation in message.citations" :id="`citation-${citation.n}`" :key="citation.n" :class="['citation-card', { active: activeCitation === citation.n }]" @mouseenter="activeCitation = citation.n" @mouseleave="activeCitation = null" @click="expandedCitation = expandedCitation === citation.n ? null : citation.n"><span class="citation-number">[{{ citation.n }}]</span><span class="doc-icon">▤</span><span class="citation-main"><span class="citation-title">{{ citation.chapter }}</span><span class="citation-detail">{{ citationDocLabel(citation.doc) }} <i>·</i> p. {{ citation.page }}</span><span class="citation-snippet">{{ expandedCitation === citation.n ? citation.snippet : `${citation.snippet.slice(0, 86)}${citation.snippet.length > 86 ? '…' : ''}` }}</span></span><span class="score">{{ Math.round(citation.score * 100) }}%</span><span class="expand-mark">{{ expandedCitation === citation.n ? '⌃' : '⌄' }}</span></button></div>
            </div>
          </div>
        </article>
      </section>
    </main>
    <footer class="composer-area">
      <div class="mode-row"><span class="mode-label">检索模式</span><div class="segmented" role="radiogroup" aria-label="检索模式"><button v-for="item in (['vector', 'bm25', 'hybrid'] as SearchMode[])" :key="item" :class="{ selected: mode === item }" :aria-checked="mode === item" role="radio" :disabled="isStreaming" @click="mode = item">{{ item }}</button></div><span class="mode-hint">{{ mode === 'hybrid' ? '语义 + 关键词，推荐' : mode === 'vector' ? '语义相似度' : '关键词匹配' }}</span></div>
      <div class="composer"><textarea ref="composer" v-model="question" :disabled="isStreaming" rows="1" placeholder="询问 STM32、ESP-IDF 的技术细节…" @input="resizeComposer" @keydown="onKeydown"></textarea><div class="composer-actions"><span>Enter 发送 <i>·</i> Shift + Enter 换行</span><button v-if="isStreaming" class="stop-button" @click="stop">停止</button><button v-else class="send-button" :disabled="!question.trim()" aria-label="发送问题" @click="ask">↑</button></div></div>
      <p class="disclaimer">答案由技术手册检索生成，请结合引用原文进行验证。</p>
    </footer>
  </div>
</template>
