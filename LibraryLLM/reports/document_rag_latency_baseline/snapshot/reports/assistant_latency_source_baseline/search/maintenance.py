"""Local administrator CLI. Never imported or exposed as a public API."""
import argparse
import json
from pathlib import Path

from search.sync_queue import SyncQueue, index_root


def main():
    from dotenv import load_dotenv
    load_dotenv()
    parser = argparse.ArgumentParser(description="LuminaR semantic-index maintenance")
    parser.add_argument("command", choices=["status", "sync", "rebuild", "worker"])
    parser.add_argument("work_ids", nargs="*")
    parser.add_argument("--index-dir", type=Path)
    parser.add_argument("--recover", action="store_true", help="Worker only: reconstruct when all snapshots are invalid")
    args = parser.parse_args()
    args.index_dir = args.index_dir or index_root()
    queue = SyncQueue(args.index_dir)
    if args.command == "status":
        output = queue.status()
        output["latest_requested_generation"] = queue.latest()
        pointer = args.index_dir / "active_index.json"
        if pointer.exists():
            version = json.loads(pointer.read_text())["version"]
            from search.index_manager import VERSION_PATTERN
            if not VERSION_PATTERN.fullmatch(version):
                raise ValueError("Invalid active version")
            output["manifest"] = json.loads((args.index_dir / "versions" / version / "manifest.json").read_text())
        print(json.dumps(output, indent=2))
    elif args.command in {"sync", "rebuild"}:
        if args.command == "sync" and not args.work_ids:
            parser.error("sync requires at least one work_id")
        seq = queue.request(args.work_ids, "rebuild" if args.command == "rebuild" else "sync")
        print(json.dumps({"requested_generation": seq, "status": "pending"}))
    else:
        import logging
        import os
        from pymongo import MongoClient
        from sentence_transformers import SentenceTransformer
        import torch
        from search.index_manager import IndexManager, MODEL
        logging.basicConfig(level=logging.INFO)
        client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
        model = SentenceTransformer(MODEL, device="cuda" if torch.cuda.is_available() else "cpu", local_files_only=True)
        model.max_seq_length = 256
        manager = IndexManager(args.index_dir, client[os.getenv("MONGO_DB_NAME", "luminar_library")].books,
                               model, legacy_dir=Path(__file__).resolve().parents[1] / "datasets/ai/embeddings",
                               recover=args.recover)
        manager.start()
        try:
            while not manager.stop_event.wait(1):
                pass
        except KeyboardInterrupt:
            manager.close()
            client.close()


if __name__ == "__main__":
    main()
