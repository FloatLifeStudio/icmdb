// Column width auto-fit: measure actual text width with canvas so the default column width just fits the longest content
// Usage: after data loads, compute the min-width map from column definitions, then use :min-width="widths.xxx" in the template

let ctx: CanvasRenderingContext2D | null = null

const FONT =
  '14px "Helvetica Neue", Helvetica, PingFang SC, Hiragino Sans GB, Microsoft YaHei, sans-serif'
const BOLD_FONT = `bold ${FONT}`

// cell left/right padding 24px plus border and measurement margin
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

// Take the widest line of multi-line text (when lines wrap individually, the column only needs to fit the longest line)
export function longestLine(lines: string[]): string {
  return lines.reduce(
    (longest, line) => (textWidth(line) > textWidth(longest) ? line : longest),
    '',
  )
}

export interface FitCol<R> {
  key: string
  label: string
  // Custom value getter (defaults to String(row[key])); for columns rendered as '-', text returns '-'
  text?: (row: R) => string
}

function valueAt(row: unknown, key: string): unknown {
  return (row as Record<string, unknown>)[key]
}

// Compute each column's min-width: widest of the bold header and all row values in that column, plus padding
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
