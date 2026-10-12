// Dev-only visual fixture. The production Vite entry does not include this page.
import React from 'react'
import { createRoot } from 'react-dom/client'
import '../src/index.css'
import 'katex/dist/katex.min.css'
import '../src/components/rag/RAGAnswer.css'
import { RAGAnswer } from '../src/components/rag/RAGAnswer'
import { comparison, wideTable, longMath, wideCode } from './fixtures/rag-formatting'

createRoot(document.getElementById('root')!).render(<main style={{ padding: 20, maxWidth: 1100, margin: 'auto', fontSize: '.9rem' }}>
  <h1 style={{ fontSize: 26 }}>Ask Document · Formatting fixture</h1>
  <p>Local test content. Scroll areas below intentionally exceed a phone’s width.</p>
  <RAGAnswer text={comparison} />
  <RAGAnswer text={wideTable + '\n\n' + longMath + wideCode + '\n\n' + 'LongToken'.repeat(50)} />
  <RAGAnswer text={String.raw`### Malformed source remains readable

$\frac{2}{$

**Unclosed bold and \(2 \times T`} />
  <button>Final source control</button>
</main>)
