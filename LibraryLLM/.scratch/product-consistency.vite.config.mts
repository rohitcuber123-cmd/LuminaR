import base from '../frontend/vite.config'
export default { ...base, server: { ...base.server, proxy: { ...base.server?.proxy,
  '/api': { target: 'http://127.0.0.1:8088', changeOrigin: true, rewrite: (path: string) => path.replace(/^\/api/, '') }
} } }
