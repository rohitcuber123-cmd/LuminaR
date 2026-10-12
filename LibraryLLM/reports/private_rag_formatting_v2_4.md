# Private RAG answer formatting V2.4

Formatting implementation and validation: **PASS**. Scope: the existing Know More → Ask Document frontend. Backend generation quality findings are recorded separately below; formatting success does not certify the accuracy of generated answers.

## X. Renderer before / after

`frontend/src/pages/LLMPage.tsx` previously placed `message.text` directly inside a `div` with `whitespace-pre-wrap`. This escaped HTML safely but displayed Markdown and LaTeX literally. Searches found no Markdown/math renderer elsewhere in the frontend.

Assistant answers now use a lazy-loaded `RAGAnswer` React component. User questions stay plain text. Grounding badges and API-owned source cards remain outside the Markdown body. Existing Ask Document source cards are filename/page chips, not navigation buttons; Knowledge Tools' trusted source buttons are untouched. The response's existing seven sources still yield the same first five visible chips.

The chat region now allows 1100px, with prose bounded to 1000px and responsive wrapping. Generated headings use the existing sans font at 20–24px; Markdown H1 maps to H2. Paragraphs, lists and blockquotes have compact spacing. No article card or extra vertical scrollbar was added. Composer padding reserves the existing launcher's footprint on desktop and phones.

## Y. Markdown

Pinned `react-markdown` 10.1.0, `remark-gfm` 4.0.1 and the compatible unified/remark parser stack. Semantic headings, paragraphs, strong/emphasis, nested ul/ol/li, inline code, fenced code, blockquotes and GFM tables render through React AST nodes. There is no raw model `dangerouslySetInnerHTML`, HTML parser plugin, syntax-highlighting library or second Markdown stack.

Line endings are normalized to LF. No blanket unescaping, punctuation rewriting, literal rewriting or removal of deliberately escaped Markdown occurs. The normalizer uses Markdown AST offsets to protect inline/fenced/indented code, HTML and link/image destinations before adapting Qwen delimiters.

## Z. Math

`remark-math` 6.0.0 and `rehype-katex` 7.0.1 use KaTeX 0.19.0. The dependency override makes both math plugins use the same patched KaTeX as the direct dependency and stylesheet. Initial installation exposed vulnerable nested older KaTeX versions; the override removed those advisories. The existing source-map-js advisory was resolved through its compatible patched update. Final npm audit: zero vulnerabilities.

Support: inline `\(...\)` / `$...$`, display `\[...\]` / `$$...$$`. Only delimiter wrappers change. Formula bodies, fractions, subscripts, digits and commands remain exact. No LaTeX-to-English replacements. JSON response decoding was audited: actual Qwen expressions contain single backslashes after `response.json()`, so no transport hack or double-decoding was introduced. Explicitly escaped double backslashes remain literal.

KaTeX CSS is imported once in `main.tsx`. Its math fonts and the new answer stylesheet do not change global LuminaR prose typography. Accessible MathML and original-expression annotations accompany selectable HTML math. Invalid expressions use the original expression in a monospace fallback; unfinished Qwen delimiters become literal inline code. Fenced code stays code, including fences labelled `math`.

KaTeX runs with `trust:false`, `maxExpand:1000`, `maxSize:20`, independent macro state per expression. Dangerous links, images and HTML extensions are disabled. Long display and inline formulas scroll locally rather than widening the page.

Ask Document currently awaits one JSON response; it does not stream. CommonMark handles incomplete Markdown without crashing, and malformed/incomplete math is covered by fixtures. No prompt, generation, retrieval, verdict or transport change was needed.

## AA. Tables and technical literals

GFM tables have cream headers, subtle theme borders and padding. A focusable, labelled wrapper supplies local horizontal scrolling; fenced code and display equations are also keyboard-focusable. A 12-column table, 45-term equation, 800-digit code line and long unbroken word all retain their content. Prose wraps normally.

Frontend fixtures preserve `10101011`, `2`, `0.184`, `36.8%`, units, subscripts and fractions. All live math annotations match the backend answer's exact mathematical source. Numeric fidelity checks operate on content AST nodes, excluding Markdown list markers and image/link URL destinations. Formatting does not substitute a corrected factual answer for the model's answer.

## AB. Security

[Security results](./private_rag_formatting_v2_4_security.json): PASS. Explicit tests cover script tags, img/onerror, javascript URLs, inert external links, suppressed Markdown remote images, KaTeX href/includegraphics/htmlClass, bounded recursive macros and macro isolation. Model HTML remains escaped text; arbitrary HTML support is disabled. Markdown links display their labels without navigation, and Markdown images display alt text without fetching remote content. Source identity remains application-controlled.

26 new frontend tests include real Know More integration checks for separate source cards and both Grounded/Unsupported badges. Test command: `npm run test:rag-formatting`.

## AC. Mobile

Browser-measured exact viewports: **375×812** and **390×844**. Both the visual stress fixture and real CN answer have no page-wide overflow. The stress fixture's wide table, code and equation have `overflow-x:auto` with scroll width greater than client width. Keyboard ArrowRight moved the table's scroll position.

At 375×812, the last real source chip ends at y=546px; the launcher starts at y=744px. At 390×844, sources end at y=578px; the launcher starts at y=776px. Composer Ask controls end before the launcher's left edge. Desktop Ask ends at x=1103px, before the launcher at x=1134px.

Evidence: [geometry](./private_rag_formatting_v2_4_browser_geometry.json), [desktop](./private_rag_formatting_v2_4_desktop.png), [390px answer](./private_rag_formatting_v2_4_mobile_390.png), [375px sources](./private_rag_formatting_v2_4_sources_375.png), [375px stress fixture](./private_rag_formatting_v2_4_fixture_375.png). Dev-only reproducible fixture: `/tests/fixtures/rag-formatting.html` on the existing Vite server; excluded from the production entry.

## AD. Live CN validation

Used the user's original 29-page CN PDF through isolated disposable localhost reader sessions. Five real API answers were rendered with the production component and checked for mathematical and numeric fidelity:

| Question | Existing backend verdict | Rendering |
|---|---|---|
| differences between pure and slotted aloha | SUPPORTED | Seven headings, seven strong spans, five exact math annotations |
| what is sfd | NOT_SUPPORTED | Unsupported text preserved |
| explain vulnerable time | SUPPORTED | Bold term and one exact math annotation |
| compare flow control and error control | SUPPORTED | Headings, bold and lists; model's external image becomes inert alt text |
| What is the SFD bit pattern? Include the exact binary string from the document. | SUPPORTED | Binary literal preserved exactly |

The real browser additionally reproduced the original ALOHA case with formatted headings, bold bullets and all five math expressions, five unchanged source chips and Grounded badge. It also displayed the real Unsupported SFD response correctly. [Live results](./private_rag_formatting_v2_4_live.json) and [browser checks](./private_rag_formatting_v2_4_browser_live.json).

**Existing generation findings:** the broad SFD question remains unsupported; the binary question's model answer says `10100011`, while the original PDF contains `10101011` (one occurrence, and zero occurrences of `10100011`). The renderer preserves the returned value rather than silently rewriting it. The ALOHA answer also contains existing spelling errors and a truncated final sentence. These are backend generation issues outside this explicitly frontend-only request. This phase makes no new claim that the backend's SUPPORTED label guarantees factual correctness.

## AE. Bundle and performance

[Bundle audit](./private_rag_formatting_v2_4_bundle.json) uses the same Python gzip measurement before/after. Lazy renderer: **432,260 bytes raw / 127,497 bytes gzip (~124.5 KiB)**; downloaded only when an assistant answer needs formatting. Main JS increases only **423 bytes raw / 172 bytes gzip**. Main CSS increases **32,155 bytes raw / 9,011 bytes gzip**. Available WOFF2 math fonts total 256,168 bytes; browsers request only fonts needed by the displayed glyphs. No highlighting baggage.

[Production performance](./private_rag_formatting_v2_4_performance.json): five warmups and 50 synchronous React server renders per sample, covering complete Markdown parsing, KaTeX and serialization. Actual CN ALOHA answer: p50 **9.47ms**, p95 **12.72ms**, maximum **13.63ms**. Mixed table/math fixture: p95 **14.50ms**. Other live answers: p95 **0.56–5.17ms**. This measures rendering only, excluding initial asset download, browser layout and the existing model's much slower generation time. Renderer application API calls: **0**; extra Qwen calls: **0**.

## Regression, scope and cleanup

[Regression results](./private_rag_formatting_v2_4_regression.json): **324/324 frontend tests**, including Know More, Knowledge Tools, Quiz, Flashcards, Assistant, Events and admin/notifications coverage. **1270 passing backend test executions**, with **10 skipped tests requiring explicitly prepared isolated MongoDB validation data**. Backend groups cover Private Document RAG/cache/preparation, DKM/artifacts/quiz, OCR native/mixed/blank/failed/size/page-limit behavior, Assistant, security, Events/presets, staff, notifications, circulation and search. Some group coverage overlaps; these are execution counts, not a unique-case claim.

Frontend TypeScript/production build succeeds; lint has zero errors and 19 pre-existing warnings. The existing >500kB main-bundle warning remains. No Router research runs. All five service checks return HTTP 200.

Of 211 baseline source files, 209 remain byte-identical. Existing production files changed in this phase: only `LLMPage.tsx` and `main.tsx`, plus package manifest/lockfile and new renderer/normalizer/styles. Backend, RAG, recommendation, verdict, DKM, quiz, flashcards and OCR source hashes remain unchanged. Existing uncommitted work was preserved.

Owned test documents/accounts were removed; the session expired normally during validation and cleanup used the existing purge operation strictly on the marked disposable reader's rows. Original PDF untouched. Full source answers and credentials were held only in ignored temporary scratch and removed after validation. No external model/provider upload.

Implementation references: [react-markdown](https://github.com/remarkjs/react-markdown), [remark-math](https://github.com/remarkjs/remark-math), [KaTeX options and trust policy](https://katex.org/docs/options.html).
