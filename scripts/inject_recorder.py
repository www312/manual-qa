"""在页面上下文注入 fetch 记录器：把 /api/ask 的响应帧写到 window 变量，
避免 CDP 5 秒超时。"""

print(js('''(() => {
  window.__sse_log = [];
  window.__frames = [];
  const orig = window.fetch;
  window.fetch = async function(...args) {
    const resp = await orig.apply(this, args);
    if (String(args[0]).includes('/api/ask')) {
      const clone = resp.clone();
      (async () => {
        const reader = clone.body.getReader();
        const dec = new TextDecoder();
        while (true) {
          const {done, value} = await reader.read();
          if (done) break;
          const chunk = dec.decode(value, {stream: true});
          window.__frames.push(chunk);
        }
        window.__sse_log.push('EOS');
      })();
    }
    return resp;
  };
  return 'recorder installed';
})()'''))
