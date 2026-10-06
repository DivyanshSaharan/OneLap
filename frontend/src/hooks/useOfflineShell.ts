import { useEffect, useRef, useState } from 'react'

export function useOfflineShell() {
  const [state, setState] = useState<
    'loading' | 'ready' | 'development' | 'unavailable'
  >('loading')
  const [updateAvailable, setUpdateAvailable] = useState(false)
  const registration = useRef<ServiceWorkerRegistration | null>(null)
  const reloadRequested = useRef(false)

  useEffect(() => {
    if (!import.meta.env.PROD) {
      setState('development')
      return
    }
    if (!window.isSecureContext || !('serviceWorker' in navigator)) {
      setState('unavailable')
      return
    }
    let cancelled = false
    const serviceWorker = navigator.serviceWorker
    let removeUpdateListeners = () => {}
    const timeout = window.setTimeout(() => {
      if (!cancelled) setState('unavailable')
    }, 20000)
    const changed = () => {
      if (reloadRequested.current) window.location.reload()
    }
    serviceWorker.addEventListener('controllerchange', changed)
    serviceWorker
      .register('/sw.js')
      .then(async (value) => {
        if (cancelled) return
        registration.current = value
        if (value.waiting && value.active) setUpdateAvailable(true)
        const workers = new Map<ServiceWorker, () => void>()
        const updateFound = () => {
          const installing = value.installing
          if (!installing || workers.has(installing)) return
          const stateChanged = () => {
            if (
              !cancelled &&
              installing.state === 'installed' &&
              value.waiting &&
              value.active
            )
              setUpdateAvailable(true)
          }
          workers.set(installing, stateChanged)
          installing.addEventListener('statechange', stateChanged)
        }
        value.addEventListener('updatefound', updateFound)
        updateFound()
        removeUpdateListeners = () => {
          value.removeEventListener('updatefound', updateFound)
          for (const [worker, listener] of workers)
            worker.removeEventListener('statechange', listener)
        }
        await serviceWorker.ready
        window.clearTimeout(timeout)
        if (!cancelled) setState('ready')
      })
      .catch(() => {
        window.clearTimeout(timeout)
        if (!cancelled) setState('unavailable')
      })
    return () => {
      cancelled = true
      window.clearTimeout(timeout)
      removeUpdateListeners()
      serviceWorker.removeEventListener('controllerchange', changed)
    }
  }, [])

  return {
    state,
    updateAvailable,
    update: () => {
      if (registration.current?.waiting) {
        reloadRequested.current = true
        registration.current.waiting.postMessage('SKIP_WAITING')
      }
    },
  }
}
