export const STATUS_LABELS = {
  open: '待认领',
  claimed: '认领中',
  sourcing_paused: '寻货暂停',
  released: '已释放',
  fulfilled: '已完成',
}

export function statusLabel(s) {
  return STATUS_LABELS[s] || s
}

export function formatRemaining(sec) {
  if (sec == null) return ''
  if (sec >= 3600) {
    const h = Math.floor(sec / 3600)
    const m = Math.floor((sec % 3600) / 60)
    return `${h}小时${m}分`
  }
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

const CLAIMER_KEY = 'wishclaim_claimer'

export function loadClaimer() {
  try { return localStorage.getItem(CLAIMER_KEY) || '' } catch { return '' }
}

export function saveClaimer(name) {
  try { localStorage.setItem(CLAIMER_KEY, name || '') } catch {}
}
