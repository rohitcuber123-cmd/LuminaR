import { useRef, useState, type FormEvent } from "react";
import {
  confirmImport,
  mutate,
  previewImport,
  segment,
  type ImportPreview,
  type ImportResult,
  type Inventory,
} from "../api/core";
import type { BackendBook } from "../lib/api";
import {
  Badge,
  Feedback,
  Modal,
  Pager,
  Panel,
  Table,
  useAction,
} from "../components/StaffUI";

export function Editor({
  kind,
  item,
  library,
  close,
  refresh,
}: {
  kind: "inventory" | "book";
  item?: Inventory | BackendBook;
  library: string;
  close: () => void;
  refresh: () => void;
}) {
  const { busy, feedback, run } = useAction(refresh);
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const data: Record<string, unknown> = Object.fromEntries(form);
    for (const key of ["total_copies", "available_copies"])
      if (key in data) data[key] = Number(data[key]);
    if (Number(data.available_copies) > Number(data.total_copies)) {
      e.currentTarget
        .querySelector<HTMLInputElement>("[name=available_copies]")
        ?.setCustomValidity("Available copies cannot exceed total copies.");
      e.currentTarget.reportValidity();
      return;
    }
    const work = item?.work_id || String(data.work_id).trim();
    if (!item) data.work_id = work;
    if (kind === "inventory") {
      if (!item) data.library_id = library;
    }
    if (item) delete data.work_id;
    const path =
      kind === "book"
        ? `/books/${item ? segment(work) : ""}`
        : `/inventory/${item ? `${segment(library)}/${segment(work)}` : ""}`;
    if (
      await run(
        () => mutate(path, item ? "PUT" : "POST", data),
        `${kind === "book" ? "Book" : "Inventory"} saved successfully.`,
      )
    )
      close();
  }
  const book = item as BackendBook | undefined;
  return (
    <Modal
      title={`${item ? "Edit" : "Add"} ${kind === "book" ? "book metadata" : "inventory"}`}
      onClose={close}
      busy={busy}
    >
      <p className="mb-5">
        {kind === "inventory"
          ? `Physical copies in library ${library}. Use a work ID from the catalogue.`
          : "Catalogue metadata and catalogue copies. Physical library inventory is managed separately."}
      </p>
      <Feedback value={feedback} />
      <form onSubmit={save} className="staff-form">
        {!item && (
          <label className="wide">
            Work ID
            <input name="work_id" required placeholder="OL123456W" />
          </label>
        )}
        {kind === "book" && (
          <>
            <label className="wide">
              Title
              <input name="title" required defaultValue={book?.title} />
            </label>
            <label>
              Authors
              <input name="authors" defaultValue={book?.authors || ""} />
            </label>
            <label>
              Category / subjects
              <input name="subjects" defaultValue={book?.subjects || ""} />
            </label>
            <label className="wide">
              Description
              <textarea
                name="description"
                rows={3}
                defaultValue={book?.description || ""}
              />
            </label>
          </>
        )}
        {kind === "inventory" && (
          <label className="wide">
            ISBN
            <input name="isbn" defaultValue={(item as Inventory)?.isbn || ""} />
          </label>
        )}
        {(kind === "inventory" || !item) && (
          <>
            <label>
              Total copies
              <input
                type="number"
                min="1"
                step="1"
                name="total_copies"
                onInput={(e) => e.currentTarget.form?.querySelector<HTMLInputElement>('[name="available_copies"]')?.setCustomValidity("")}
                required
                defaultValue={item?.total_copies ?? 1}
              />
            </label>
            <label>
              Available copies
              <input
                type="number"
                min="0"
                step="1"
                name="available_copies"
                required
                defaultValue={item?.available_copies ?? 1}
                onInput={(e) => e.currentTarget.setCustomValidity("")}
              />
            </label>
          </>
        )}
        <label className="wide">
          Shelf location
          <input
            name="shelf_location"
            defaultValue={item?.shelf_location || ""}
          />
        </label>
        <footer>
          <button type="button" disabled={busy} onClick={close}>
            Cancel
          </button>
          <button className="staff-primary" disabled={busy}>
            {busy ? "Saving…" : "Save changes"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}

export function DatasetImport({
  library,
  refresh,
}: {
  library: string;
  refresh: () => void;
}) {
  const [file, setFile] = useState<File | null>(null),
    [preview, setPreview] = useState<ImportPreview | null>(null),
    [result, setResult] = useState<ImportResult | null>(null);
  const [page, setPage] = useState(0),
    [filter, setFilter] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const { busy, run, feedback, setFeedback } = useAction(() => {});
  function select(file?: File) {
    setPreview(null);
    setResult(null);
    setPage(0);
    setFilter("");
    setFile(null);
    setFeedback(null);
    if (!file) return;
    if (
      !/\.(csv|xlsx)$/i.test(file.name) ||
      file.size > 25 * 1024 * 1024 ||
      file.size === 0
    ) {
      setFeedback({
        error: true,
        text: "Choose a non-empty CSV or XLSX file up to 25 MB.",
      });
      if (input.current) input.current.value = "";
      return;
    }
    setFile(file);
  }
  const rows =
    preview?.rows.filter((r) => !filter || r.status === filter) || [];
  return (
    <Panel title="Dataset import">
      <div className="staff-upload">
        <h3>Import books into library inventory.</h3>
        <p className="mt-3">
          Required columns:{" "}
          <strong>isbn, total_copies, available_copies</strong>
        </p>
        <p className="mt-2">
          Optional: title, author, shelf_location. Only exact ISBN matches are
          imported.
        </p>
        <div
          className="staff-drop"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            if (!busy) select(e.dataTransfer.files[0]);
          }}
        >
          <strong>Drop a CSV or XLSX file here</strong>
          <label htmlFor="dataset-file">Choose dataset · maximum 25 MB</label>
          <input
            ref={input}
            id="dataset-file"
            type="file"
            accept=".csv,.xlsx"
            disabled={busy}
            onChange={(e) => select(e.target.files?.[0])}
          />
          {file && (
            <span>
              Selected: {file.name} · {(file.size / 1024).toFixed(1)} KB
            </span>
          )}
        </div>
        <button
          className="staff-primary"
          disabled={!file || busy}
          onClick={() => {
            setPreview(null);
            setResult(null);
            void run(async () => {
              const p = await previewImport(library, file!);
              setPreview(p);
              setPage(0);
            }, "Dataset preview ready. Review the rows before confirming.");
          }}
        >
          {busy ? "Processing…" : "Preview dataset"}
        </button>
        <Feedback value={feedback} />
        {preview && (
          <>
            <h3 className="mt-6">
              Preview: {preview.filename} · Library {preview.library_id}
            </h3>
            <div className="staff-summary">
              {Object.entries(preview.summary).map(([k, v]) => (
                <span key={k}>
                  {k.replaceAll("_", " ")}: <strong>{v}</strong>
                </span>
              ))}
            </div>
            <label>
              Filter validation results
              <select
                value={filter}
                onChange={(e) => {
                  setFilter(e.target.value);
                  setPage(0);
                }}
              >
                <option value="">All rows</option>
                {["MATCHED", "INVALID", "NOT_FOUND", "AMBIGUOUS", "EXISTS"].map(
                  (s) => (
                    <option key={s}>{s}</option>
                  ),
                )}
              </select>
            </label>
            <Table
              headers={["Row", "ISBN", "Book", "Copies", "Status", "Detail"]}
              count={rows.length}
              empty="No rows match this filter."
            >
              {rows.slice(page * 20, page * 20 + 20).map((r, i) => (
                <tr key={i}>
                  <td>{r.row_number ?? page * 20 + i + 1}</td>
                  <td>{r.isbn || "—"}</td>
                  <td>{r.catalogue_title || r.title || r.work_id || "—"}</td>
                  <td>
                    {r.available_copies ?? "—"} / {r.total_copies ?? "—"}
                  </td>
                  <td>
                    <Badge>{r.status.replaceAll("_", " ")}</Badge>
                  </td>
                  <td>
                    {r.reason}
                    {r.candidates && (
                      <details>
                        <summary>View candidates</summary>
                        <pre>{JSON.stringify(r.candidates, null, 2)}</pre>
                      </details>
                    )}
                  </td>
                </tr>
              ))}
            </Table>
            <Pager page={page} count={rows.length} onChange={setPage} />
            <p className="my-4">
              Confirm to add matched rows. Existing, invalid, ambiguous and
              unmatched rows will be skipped.
            </p>
            <button
              className="staff-primary"
              disabled={busy || !preview.summary.matched}
              onClick={() =>
                void run(async () => {
                  const summary = await confirmImport(preview);
                  setResult(summary);
                  setPreview(null);
                  setFile(null);
                  if (input.current) input.current.value = "";
                  refresh();
                }, "Import completed. Review the summary below.")
              }
            >
              Confirm import
            </button>
          </>
        )}
        {result && (
          <section aria-label="Import summary">
            <h3 className="mt-6">Import completed</h3>
            <div className="staff-summary">
              {Object.entries(result)
                .filter(([, v]) => typeof v === "number")
                .map(([k, v]) => (
                  <span key={k}>
                    {k.replaceAll("_", " ")}: <strong>{String(v)}</strong>
                  </span>
                ))}
            </div>
            {result.errors?.map((e, i) => (
              <p role="alert" key={i}>
                {e.work_id}: {e.error}
              </p>
            ))}
          </section>
        )}
      </div>
    </Panel>
  );
}
