import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5174,
    strictPort: true,
    allowedHosts: ['llmud.trazen.org'],
    // We are now telling Vite to proxy any API calls it doesn't recognize
    // to our Nginx Proxy Manager instance.    
  }
})