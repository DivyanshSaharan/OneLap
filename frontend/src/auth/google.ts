import { ApiError } from '../api'

export interface GoogleIdentity {
  initialize(options: {
    client_id: string
    nonce: string
    ux_mode: 'popup'
    auto_select: false
    callback: (result: { credential: string }) => void
  }): void
  renderButton(
    element: HTMLElement,
    options: {
      theme: 'outline'
      size: 'large'
      text: 'continue_with'
      width: number
    },
  ): void
  disableAutoSelect(): void
}

declare global {
  interface Window {
    google?: { accounts: { id: GoogleIdentity } }
  }
}

let loading: Promise<GoogleIdentity> | null = null

export function loadGoogle(): Promise<GoogleIdentity> {
  if (window.google?.accounts.id)
    return Promise.resolve(window.google.accounts.id)
  if (loading) return loading
  loading = new Promise<GoogleIdentity>((resolve, reject) => {
    const script = document.createElement('script')
    const timeout = window.setTimeout(failed, 15_000)
    function failed() {
      window.clearTimeout(timeout)
      script.remove()
      loading = null
      reject(new ApiError('google_widget_unavailable'))
    }
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.onload = () => {
      window.clearTimeout(timeout)
      if (window.google?.accounts.id) resolve(window.google.accounts.id)
      else failed()
    }
    script.onerror = failed
    document.head.append(script)
  })
  return loading
}
