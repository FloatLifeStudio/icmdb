// 列宽自适应:用 canvas 测量文本实际宽度,让列默认宽到刚好放下最长内容。
// 用法:数据加载后按列定义算出 min-width 表,模板里 :min-width="widths.xxx"。

let ctx: CanvasRenderingContext2D | null = null

const FONT =
  '14px "Helvetica Neue", Helvetica, PingFang SC, Hiragino Sans GB, Microsoft YaHei, sans-serif'
const BOLD_FONT = `bold ${FONT}`

// cell 左右 padding 24px + 边框与测量余量
const PAD = 30

function measure(text: string, font: string): number {
  if (!ctx) {
    ctx = document.createElement('canvas').getContext('2d')
  }
  if (!ctx) return text.length * 8
  ctx.font = font
  return ctx.measureText(text).width
}

export function textWidth(text: string): number {
  return measure(text, FONT)
}

// 多行文本取最宽的一行(行内各自换行显示时,列宽只需放下最长行)
export function longestLine(lines: string[]): string {
  return lines.reduce(
    (longest, line) => (textWidth(line) > textWidth(longest) ? line : longest),
    '',
  )
}

export interface FitCol<R> {
  key: string
  label: string
  // 自定义取值(默认取 String(row[key]));渲染为 '-' 的列传 text 返回 '-'
  text?: (row: R) => string
}

function valueAt(row: unknown, key: string): unknown {
  return (row as Record<string, unknown>)[key]
}

// 算各列 min-width:列头(粗体)与该列所有行取值中最宽者 + padding
export function fitMinWidths<R>(
  rows: readonly R[],
  cols: FitCol<R>[],
): Record<string, number> {
  const out: Record<string, number> = {}
  for (const col of cols) {
    let max = measure(col.label, BOLD_FONT)
    for (const row of rows) {
      const raw = col.text ? col.text(row) : valueAt(row, col.key)
      const s = raw == null || raw === '' ? '-' : String(raw)
      max = Math.max(max, textWidth(s))
    }
    out[col.key] = Math.ceil(max) + PAD
  }
  return out
}
