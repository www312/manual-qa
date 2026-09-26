import { createServer } from 'node:http'

const port = 8000
const citations = [
  { n: 1, chunk_id: 'rm0433-17878', doc: 'rm0433', chapter: '26 DAC > 26.7 DAC registers', page: 1079, score: 0.93, snippet: 'The APB1 peripheral clock enable register (RCC_APB1ENR) is used to enable the clock for the peripherals connected to APB1. The register offset is 0x58.' },
  { n: 2, chunk_id: 'esp-idf-gpio-0042', doc: 'esp-idf', chapter: 'GPIO > GPIO API Reference', page: 122, score: 0.87, snippet: 'Configure the GPIO pin using gpio_config_t. Input-only GPIOs can be configured with pull-up mode when the corresponding pad supports it.' },
  { n: 3, chunk_id: 'rm0433-03112', doc: 'rm0433', chapter: '2.3.4 Memory and bus architecture', page: 74, score: 0.81, snippet: 'DMA controllers can transfer data between memory and peripherals without CPU intervention. Carefully configure the data width, increment mode, and transfer completion interrupt.' },
]
const answer = '根据手册内容，建议先确认目标外设挂载的总线与时钟配置，再进行寄存器或驱动初始化。STM32H743 的相关外设需要先打开对应的 APB 时钟，RCC_APB1ENR 的地址偏移为 0x58 [1]。\n\n如果你在 ESP-IDF 中配置 GPIO，应通过 gpio_config_t 统一设置方向、上下拉和中断属性，并注意输入专用引脚的能力限制 [2]。涉及 DMA 传输时，还需要核对数据宽度、地址递增与传输完成中断，避免缓存一致性问题 [3]。'

function writeEvent(response, event, data) { response.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`) }
const server = createServer((request, response) => {
  if (request.method !== 'POST' || request.url !== '/api/ask') { response.writeHead(404, { 'Content-Type': 'application/json' }); response.end(JSON.stringify({ message: 'Not found' })); return }
  let body = ''
  request.on('data', (chunk) => { body += chunk })
  request.on('end', async () => {
    try { JSON.parse(body || '{}') } catch { response.writeHead(400); response.end(); return }
    response.writeHead(200, { 'Content-Type': 'text/event-stream; charset=utf-8', 'Cache-Control': 'no-cache', Connection: 'keep-alive', 'Access-Control-Allow-Origin': '*' })
    writeEvent(response, 'citations', { citations })
    const chunks = answer.match(/.{1,22}/gs) ?? [answer]
    for (const chunk of chunks) { if (response.destroyed) return; await new Promise((resolve) => setTimeout(resolve, 80)); writeEvent(response, 'delta', { text: chunk }) }
    writeEvent(response, 'done', { question_id: `mock_${Date.now()}`, latency_ms: 1680, tokens: 105 }); response.end()
  })
})
server.listen(port, () => console.log(`Mock SSE server listening at http://localhost:${port}`))
