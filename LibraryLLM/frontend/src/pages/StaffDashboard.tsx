import { lazy, Suspense, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuthStore } from "../store/useAuthStore";
import {
  api,
  activeReservation,
  getInventory,
  mutate,
  overdue,
  segment,
  type Inventory,
  type RecordItem,
} from "../api/core";
import type { BackendBook } from "../lib/api";
import {
  Badge,
  date,
  Details,
  Feedback,
  Modal,
  Pager,
  Panel,
  Stats,
  Table,
  useAction,
} from "../components/StaffUI";
import { DatasetImport, Editor } from "./StaffForms";
import { StaffManagement } from './StaffManagement';
const AdminOperations = lazy(() => import('./AdminOperations').then(m => ({ default: m.AdminOperations })));
const AdminNotifications = lazy(() => import('./AdminOperations').then(m => ({ default: m.AdminNotifications })));
import "./Staff.css";

type Data = {
  summary?: { users: number; books: number; librarians: number; active_loans: number; reservations: number; unpaid: number };
  issues: RecordItem[];
  reservations: RecordItem[];
  fines: RecordItem[];
  activities: RecordItem[];
  inventory: Inventory[];
  bookCount: number;
  unpaid: number;
};
function recordId(tab: string, record: RecordItem) {
  switch (tab) {
    case "Issues": return record.issue_id;
    case "Reservations": return record.reservation_id;
    case "Fines": return record.fine_id;
    case "Activity": return record.activity_id;
  }
}
const INITIAL: Data = {
  issues: [],
  reservations: [],
  fines: [],
  activities: [],
  inventory: [],
  bookCount: 0,
  unpaid: 0,
};
export function StaffDashboard({ admin = false }: { admin?: boolean }) {
  const user = useAuthStore((s) => s.user)!;
  const [params, setParams] = useSearchParams();
  const tabs = admin
    ? ["Operations", "Notifications", "Staff Management", "Books"]
    : [
        "Books",
        "Issues",
        "Reservations",
        "Inventory",
        "Dataset import",
        "Fines",
        "Activity",
      ];
  const selected = params.get("tab") || tabs[0];
  const tab = tabs.includes(selected) ? selected : tabs[0];
  const [revision, setRevision] = useState(0),
    [data, setData] = useState<Data>(INITIAL);
  const [staffCount, setStaffCount] = useState<number | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({}),
    [loading, setLoading] = useState(true);
  const [library, setLibrary] = useState(
    import.meta.env.VITE_LIBRARY_ID || "LIB001",
  );
  const [libraryDraft, setLibraryDraft] = useState(library);
  const [query, setQuery] = useState(""),
    [status, setStatus] = useState(""),
    [onlyOverdue, setOnlyOverdue] = useState(false),
    [page, setPage] = useState(0);
  const [books, setBooks] = useState<BackendBook[]>([]),
    [bookPage, setBookPage] = useState(0),
    [booksLoading, setBooksLoading] = useState(false);
  const [editor, setEditor] = useState<{
    kind: "book" | "inventory";
    item?: BackendBook | Inventory;
  } | null>(null);
  const [details, setDetails] = useState<{
    title: string;
    data: unknown;
  } | null>(null);
  const [confirm, setConfirm] = useState<{
    title: string;
    action: () => Promise<unknown>;
    message: string;
  } | null>(null);
  const refresh = () => setRevision((v) => v + 1);
  const { busy, feedback, run, setFeedback } = useAction(refresh);
  useEffect(() => {
    setQuery("");
    setStatus("");
    setPage(0);
    setBookPage(0);
    setFeedback(null);
  }, [tab, setFeedback]);
  useEffect(() => {
    const controller = new AbortController();
    let alive = true;
    setLoading(true);
    setErrors({});
    setData(INITIAL);
    const load = async (key: string, request: Promise<Partial<Data>>) => {
      try {
        const value = await request;
        if (alive) setData((d) => ({ ...d, ...value }));
      } catch (e) {
        if (alive)
          setErrors((old) => ({
            ...old,
            [key]: e instanceof Error ? e.message : "Unable to load data.",
          }));
      }
    };
    const options = { signal: controller.signal };
    void Promise.all(admin ? [load('summary', api<NonNullable<Data['summary']>>('/admin/summary', options).then(summary => ({ summary })))] : [
      load(
        "issues",
        api<{ issues: RecordItem[] }>("/issues/all", options).then((r) => ({
          issues: r.issues,
        })),
      ),
      load(
        "reservations",
        api<{ reservations: RecordItem[] }>("/reservations/all", options).then(
          (r) => ({ reservations: r.reservations }),
        ),
      ),
      load(
        "fines",
        api<{ fines: RecordItem[]; total_unpaid: number }>(
          "/fines/all",
          options,
        ).then((r) => ({ fines: r.fines, unpaid: r.total_unpaid })),
      ),
      admin
        ? load(
            "books",
            api<{ count: number }>("/books/?limit=1", options).then((r) => ({
              bookCount: r.count,
            })),
          )
        : load(
            "inventory",
            getInventory(library, controller.signal).then((inventory) => ({
              inventory,
            })),
          ),
      ...(!admin
        ? [
            load(
              "activity",
              api<{ activities: RecordItem[] }>("/activity/all", options).then(
                (r) => ({ activities: r.activities }),
              ),
            ),
          ]
        : []),
    ]).finally(() => {
      if (alive) setLoading(false);
    });
    return () => {
      alive = false;
      controller.abort();
    };
  }, [revision, library, admin]);
  useEffect(() => {
    if (tab !== "Books") return;
    const controller = new AbortController();
    setBooksLoading(true);
    api<{ results: BackendBook[]; count: number }>(
      `/books/?limit=20&offset=${bookPage * 20}`,
      { signal: controller.signal },
    )
      .then((r) => {
        setBooks(r.results);
        setData((d) => ({ ...d, bookCount: r.count }));
        setErrors((e) => {
          const copy = { ...e };
          delete copy.books;
          return copy;
        });
      })
      .catch((e) => {
        if (!controller.signal.aborted) {
          setBooks([]);
          setErrors((old) => ({ ...old, books: e.message }));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setBooksLoading(false);
      });
    return () => controller.abort();
  }, [tab, bookPage, revision]);
  const activeIssues = data.issues.filter((r) => r.status === "ISSUED");
  const metric = (key: string, value: number) =>
    loading ? "…" : errors[key] ? "—" : value.toLocaleString();
  const stats = admin
    ? [
        { label: "Total users", value: metric("summary", data.summary?.users ?? 0) },
        { label: "Total books", value: metric("summary", data.summary?.books ?? 0) },
        { label: "Librarians", value: staffCount ?? metric("summary", data.summary?.librarians ?? 0) },
        {
          label: "Active issues",
          value: metric("summary", data.summary?.active_loans ?? 0),
        },
        {
          label: "Reservations",
          value: metric(
            "summary",
            data.summary?.reservations ?? 0,
          ),
        },
        {
          label: "Outstanding fines",
          value: metric("summary", data.summary?.unpaid ?? 0),
          note: "Unpaid total (INR)",
        },
      ]
    : [
        {
          label: "Active issues",
          value: metric("issues", activeIssues.length),
          note: "All library loans",
        },
        {
          label: "Reservations",
          value: metric(
            "reservations",
            data.reservations.filter(activeReservation).length,
          ),
        },
        {
          label: "Available inventory",
          value: metric(
            "inventory",
            data.inventory.filter((r) => r.available_copies > 0).length,
          ),
          note: `Titles with a free copy · ${library}`,
        },
        {
          label: "Overdue books",
          value: metric("issues", data.issues.filter(overdue).length),
        },
      ];
  const matches = (values: unknown[]) =>
    values.join(" ").toLowerCase().includes(query.toLowerCase());
  const recordSource =
    tab === "Issues"
      ? data.issues
      : tab === "Reservations"
        ? data.reservations
        : tab === "Fines"
          ? data.fines
          : data.activities;
  const records = recordSource.filter(
    (r) =>
      matches([
        r.user_id,
        r.title,
        r.work_id,
        r.description,
        r.activity_type,
      ]) &&
      (!status || r.status === status) &&
      (tab !== "Issues" ||
        (onlyOverdue ? overdue(r) : status ? true : r.status === "ISSUED")),
  );
  const inventory = data.inventory.filter(
    (r) =>
      matches([r.title, r.authors, r.work_id, r.isbn]) &&
      (!status ||
        (status === "available"
          ? r.available_copies > 0
          : r.available_copies === 0)),
  );
  const visibleBooks = books.filter((r) => matches([r.title, r.authors]));
  function view(path: string, title: string) {
    void run(async () => {
      setDetails({ title, data: await api(path) });
    }, "Details loaded.");
  }
  function ask(title: string, path: string, method: string, message: string) {
    setConfirm({ title, action: () => mutate(path, method), message });
  }
  const owner = (r: RecordItem) =>
    r.user_id === Number(user.user_id ?? user.id);
  const actionsDisabled = busy || loading;
  const search = (
    <input
      aria-label={
        tab === "Inventory"
          ? "Search title, author, ISBN"
          : "Search current results"
      }
      placeholder={
        tab === "Inventory"
          ? "Search title, author, ISBN"
          : "Search user or book"
      }
      value={query}
      onChange={(e) => {
        setQuery(e.target.value);
        setPage(0);
      }}
    />
  );
  const filter = (
    <select
      aria-label="Filter status"
      value={status}
      onChange={(e) => {
        setStatus(e.target.value);
        setPage(0);
      }}
    >
      <option value="">
        {tab === "Issues" ? "Active loans" : "All statuses"}
      </option>
      {[...new Set(recordSource.map((r) => r.status).filter(Boolean))].map(
        (s) => (
          <option key={s}>{s}</option>
        ),
      )}
    </select>
  );
  return (
    <div className="staff">
      <div className="staff-heading">
        <p className="staff-eyebrow">{admin ? "Administrator" : "Librarian"}</p>
        <h1>{admin ? "Admin dashboard" : "Librarian dashboard"}</h1>
        <p>
          Signed in as {user.email}.{" "}
          {admin
            ? "Full system administration and oversight."
            : "Day-to-day circulation and catalogue operations."}
        </p>
      </div>
      <Stats items={stats} />
      {admin ? (
        <p>
          Circulation tools — issues, reservations, inventory, dataset import,
          fines and activity — are on the{" "}
          <Link to="/librarian">Librarian dashboard</Link>, which Admins can
          also open.
        </p>
      ) : (
        <form
          className="staff-library"
          onSubmit={(e) => {
            e.preventDefault();
            if (libraryDraft.trim()) {
              setLibrary(libraryDraft.trim());
              setPage(0);
            }
          }}
        >
          <label htmlFor="library-id">Library ID</label>
          <input
            id="library-id"
            value={libraryDraft}
            onChange={(e) => setLibraryDraft(e.target.value)}
            required
            disabled={busy}
          />
          <button disabled={busy || loading}>Apply</button>
        </form>
      )}
      {Object.entries(errors).map(([key, message]) => (
        <div className="staff-feedback is-error" role="alert" key={key}>
          Unable to load {key}: {message}{" "}
          <button onClick={refresh}>Retry</button>
        </div>
      ))}
      <Feedback value={feedback} />
      <div
        className="staff-tabs"
        role="tablist"
        aria-label="Dashboard sections"
      >
        {tabs.map((t) => (
          <button
            key={t}
            id={`tab-${t}`}
            role="tab"
            aria-controls="staff-content"
            aria-selected={tab === t}
            onClick={() => setParams({ tab: t })}
          >
            {t}
          </button>
        ))}
      </div>
      <div id="staff-content" role="tabpanel" aria-labelledby={`tab-${tab}`}>
        {tab === 'Staff Management' && <StaffManagement onCount={setStaffCount} />}
        {admin && tab === 'Operations' && <Suspense fallback={<p role="status">Loading operations…</p>}><AdminOperations /></Suspense>}
        {admin && tab === 'Notifications' && <Suspense fallback={<p role="status">Loading notifications…</p>}><AdminNotifications /></Suspense>}
        {tab === "Dataset import" && (
          <DatasetImport key={library} library={library} refresh={refresh} />
        )}
        {tab === "Books" && (
          <Panel
            title="Catalogue"
            tools={
              <>
                <input
                  aria-label="Search title or author on this page"
                  placeholder="Search title or author on this page"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                <button
                  className="staff-primary"
                  onClick={() => setEditor({ kind: "book" })}
                >
                  + Add book
                </button>
              </>
            }
          >
            <p className="staff-note">
              Book metadata and catalogue copies. Physical copies are managed in
              Inventory. Search filters this page; use pagination to browse the
              catalogue, or <Link to="/search">open global semantic search</Link>.
            </p>
            {booksLoading ? (
              <p className="staff-empty" role="status">
                Loading books…
              </p>
            ) : (
              !errors.books && (
                <>
                  <Table
                    headers={[
                      "Title",
                      "Author",
                      "Category",
                      "Available",
                      "Actions",
                    ]}
                    count={visibleBooks.length}
                    empty="No books found on this page."
                  >
                    {visibleBooks.map((b) => (
                      <tr key={b.work_id}>
                        <td>
                          <Link to={`/book/${segment(b.work_id)}`}>
                            {b.title}
                          </Link>
                          <small>{b.work_id}</small>
                        </td>
                        <td>{b.authors || "—"}</td>
                        <td>{b.subjects?.split(/[,|]/)[0] || "—"}</td>
                        <td>
                          {b.available_copies} / {b.total_copies}
                        </td>
                        <td>
                          <button
                            disabled={actionsDisabled}
                            onClick={() => setEditor({ kind: "book", item: b })}
                          >
                            Edit
                          </button>
                          {user.role === "ADMIN" && <button
                            disabled={actionsDisabled}
                            onClick={() =>
                              ask(
                                `Delete “${b.title}”?`,
                                `/books/${segment(b.work_id)}`,
                                "DELETE",
                                "Book deleted successfully.",
                              )
                            }
                          >
                            Delete
                          </button>}
                        </td>
                      </tr>
                    ))}
                  </Table>
                  <Pager
                    page={bookPage}
                    count={data.bookCount}
                    onChange={(p) => {
                      setBookPage(p);
                      setQuery("");
                    }}
                  />
                </>
              )
            )}
          </Panel>
        )}
        {tab === "Inventory" && (
          <Panel
            title="Inventory"
            tools={
              <>
                {search}
                <select
                  aria-label="Inventory availability"
                  value={status}
                  onChange={(e) => {
                    setStatus(e.target.value);
                    setPage(0);
                  }}
                >
                  <option value="">All availability</option>
                  <option value="available">Available</option>
                  <option value="unavailable">Out of stock</option>
                </select>
                <button
                  className="staff-primary"
                  disabled={loading}
                  onClick={() => setEditor({ kind: "inventory" })}
                >
                  + Add book
                </button>
              </>
            }
          >
            {loading ? (
              <p className="staff-empty" role="status">
                Loading inventory…
              </p>
            ) : (
              !errors.inventory && (
                <>
                  <Table
                    headers={[
                      "Book",
                      "Format",
                      "Shelf",
                      "Available",
                      "Total",
                      "Actions",
                    ]}
                    count={inventory.length}
                    empty={query || status ? "No inventory items match these filters." : "No physical copies are registered for this library. Add a catalogue work ID or import a dataset to stock this library."}
                  >
                    {inventory.slice(page * 20, page * 20 + 20).map((r) => (
                      <tr
                        key={r.work_id}
                        className={!r.available_copies ? "staff-low" : ""}
                      >
                        <td>
                          <Link to={`/book/${segment(r.work_id)}`}>
                            {r.title || r.work_id}
                          </Link>
                          <small>{r.authors || r.isbn || r.work_id}</small>
                        </td>
                        <td>Physical book</td>
                        <td>{r.shelf_location || "—"}</td>
                        <td>
                          {r.available_copies}
                          {r.available_copies <= 1 && (
                            <small>
                              {r.available_copies
                                ? "Low stock"
                                : "Out of stock"}
                            </small>
                          )}
                        </td>
                        <td>{r.total_copies}</td>
                        <td>
                          <button
                            disabled={busy}
                            onClick={() =>
                              setEditor({ kind: "inventory", item: r })
                            }
                          >
                            Edit
                          </button>
                          {user.role === "ADMIN" && (
                            <button
                              disabled={busy}
                              onClick={() =>
                                ask(
                                  "Delete this inventory item?",
                                  `/inventory/${segment(library)}/${segment(r.work_id)}`,
                                  "DELETE",
                                  "Inventory deleted successfully.",
                                )
                              }
                            >
                              Delete
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </Table>
                  <Pager
                    page={page}
                    count={inventory.length}
                    onChange={setPage}
                  />
                </>
              )
            )}
          </Panel>
        )}
        {["Issues", "Reservations", "Fines", "Activity"].includes(tab) && (
          <Panel
            title={
              tab === "Issues"
                ? "Active loans"
                : tab === "Activity"
                  ? "Library activity"
                  : tab
            }
            tools={
              <>
                {search}
                {tab !== "Activity" && filter}
                {tab === "Issues" && (
                  <button
                    aria-pressed={onlyOverdue}
                    onClick={() => {
                      setOnlyOverdue((v) => !v);
                      setPage(0);
                    }}
                  >
                    {onlyOverdue ? "Show all loans" : "Show overdue only"}
                  </button>
                )}
              </>
            }
          >
            {tab !== "Activity" && (
              <p className="staff-note">
                {tab === "Issues"
                  ? "This backend allows borrowers to return their own loans only."
                  : tab === "Fines"
                    ? "Only the fine owner can mark it as paid. This updates its status; no money is transferred."
                    : "Cancellation is available to the reservation owner only. Queue shows the next waiting reservation."}
              </p>
            )}
            {loading ? (
              <p className="staff-empty" role="status">
                Loading {tab.toLowerCase()}…
              </p>
            ) : (
              !errors[tab.toLowerCase()] && (
                <>
                  <Table
                    headers={
                      tab === "Activity"
                        ? ["When", "Type", "Detail"]
                        : [
                            "User",
                            "Book",
                            tab === "Fines" ? "Amount (INR)" : "Date",
                            ...(tab === "Issues" ? ["Due date"] : []),
                            "Status",
                            "Actions",
                          ]
                    }
                    count={records.length}
                    empty={
                      tab === "Issues"
                        ? query || status || onlyOverdue ? "No loans match these filters." : "No active loans."
                        : `No ${tab.toLowerCase()} records found.`
                    }
                  >
                    {records.slice(page * 20, page * 20 + 20).map((r, i) => (
                      <tr
                        key={String(
                          recordId(tab, r) ?? i,
                        )}
                      >
                        {tab === "Activity" ? (
                          <>
                            <td>{date(r.created_at)}</td>
                            <td>
                              <Badge>
                                {r.activity_type?.replaceAll("_", " ")}
                              </Badge>
                            </td>
                            <td style={{ whiteSpace: "normal", minWidth: 240 }}>
                              {r.description}
                            </td>
                          </>
                        ) : (
                          <>
                            <td>User #{r.user_id}</td>
                            <td>{r.title || r.work_id}</td>
                            <td>
                              {tab === "Fines"
                                ? r.amount
                                : date(r.issued_at || r.reserved_at)}
                              {tab === "Fines" && (
                                <small>{date(r.created_at)}</small>
                              )}
                            </td>
                            {tab === "Issues" && <td>{date(r.due_date)}</td>}
                            <td>
                              <Badge>
                                {overdue(r)
                                  ? "OVERDUE"
                                  : r.status.replaceAll("_", " ")}
                              </Badge>
                            </td>
                            <td>
                              <button
                                disabled={busy}
                                onClick={() =>
                                  view(
                                    `/${tab.toLowerCase()}/${recordId(tab, r)}`,
                                    `${tab} details`,
                                  )
                                }
                              >
                                View
                              </button>
                              {tab === "Issues" &&
                                r.status === "ISSUED" &&
                                owner(r) && (
                                  <button
                                    disabled={busy}
                                    onClick={() =>
                                      ask(
                                        "Return this book?",
                                        `/issues/return/${r.issue_id}`,
                                        "POST",
                                        "Book returned successfully.",
                                      )
                                    }
                                  >
                                    Return
                                  </button>
                                )}
                              {tab === "Reservations" && (
                                <>
                                  <button
                                    disabled={busy}
                                    onClick={() =>
                                      view(
                                        `/reservations/queue/${segment(r.work_id)}`,
                                        "Next reservation in queue",
                                      )
                                    }
                                  >
                                    Queue
                                  </button>
                                  {activeReservation(r) && owner(r) && (
                                    <button
                                      disabled={busy}
                                      onClick={() =>
                                        ask(
                                          "Cancel this reservation?",
                                          `/reservations/cancel/${r.reservation_id}`,
                                          "POST",
                                          "Reservation cancelled successfully.",
                                        )
                                      }
                                    >
                                      Cancel
                                    </button>
                                  )}
                                </>
                              )}
                              {tab === "Fines" &&
                                r.status === "UNPAID" &&
                                owner(r) && (
                                  <button
                                    disabled={busy}
                                    onClick={() =>
                                      ask(
                                        "Mark this fine as paid?",
                                        `/fines/pay/${r.fine_id}`,
                                        "POST",
                                        "Fine marked as paid.",
                                      )
                                    }
                                  >
                                    Mark as paid
                                  </button>
                                )}
                            </td>
                          </>
                        )}
                      </tr>
                    ))}
                  </Table>
                  <Pager
                    page={page}
                    count={records.length}
                    onChange={setPage}
                  />
                </>
              )
            )}
          </Panel>
        )}
      </div>
      {editor && (
        <Editor
          {...editor}
          library={library}
          close={() => setEditor(null)}
          refresh={() => {
            refresh();
            setFeedback({ error: false, text: "Changes saved successfully." });
          }}
        />
      )}
      {details && <Details value={details} onClose={() => setDetails(null)} />}
      {confirm && (
        <Modal
          title={confirm.title}
          busy={busy}
          onClose={() => setConfirm(null)}
        >
          <p>Confirm this action to continue. Deletions cannot be undone.</p>
          <Feedback value={feedback} />
          <div className="staff-confirm-actions">
            <button disabled={busy} onClick={() => setConfirm(null)}>
              Cancel
            </button>
            <button
              className="staff-primary"
              disabled={busy}
              onClick={async () => {
                if (await run(confirm.action, confirm.message))
                  setConfirm(null);
              }}
            >
              {busy ? "Processing…" : "Confirm"}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
