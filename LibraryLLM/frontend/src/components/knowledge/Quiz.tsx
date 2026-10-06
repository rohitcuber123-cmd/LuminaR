import { useState } from 'react'
import type { Question } from '../../lib/knowledgeArtifacts'
import { SourceLink } from './SourceLink'
import { toolButton } from './styles'

const control = 'my-3 w-full min-w-0 max-w-full border border-line bg-paper p-2 text-sm focus-visible:outline-2 focus-visible:outline-brand disabled:opacity-40'
// Preserve the existing fill-answer normalization and per-question checking.
const normalize = (value: string) => value.trim().toLowerCase().replace(/[^\p{L}\p{N}\s]/gu, '').replace(/\s+/g, ' ')

export function Quiz({ questions, onSource }: { questions: Question[]; onSource: (id: string) => void }) {
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [matches, setMatches] = useState<Record<string, Record<string, string>>>({})
  const [checked, setChecked] = useState<Record<string, boolean>>({})
  return <div className="space-y-4">
    <p className="text-sm text-ink-soft">Use the wording from the document. Answers are checked after you submit.</p>
    {questions.map((q, i) => {
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
            : <input id={q.id} className={control} value={answers[q.id] || ''} disabled={checked[q.id]} onChange={e => { const value = e.currentTarget.value; setAnswers(current => ({ ...current, [q.id]: value })) }} autoComplete="off" />}
        </>}
        <button className={toolButton} disabled={!ready || checked[q.id]} onClick={() => setChecked(current => ({ ...current, [q.id]: true }))}>Check answer</button>
        {checked[q.id] && <div role="status">
          {matching ? <>
            <p className="mt-2 font-medium">{pairsCorrect === q.leftItems.length ? 'Correct.' : `${pairsCorrect} / ${q.leftItems.length} pairs correct.`}</p>
            <ul className="mt-3 space-y-3">{q.leftItems.map(left => <li key={left.id} className="break-words text-sm">
              <p>{left.text} → {q.rightItems.find(right => right.id === q.correctMatches[left.id])?.text} {matches[q.id]?.[left.id] === q.correctMatches[left.id] ? '✓' : '(expected match)'}</p>
              <blockquote className="mt-1">{left.sourceExcerpt}</blockquote><SourceLink source={left} onSource={onSource} />
            </li>)}</ul>
          </> : <><p className="mt-2 font-medium">{q.type === 'mcq'
            ? (answers[q.id] === q.correctAnswer ? 'Correct.' : `Correct answer: ${q.correctAnswer}`)
            : (normalize(answers[q.id]) === normalize(q.correctAnswer) ? 'Correct.' : `Source answer: ${q.correctAnswer}`)}</p>
            <blockquote className="mt-2 break-words text-sm">{q.sourceExcerpt}</blockquote></>}
          <SourceLink source={q} onSource={onSource} />
        </div>}
      </div>
    })}
    <button className={toolButton} onClick={() => { setAnswers({}); setMatches({}); setChecked({}) }}>Try again</button>
  </div>
}
