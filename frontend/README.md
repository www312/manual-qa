# 嵌入式手册智能问答

Vue 3 + TypeScript + Vite 的嵌入式技术手册 RAG 问答界面。页面通过 SSE 接收流式答案，并支持引用定位、检索模式切换与中断请求。

## 无后端演示

在两个终端分别运行：

```bash
npm run mock
npm run dev
```

然后打开 Vite 输出的地址即可体验完整问答流程。`mock/server.mjs` 会在 `8000` 端口提供 `/api/ask` SSE 服务，Vite 会将 `/api` 请求代理到该服务。

## 其他命令

```bash
npm run build     # 类型检查并构建生产包
npm run preview   # 预览生产包
```
