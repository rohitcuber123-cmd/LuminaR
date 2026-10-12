import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { performance } from 'node:perf_hooks'
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { JSDOM } from 'jsdom'
import { RAGAnswer } from '../src/components/rag/RAGAnswer'
import { comparison } from './fixtures/rag-formatting'
import { unified } from 'unified'
import remarkParse from 'remark-parse'
import remarkMath from 'remark-math'
import { normalizeRAGMarkdown } from '../src/lib/ragAnswerMarkdown'

const samples: Record<string, string> = { mixed_fixture: comparison }
for (let i = 0; i < 5; i++) {
  const path = `../.scratch/private_rag_formatting_v2_4/answer_${i}.json`
  if (existsSync(path)) samples['live_' + i] = JSON.parse(readFileSync(path, 'utf8')).answer
}
const fetchBefore = globalThis.fetch
let networkCalls = 0
globalThis.fetch = async () => { networkCalls++; throw Error('Renderer must never call the network') }
const results = Object.entries(samples).map(([name, text]) => {
  for (let i = 0; i < 5; i++) renderToStaticMarkup(<RAGAnswer text={text} />)
  const timings: number[] = []
  let html = ''
  for (let i = 0; i < 50; i++) {
    const start = performance.now(); html = renderToStaticMarkup(<RAGAnswer text={text} />); timings.push(performance.now() - start)
  }
  const doc = new JSDOM(html).window.document
  const mathSources = [...doc.querySelectorAll('annotation')].map(n => n.textContent || '')
  const mathExact = mathSources.every(expression => text.includes(expression))
  if (!mathExact) throw Error('Formula source was changed')
  // Only content literals: list marker numbers and image/link URL paths are
  // Markdown structure, not source-critical answer text.
  const ast = unified().use(remarkParse).use(remarkMath).parse(normalizeRAGMarkdown(text))
  function content(node: any): string {
    if (typeof node.value === 'string') return node.value
    if (node.type === 'image') return node.alt || ''
    return (node.children || []).map(content).join(' ')
  }
  const tokens = content(ast).match(/\b(?:[01]{8,}|\d+(?:\.\d+)?%?)\b/g) || []
  const visible = doc.body.textContent || ''
  const missing = tokens.filter(token => !visible.includes(token))
  // Text may occur in an escaped HTML literal; digits must still survive.
  if (missing.length) throw Error('Lost literal ' + missing.join(', '))
  timings.sort((a, b) => a - b)
  return { name, characters: text.length, samples: timings.length, p50_ms: +timings[25].toFixed(2), p95_ms: +timings[47].toFixed(2), max_ms: +timings[49].toFixed(2),
    rendered_math_count: mathSources.length, math_annotations_match_backend_exactly: mathExact, numeric_tokens_preserved: true,
    headings: doc.querySelectorAll('h2,h3,h4').length, bold: doc.querySelectorAll('strong').length, tables: doc.querySelectorAll('table').length }
})
globalThis.fetch = fetchBefore
const output = { measurement: 'Warm synchronous React server render, complete Markdown parsing + KaTeX + React serialization. Excludes network/model time and browser layout; 5 warmups, 50 samples each.', network_calls: networkCalls, extra_qwen_calls: 0, results }
writeFileSync('../reports/private_rag_formatting_v2_4_performance.json', JSON.stringify(output, null, 2))
console.log(JSON.stringify(output, null, 2))
