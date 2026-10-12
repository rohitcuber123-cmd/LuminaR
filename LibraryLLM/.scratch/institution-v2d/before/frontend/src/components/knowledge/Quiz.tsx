import { useEffect, useRef, useState } from 'react'
import type { ClozeGrade, Question } from '../../lib/knowledgeArtifacts'
import { SourceLink } from './SourceLink'
import { toolButton } from './styles'

const control = 'my-3 w-full min-w-0 max-w-full border border-line bg-paper p-2 text-sm focus-visible:outline-2 focus-visible:outline-brand disabled:opacity-40'
// Preserve normalization for previously saved true/false items only.
const normalize = (value: string) => value.trim().toLowerCase().replace(/[^\p{L}\p{N}\s]/gu, '').replace(/\s+/g, ' ')

export function Quiz({ questions, onSource, onGrade }: { questions: Question[]; onSource: (id: string) => void;
  onGrade?: (id: string, answer: string, signal: AbortSignal) => Promise<ClozeGrade> }) {
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [matches, setMatches] = useState<Record<string, Record<string, string>>>({})
  const [checked, setChecked] = useState<Record<string, boolean>>({})
  const [index, setIndex] = useState(0)
  const [grades, setGrades] = useState<Record<string, ClozeGrade>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState<Record<string, boolean>>({})
  const requests = useRef(new Map<string, AbortController>())
  useEffect(() => { const active = requests.current; return () => { active.forEach(request => request.abort()); active.clear() } }, [])
  const submitCloze = async (id: string) => {
    if (requests.current.has(id) || checked[id] || !answers[id]?.trim()) return
    if (!onGrade) { setErrors(current => ({ ...current, [id]: 'Open this quiz again to check your answer.' })); return }
    const abort = new AbortController(); requests.current.set(id, abort)
    setBusy(current => ({ ...current, [id]: true })); setErrors(current => ({ ...current, [id]: '' }))
    try {
      const result = await onGrade(id, answers[id], abort.signal)
      if (!abort.signal.aborted) { setGrades(current => ({ ...current, [id]: result })); setChecked(current => ({ ...current, [id]: true })) }
    } catch (error) {
      if (!abort.signal.aborted) setErrors(current => ({ ...current, [id]: error instanceof Error ? error.message : 'Answer checking failed. Keep your answer and retry.' }))
    } finally {
      if (requests.current.get(id) === abort) requests.current.delete(id)
      if (!abort.signal.aborted) setBusy(current => ({ ...current, [id]: false }))
    }
  }
  const safeIndex = Math.min(index, Math.max(0, questions.length - 1))
  return <div className="space-y-4">
    <p className="text-sm text-ink-soft">Equivalent short answers are accepted when supported by the document. Answers are checked after you submit.</p>
    <p className="text-center text-sm" aria-live="polite">Question {safeIndex + 1} of {questions.length}</p>
    {questions.slice(safeIndex, safeIndex + 1).map(q => {
      const i = safeIndex
      const matching = q.type === 'matching'
      const ready = matching ? q.leftItems.every(left => matches[q.id]?.[left.id]) : !!answers[q.id]?.trim()
      const pairsCorrect = matching ? q.leftItems.filter(left => matches[q.id]?.[left.id] === q.correctMatches[left.id]).length : 0
      return <div key={q.id} className="min-w-0 border border-line bg-panel p-4">
        <p className="mb-2 text-xs uppercase text-ink-soft">{q.type === 'mcq' ? 'Multiple Choice' : matching ? 'Match the Following' : q.type === 'true_false' ? 'Saved True / False' : 'Fill in the Blanks'}</p>
        {q.type === 'mcq' ? <fieldset disabled={checked[q.id]}>
          <legend className="leading-relaxed">{i+1}. {q.question}</legend>
          <div className="my-3 space-y-2">{q.options.map((option, index) => <label key={option} className="flex items-start gap-2 break-words text-sm">
            <input type="radio" name={q.id} value={option} checked={answers[q.id] === option}
              onChange={() => setAnswers(current => ({ ...current, [q.id]: option }))}
              className="mt-1 shrink-0 accent-brand focus-visible:outline-2 focus-visible:outline-brand" />
            <span>{String.fromCharCode(65+index)}. {option}</span>
          </label>)}</div>
        </fieldset> : matching ? <>
          <p className="leading-relaxed">{i+1}. {q.question}</p>
          <div className="mt-3 grid min-w-0 gap-4 sm:grid-cols-2">
            <div className="min-w-0"><h3 className="text-xs uppercase text-ink-soft">Column A</h3>{q.leftItems.map(left => <label key={left.id} className="mt-3 block break-words text-sm">
              {left.text}<select aria-label={`Match for ${left.text}`} className={control} disabled={checked[q.id]}
                value={matches[q.id]?.[left.id] || ''} onChange={e => { const value = e.currentTarget.value; setMatches(current => ({ ...current, [q.id]: { ...current[q.id], [left.id]: value } })) }}>
                <option value="">Select match</option>{q.rightItems.map((right, index) => <option key={right.id} value={right.id}>{String.fromCharCode(65+index)}. {right.text}</option>)}
              </select>
            </label>)}</div>
            <div className="min-w-0"><h3 className="text-xs uppercase text-ink-soft">Column B</h3><ol className="mt-3 space-y-3 text-sm">{q.rightItems.map((right, index) => <li key={right.id} className="break-words">{String.fromCharCode(65+index)}. {right.text}</li>)}</ol></div>
          </div>
        </> : <>
          <label htmlFor={q.id} className="block leading-relaxed">{i+1}. {q.question}</label>
          {q.type === 'true_false' ? <select id={q.id} className={control} value={answers[q.id] || ''} disabled={checked[q.id]} onChange={e => { const value = e.currentTarget.value; setAnswers(current => ({ ...current, [q.id]: value })) }}><option value="">Choose True or False</option><option>True</option><option>False</option></select>
            : <input id={q.id} className={control} value={answers[q.id] || ''} disabled={checked[q.id] || busy[q.id]} maxLength={500}
              onChange={e => { const value = e.currentTarget.value; setAnswers(current => ({ ...current, [q.id]: value })) }}
              onKeyDown={e => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) { e.preventDefault(); void submitCloze(q.id) } }} autoComplete="off" />}
        </>}
        <button className={toolButton} disabled={!ready || checked[q.id] || busy[q.id]}
          onClick={() => q.type === 'fill_blank' ? void submitCloze(q.id) : setChecked(current => ({ ...current, [q.id]: true }))}>{busy[q.id] ? 'Checking…' : 'Check answer'}</button>
        {errors[q.id] && <div role="alert" className="mt-3 text-sm"><p>{errors[q.id]}</p><button className={toolButton + ' mt-2'} disabled={busy[q.id]} onClick={() => void submitCloze(q.id)}>Retry checking</button></div>}
        {checked[q.id] && <div role="status" aria-live="polite">
          {matching ? <>
            <p className="mt-2 font-medium">{pairsCorrect === q.leftItems.length ? 'Correct.' : `${pairsCorrect} / ${q.leftItems.length} pairs correct.`}</p>
            {pairsCorrect === q.leftItems.length && <p className="text-sm text-ink-soft">{pairsCorrect} / {q.leftItems.length} pairs correct.</p>}
            <ul className="mt-3 space-y-3">{q.leftItems.map(left => <li key={left.id} className="break-words text-sm">
              <p>{left.text} → {q.rightItems.find(right => right.id === q.correctMatches[left.id])?.text} {matches[q.id]?.[left.id] === q.correctMatches[left.id] ? '✓' : '(expected match)'}</p>
              {matches[q.id]?.[left.id] !== q.correctMatches[left.id] && <p className="mt-1 text-ink-soft">Your match: {q.rightItems.find(right => right.id === matches[q.id]?.[left.id])?.text}</p>}
              <blockquote className="mt-1">{left.sourceExcerpt}</blockquote><SourceLink source={left} onSource={onSource} />
            </li>)}</ul>
          </> : q.type === 'fill_blank' && grades[q.id] ? <>
            <p className="mt-2 font-medium">{grades[q.id].verdict === 'CORRECT' ? '✓ Correct' : grades[q.id].verdict === 'PARTIAL' ? '~ Partially correct' : '× Needs review'}</p>
            <p className="mt-2 break-words text-sm">Your answer: {answers[q.id]}</p>
            <p className="mt-1 break-words text-sm">{grades[q.id].verdict === 'CORRECT' ? 'Accepted answer' : 'Expected'}: {grades[q.id].canonical_answer}</p>
            <p className="mt-2 text-sm">{grades[q.id].feedback}</p>
          </> : <><p className="mt-2 font-medium">{q.type === 'mcq'
            ? (answers[q.id] === q.correctAnswer ? 'Correct.' : `Correct answer: ${q.correctAnswer}`)
            : (normalize(answers[q.id]) === normalize(q.correctAnswer) ? 'Correct.' : `Source answer: ${q.correctAnswer}`)}</p>
            <blockquote className="mt-2 break-words text-sm">{q.type === 'mcq' ? q.explanation || q.sourceExcerpt : q.sourceExcerpt}</blockquote></>}
          <SourceLink source={q} onSource={onSource} />
        </div>}
      </div>
    })}
    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2"><button className={toolButton + ' justify-self-start'} disabled={safeIndex === 0} onClick={() => setIndex(safeIndex - 1)}>← Previous</button><span className="text-xs text-ink-soft">{safeIndex + 1} / {questions.length}</span><button className={toolButton + ' justify-self-end'} disabled={safeIndex === questions.length - 1} onClick={() => setIndex(safeIndex + 1)}>Next →</button></div>
    <button className={toolButton} onClick={() => {
      const q = questions[safeIndex]
      if (q?.type === 'fill_blank') {
        requests.current.get(q.id)?.abort(); requests.current.delete(q.id)
        setAnswers(current => ({ ...current, [q.id]: '' })); setChecked(current => ({ ...current, [q.id]: false }))
        setGrades(current => { const next = { ...current }; delete next[q.id]; return next })
        setErrors(current => ({ ...current, [q.id]: '' })); setBusy(current => ({ ...current, [q.id]: false }))
      } else { requests.current.forEach(request => request.abort()); requests.current.clear(); setAnswers({}); setMatches({}); setChecked({}); setGrades({}); setErrors({}); setBusy({}); setIndex(0) }
    }}>Try again</button>
  </div>
}
