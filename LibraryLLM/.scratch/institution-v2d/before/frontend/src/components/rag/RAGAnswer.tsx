import { memo } from 'react'
import Markdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import type { Root, Element, ElementContent } from 'hast'
import type { VFile } from 'vfile'
import { normalizeRAGMarkdown } from '../../lib/ragAnswerMarkdown'

const components: Components = {
  h1: ({ children }) => <h2 className="rag-answer-title">{children}</h2>,
  h2: ({ children }) => <h2>{children}</h2>,
  h3: ({ children }) => <h3>{children}</h3>,
  h4: ({ children }) => <h4>{children}</h4>,
  // Model-written links/images aren't authoritative citations. No navigation
  // or remote image requests; trusted source cards remain outside this body.
  a: ({ children }) => <span>{children}</span>,
  img: ({ alt }) => <span>{alt}</span>,
  table: ({ children }) => <div className="rag-answer-scroll" role="region" aria-label="Answer table" tabIndex={0}><table>{children}</table></div>,
  pre: ({ children }) => <pre tabIndex={0} aria-label="Answer code block">{children}</pre>,
  span: ({ node: _node, className, children, ...props }) => {
    if (className?.split(' ').includes('katex-error')) return <code className="rag-math-fallback" title="Expression could not be rendered">{children}</code>
    const scrollable = className?.split(' ').includes('katex-display')
    return <span {...props} className={className} {...(scrollable ? { tabIndex: 0, role: 'region', 'aria-label': 'Answer equation' } : {})}>{children}</span>
  },
}

const remarkPlugins = [remarkGfm, remarkMath]
// rehype-katex recovers unsupported commands with red math text. Use the
// original complete expression in monospace for every reported parse failure.
function safeKatex() {
  const renderMath = rehypeKatex({ trust: false, strict: 'ignore', maxExpand: 1000, maxSize: 20, output: 'htmlAndMathml' })
  function text(node: ElementContent): string {
    return node.type === 'text' ? node.value : 'children' in node ? node.children.map(text).join('') : ''
  }
  return (tree: Root, file: VFile) => {
    function walk(parent: Root | Element) {
      for (let i = 0; i < parent.children.length; i++) {
        const node = parent.children[i]
        if (node.type !== 'element') continue
        const mathNode = node.tagName === 'pre' && node.children.length === 1 && node.children[0].type === 'element'
          ? node.children[0] : node
        const classes = mathNode.properties.className
        if (Array.isArray(classes) && classes.some(c => c === 'math-inline' || c === 'math-display')) {
          const expression = text(node)
          const isolated: Root = { type: 'root', children: [node] }
          const before = file.messages.length
          renderMath(isolated, file)
          const result: ElementContent[] = file.messages.length > before
            ? [{ type: 'element', tagName: 'code', properties: { className: ['rag-math-fallback'], title: 'Expression could not be rendered' }, children: [{ type: 'text', value: expression }] }]
            : isolated.children as ElementContent[]
          parent.children.splice(i, 1, ...result)
          i += result.length - 1
        } else walk(node)
      }
    }
    walk(tree)
  }
}
const rehypePlugins: NonNullable<Parameters<typeof Markdown>[0]['rehypePlugins']> = [
  safeKatex,
]

export const RAGAnswer = memo(function RAGAnswer({ text }: { text: string }) {
  return <div className="rag-answer">
    <Markdown components={components} remarkPlugins={remarkPlugins} rehypePlugins={rehypePlugins}>
      {normalizeRAGMarkdown(text)}
    </Markdown>
  </div>
})

export default RAGAnswer
