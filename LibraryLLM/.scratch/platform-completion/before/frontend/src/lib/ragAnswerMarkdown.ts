import { unified } from 'unified'
import remarkParse from 'remark-parse'
import type { Root, RootContent } from 'mdast'

const parser = unified().use(remarkParse)

/** Adapt Qwen's delimiters, never the expression. Markdown's own parser
 * supplies protected ranges so code, HTML and link destinations stay literal.
 * JSON has already been decoded by response.json(); do not unescape it again.
 */
export function normalizeRAGMarkdown(answer: string): string {
  const source = answer.replace(/\r\n?/g, '\n')
  if (!source.includes('\\(') && !source.includes('\\[')) return source
  const protectedOffsets = new Uint8Array(source.length)
  function protect(node: Root | RootContent) {
    if (['code', 'inlineCode', 'html', 'link', 'image', 'definition'].includes(node.type)) {
      const start = node.position?.start.offset
      const end = node.position?.end.offset
      if (start != null && end != null) protectedOffsets.fill(1, start, end)
    } else if ('children' in node) {
      for (const child of node.children) protect(child as RootContent)
    }
  }
  protect(parser.parse(source))
  let output = ''
  for (let i = 0; i < source.length; i++) {
    const open = source.slice(i, i + 2)
    if (!protectedOffsets[i] && source[i - 1] !== '\\' && (open === '\\(' || open === '\\[')) {
      const closing = open === '\\(' ? '\\)' : '\\]'
      let end = source.indexOf(closing, i + 2)
      while (end >= 0 && source[end - 1] === '\\') end = source.indexOf(closing, end + 2)
      if (end >= 0 && !protectedOffsets.subarray(i, end + 2).includes(1)) {
        const expression = source.slice(i + 2, end)
        // Delimiter changes alone; digits, commands, units and subscripts remain exact.
        output += open === '\\(' ? '$' + expression + '$' : '\n\n$$\n' + expression + '\n$$\n\n'
        i = end + 1
        continue
      }
      if (end < 0) {
        // An unfinished model expression is readable literal code, not a
        // partially interpreted formula. Preserve its original characters.
        const lineEnd = source.indexOf('\n', i)
        const stop = lineEnd < 0 ? source.length : lineEnd
        const original = source.slice(i, stop)
        const runs = original.match(/`+/g) || []
        const ticks = '`'.repeat(Math.max(0, ...runs.map(run => run.length)) + 1)
        output += ticks + ' ' + original + ' ' + ticks
        i = stop - 1
        continue
      }
    }
    output += source[i]
  }
  return output
}
