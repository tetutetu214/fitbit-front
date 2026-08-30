import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { coachApiPlugin } from './vite/coach-plugin'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const coachEnv = loadEnv(mode, process.cwd(), 'COACH_')
  return {
    plugins: [tailwindcss(), react(), coachApiPlugin(coachEnv.COACH_MODEL_ID)],
  }
})
