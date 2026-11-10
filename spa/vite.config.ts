import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // The runner only accepts this origin, so don't drift to another port.
  server: { port: 5173, strictPort: true },
})
