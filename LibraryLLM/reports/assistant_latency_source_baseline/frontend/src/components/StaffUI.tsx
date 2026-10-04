import { useEffect, useRef, useState, type ReactNode } from "react";
import { dateValue } from "../api/core";

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
}: {
  headers: string[];
  children: ReactNode;
  empty: string;
  count: number;
}) {
  return count ? (
    <div
      className="staff-table-wrap"
      tabIndex={0}
      aria-label="Scrollable results"
    >
      <table className="staff-table">
        <thead>
          <tr>
            {headers.map((h) => (
              <th key={h}>{h}</th>
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
}: {
  page: number;
  count: number;
  onChange: (page: number) => void;
  size?: number;
}) {
  return (
    <div className="staff-pager">
      <span>
        {count
          ? `${page * size + 1}–${Math.min((page + 1) * size, count)} of ${count}`
          : "0 results"}
      </span>
      <button disabled={page === 0} onClick={() => onChange(page - 1)}>
        Previous
      </button>
      <button
        disabled={(page + 1) * size >= count}
        onClick={() => onChange(page + 1)}
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
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  busy?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    const dialog = ref.current;
    dialog?.showModal();
    return () => {
      dialog?.close();
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className="staff-dialog"
      aria-label={title}
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onClose();
      }}
    >
      <header>
        <h2>{title}</h2>
        <button aria-label="Close dialog" disabled={busy} onClick={onClose}>
          ×
        </button>
      </header>
      {children}
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
