/**
 * 组合计算工具 — 前端侧衍生指标计算
 *
 * 本模块中的计算原本由后端提供（标记为「便捷计算，前端也可完成」），
 * 此处实现前端版本，与后端等效。所有函数均为纯函数，不依赖后端状态。
 *
 * 使用方式：从 PortfolioDetail.vue 等组件中导入，传入原始数据即可得到结果。
 */

// ── 持仓维度计算 ──────────────────────────────────────

/** 持仓累计收益金额：(现价 - 成本价) × 股数 */
export function calcReturnAmount(currentPrice, costPrice, shares) {
  if (costPrice == null || currentPrice == null || costPrice <= 0) return null
  return (currentPrice - costPrice) * shares
}

/** 持仓累计收益率：(现价 / 成本价) - 1 */
export function calcReturnRate(currentPrice, costPrice) {
  if (costPrice == null || currentPrice == null || costPrice <= 0) return null
  return (currentPrice / costPrice) - 1
}

/** 个股当日收益率：(今收 - 昨收) / 昨收 */
export function calcDailyReturnRate(currentPrice, prevClose) {
  if (currentPrice == null || prevClose == null || prevClose <= 0) return null
  return (currentPrice - prevClose) / prevClose
}

// ── 组合维度计算 ──────────────────────────────────────

/** 累计收益：总市值 - 总成本 */
export function calcCumReturn(totalMarketValue, totalCost) {
  if (totalCost == null || totalMarketValue == null || totalCost <= 0) return null
  return totalMarketValue - totalCost
}

/** 累计收益率：(总市值 / 总成本) - 1 */
export function calcCumReturnRate(totalMarketValue, totalCost) {
  if (totalCost == null || totalMarketValue == null || totalCost <= 0) return null
  return (totalMarketValue / totalCost) - 1
}

// ── NAV 序列计算 ──────────────────────────────────────

/**
 * 从原始 NAV 序列计算每日收益。
 * @param {Array<{date: string, nav: number}>} navSeries - 按日期升序排列的 NAV 序列
 * @returns {Map<string, {returnAmount: number|null, returnRate: number|null}>} 日期 → 日收益
 */
export function calcDailyReturns(navSeries) {
  const result = new Map()
  let prevNav = null
  for (const record of navSeries) {
    let returnAmount = null
    let returnRate = null
    if (prevNav != null && prevNav > 0) {
      returnAmount = record.nav - prevNav
      returnRate = returnAmount / prevNav
    }
    prevNav = record.nav
    result.set(record.date, { return_amount: returnAmount, return_rate: returnRate })
  }
  return result
}

/**
 * 从原始 NAV 序列计算月度收益。
 * @param {Array<{date: string, nav: number}>} navSeries - 按日期升序排列的 NAV 序列
 * @param {number} year - 年份
 * @returns {Array<{month: number, return_amount: number|null, return_rate: number|null}>}
 */
export function calcMonthlyReturns(navSeries, year) {
  const byMonth = {}
  for (const record of navSeries) {
    const [ry, rm] = record.date.split('-').map(Number)
    if (ry !== year) continue
    if (!byMonth[rm]) byMonth[rm] = []
    byMonth[rm].push(record)
  }

  const result = []
  for (let month = 1; month <= 12; month++) {
    const monthData = byMonth[month]
    if (!monthData || monthData.length === 0) {
      result.push({ month, return_amount: null, return_rate: null })
      continue
    }
    const firstNav = monthData[0].nav
    const lastNav = monthData[monthData.length - 1].nav
    let return_amount = null
    let return_rate = null
    if (firstNav > 0) {
      return_amount = lastNav - firstNav
      return_rate = return_amount / firstNav
    }
    result.push({ month, return_amount, return_rate })
  }
  return result
}

// ── 格式化（与后端返回格式对齐）────────────────────────

/** 金额格式化 */
export function fmtMoney(v) {
  if (v == null) return '--'
  return v >= 0 ? '¥' + v.toFixed(2) : '-¥' + Math.abs(v).toFixed(2)
}

/** 收益率格式化 */
export function fmtRate(v) {
  if (v == null) return '--'
  return (v >= 0 ? '+' : '') + (v * 100).toFixed(2) + '%'
}

/** 颜色类名 */
export function moneyClass(v) { return v > 0 ? 'up' : v < 0 ? 'down' : 'zero' }
export function rateClass(v) { return v > 0 ? 'up' : v < 0 ? 'down' : 'zero' }
