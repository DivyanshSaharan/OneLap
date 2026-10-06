import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'
import { workerSource } from './build/worker.ts'

function offlineShell(): Plugin {
  return {
    name: 'onelap-offline-shell',
    apply: 'build',
    generateBundle(_options, bundle) {
      const files = Object.keys(bundle)
        .filter((name) => !name.endsWith('.map'))
        .sort()
      const hash = createHash('sha256')
      hash.update(workerSource([], 'version-placeholder'))
      for (const name of files) {
        const item = bundle[name]
        hash
          .update(name)
          .update(item.type === 'chunk' ? item.code : item.source)
      }
      for (const name of ['icon.svg', 'manifest.webmanifest']) {
        hash
          .update(name)
          .update(readFileSync(new URL(`./public/${name}`, import.meta.url)))
      }
      const version = hash.digest('hex').slice(0, 16)
      this.emitFile({
        type: 'asset',
        fileName: 'sw.js',
        source: workerSource(
          [
            'index.html',
            'icon.svg',
            'manifest.webmanifest',
            ...files.filter((file) => file !== 'index.html'),
          ],
          `onelap-shell-${version}`,
        ),
      })
    },
  }
}

export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  plugins: [react(), offlineShell()],
  server: { strictPort: true, proxy: { '/api': 'http://127.0.0.1:8770' } },
  preview: { strictPort: true, proxy: { '/api': 'http://127.0.0.1:8770' } },
  build: { outDir: '../dist', emptyOutDir: true },
})
