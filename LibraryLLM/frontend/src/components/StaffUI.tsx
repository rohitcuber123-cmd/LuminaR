import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { dateValue } from "../api/core";
import { scrollToContentAnchor } from "../lib/paginationScroll";

export function Badge({ children }: { children: ReactNode }) {
  return <span className="staff-badge">{children}</span>;
}
export function date(value?: string) {
  const time = dateValue(value);
  return Number.isNaN(time)
    ? "—"
    : new Date(time).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      });
}
export function Panel({
  title,
  tools,
  children,
}: {
  title: string;
  tools?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="staff-panel">
      <div className="staff-panel-head">
        <h2>{title}</h2>
        <div className="staff-tools">{tools}</div>
      </div>
      {children}
    </section>
  );
}
export function Stats({
  items,
}: {
  items: { label: string; value: ReactNode; note?: string }[];
}) {
  return (
    <div
      className="staff-stats"
      style={{ "--stat-count": items.length } as React.CSSProperties}
    >
      {items.map((item) => (
        <div className="staff-stat" key={item.label}>
          <h2>{item.label}</h2>
          <strong>{item.value}</strong>
          {item.note && <small>{item.note}</small>}
        </div>
      ))}
    </div>
  );
}
export function Table({
  headers,
  children,
  empty,
  count,
  label = 'Scrollable results',
  className = '',
  widths,
}: {
  headers: string[];
  children: ReactNode;
  empty: string;
  count: number;
  label?: string;
  className?: string;
  widths?: string[];
}) {
  return count ? (
    <div
      className="staff-table-wrap"
      tabIndex={0}
      role="region"
      aria-label={label}
    >
      <table className={`staff-table ${className}`} aria-label={label}>
        {widths && <colgroup>{widths.map((width, index) => <col key={index} style={{ width }} />)}</colgroup>}
        <thead>
          <tr>
            {headers.map((h) => (
              <th key={h} scope="col">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  ) : (
    <p className="staff-empty">{empty}</p>
  );
}
export function Pager({
  page,
  count,
  onChange,
  size = 20,
  label = 'Results pagination',
  anchorSelector = '.staff-table-wrap, .staff-activity-results, .institution-table, .institutions, .workspace-content',
}: {
  page: number;
  count: number;
  onChange: (page: number) => void;
  size?: number;
  label?: string;
  anchorSelector?: string;
}) {
  function go(next: number) {
    onChange(next)
    requestAnimationFrame(() => {
      scrollToContentAnchor(anchorSelector)
    })
  }
  return (
    <div className="staff-pager" role="navigation" aria-label={label}>
      <span>
        {count
          ? `${page * size + 1}–${Math.min((page + 1) * size, count)} of ${count}`
          : "0 results"}
      </span>
      <button disabled={page === 0} onClick={() => go(page - 1)}>
        Previous
      </button>
      <button
        disabled={(page + 1) * size >= count}
        onClick={() => go(page + 1)}
      >
        Next
      </button>
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
  busy = false,
  className = '',
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  busy?: boolean;
  className?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [closing, setClosing] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const closeRequested = useRef(false);
  function requestClose() {
    if (busy || closeRequested.current) return;
    closeRequested.current = true;
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
    if (reduced || !ref.current?.animate) { onClose(); return; }
    setClosing(true);
    closeTimer.current = setTimeout(onClose, className.includes('workspace-nav-dialog') ? 160 : 120);
  }
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    const dialog = ref.current;
    dialog?.showModal();
    dialog?.querySelector<HTMLElement>('[data-autofocus]')?.focus();
    return () => {
      clearTimeout(closeTimer.current);
      dialog?.close();
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={`staff-dialog ui-dialog ${className}${closing ? ' is-closing' : ''}`}
      aria-labelledby={titleId}
      aria-modal="true"
      onKeyDown={e => {
        if (e.key === 'Escape') { e.preventDefault(); requestClose(); }
        if(e.key === 'Tab') {
          const focusable=[...e.currentTarget.querySelectorAll<HTMLElement>('button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])')].filter(element=>element.getClientRects().length>0)
          const first=focusable[0],last=focusable.at(-1)
          if(first && (e.shiftKey && document.activeElement===first || !e.shiftKey && document.activeElement===last)) {
            e.preventDefault();(e.shiftKey?last:first)?.focus()
          }
        }
      }}
      onClick={e => {
        if (e.target !== e.currentTarget || busy) return;
        const bounds = e.currentTarget.getBoundingClientRect();
        if (e.clientX < bounds.left || e.clientX > bounds.right || e.clientY < bounds.top || e.clientY > bounds.bottom) requestClose();
      }}
      onCancel={(e) => {
        e.preventDefault();
        requestClose();
      }}
    >
      <header role="presentation">
        <h2 id={titleId}>{title}</h2>
        <button type="button" className="ui-dialog-close" aria-label="Close dialog" disabled={busy || closing} onClick={requestClose}>
          ×
        </button>
      </header>
      <div className="ui-dialog-body">{children}</div>
    </dialog>
  );
}
export function Details({
  value,
  onClose,
}: {
  value: { title: string; data: unknown };
  onClose: () => void;
}) {
  return (
    <Modal title={value.title} onClose={onClose}>
      <dl className="staff-details">
        {Object.entries(value.data as object).map(([k, v]) => (
          <div key={k}>
            <dt>{k.replaceAll("_", " ")}</dt>
            <dd>
              {v == null
                ? "—"
                : typeof v === "object"
                  ? JSON.stringify(v, null, 2)
                  : String(v)}
            </dd>
          </div>
        ))}
      </dl>
    </Modal>
  );
}
export function useAction(refresh: () => void) {
  const [busy, setBusy] = useState(false),
    [feedback, setFeedback] = useState<{ error: boolean; text: string } | null>(
      null,
    );
  const lock = useRef(false);
  async function run(action: () => Promise<unknown>, message: string) {
    if (lock.current) return false;
    lock.current = true;
    setBusy(true);
    setFeedback(null);
    try {
      await action();
      setFeedback({ error: false, text: message });
      refresh();
      return true;
    } catch (e) {
      setFeedback({
        error: true,
        text: e instanceof Error ? e.message : "Request failed.",
      });
      return false;
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return { busy, run, feedback, setFeedback };
}
export function Feedback({
  value,
}: {
  value: { error: boolean; text: string } | null;
}) {
  return (
    value && (
      <div
        className={`staff-feedback ${value.error ? "is-error" : ""}`}
        role={value.error ? "alert" : "status"}
      >
        {value.text}
      </div>
    )
  );
}
