/** Format number as Chinese Yuan */
export function yuan(val) {
  if (val == null) return '--'
  return Number(val).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

/** Format as percentage */
export function percent(val) {
  if (val == null) return '--'
  return (Number(val) * 100).toFixed(2) + '%'
}

/** Format large number (volume) */
export function volume(val) {
  if (val == null) return '--'
  if (val >= 1e8) return (val / 1e8).toFixed(2) + '亿'
  if (val >= 1e4) return (val / 1e4).toFixed(2) + '万'
  return val.toString()
}

/** Format timestamp/date string */
export function dateStr(val) {
  if (!val) return '--'
  return String(val).slice(0, 10)
}

/** Color for profit/loss */
export function pnlColor(val) {
  if (val == null) return ''
  return val >= 0 ? '#f56c6c' : '#67c23a'
}
