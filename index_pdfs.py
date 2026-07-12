#!/usr/bin/env python3
# index_pdfs.py
# Specialized fast indexer that updates or removes ONLY PDF service manuals in the RAG index
# without re-indexing or re-embedding forum posts.

import os
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import json
import argparse
import sqlite3
import numpy as np
import datetime
import shutil

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

import config
from preprocessing.importer import PDFImporter
from embeddings.factory import get_embeddings_provider
from vector_store.factory import get_vector_store

def check_pdf_changes():
    """
    Checks if there are any new PDFs in Service_manuals (which need to be moved and indexed),
    or if any PDFs in Archive/official were deleted/modified compared to the database.
    """
    manuals_dir = "Service_manuals"
    archive_dir = config.ARCHIVE_DIR
    official_dir = os.path.join(archive_dir, "official")
    
    # 1. Check if there are any new PDFs in Service_manuals
    if os.path.exists(manuals_dir):
        for f in os.listdir(manuals_dir):
            if f.lower().endswith(".pdf"):
                return True # New files to process
                
    # 2. Check if files in Archive/official differ from what is in the database
    is_anon_build = os.path.exists("Index_anon") and not os.path.exists("Index")
    index_dir = "Index_anon" if is_anon_build else config.INDEX_DIR
    db_path = os.path.join(index_dir, "knowledge_base.db")
    
    if not os.path.exists(db_path):
        return True
        
    db_pdfs = set()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT metadata_json FROM chunks WHERE source = 'official'")
        for row in cursor.fetchall():
            try:
                meta = json.loads(row[0])
                if "document" in meta:
                    db_pdfs.add(meta["document"])
            except Exception:
                pass
        conn.close()
    except Exception:
        pass
        
    current_official_pdfs = set()
    if os.path.exists(official_dir):
        for f in os.listdir(official_dir):
            if f.lower().endswith(".pdf"):
                current_official_pdfs.add(f)
                
    return db_pdfs != current_official_pdfs

def run_pdf_update(anonymize=False, provider=None, store=None):
    # Auto-detect anonymization directory in development workspace
    if not anonymize:
        if os.path.exists("Index_anon") and not os.path.exists("Index"):
            anonymize = True

    index_dir = "Index_anon" if anonymize else config.INDEX_DIR
    archive_dir = config.ARCHIVE_DIR
    db_path = os.path.join(index_dir, "knowledge_base.db")
    sync_path = os.path.join(index_dir, "sync_dates.json")

    print("="*60)
    print(f"Starting Fast PDF Index Update (anonymize={anonymize})")
    print(f"Index Directory: {index_dir}")
    print(f"Database Path:   {db_path}")
    print("="*60)

    # 1. Ensure target directory exists
    os.makedirs(index_dir, exist_ok=True)

    # 2. Open or create SQLite DB
    db_existed = os.path.exists(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables if database didn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chunks (
        chunk_id TEXT PRIMARY KEY,
        thread_id INTEGER,
        thread_title TEXT,
        url TEXT,
        chunk_index INTEGER,
        text TEXT,
        metadata_json TEXT,
        embedding BLOB,
        source TEXT,
        summary TEXT
    )
    """)
    cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS fts_chunks USING fts5(
        chunk_id UNINDEXED,
        thread_title,
        text
    )
    """)
    conn.commit()

    # 3. Read list of PDFs currently registered in DB
    db_pdfs = set()
    if db_existed:
        cursor.execute("SELECT DISTINCT metadata_json FROM chunks WHERE source = 'official'")
        for row in cursor.fetchall():
            try:
                meta = json.loads(row[0])
                if "document" in meta:
                    db_pdfs.add(meta["document"])
            except Exception:
                pass

    # 4. Move new PDF manuals from Service_manuals to Archive/official
    manuals_dir = "Service_manuals"
    official_dir = os.path.join(archive_dir, "official")
    os.makedirs(official_dir, exist_ok=True)
    os.makedirs(manuals_dir, exist_ok=True)

    new_files_moved = False
    for f in os.listdir(manuals_dir):
        if f.lower().endswith(".pdf"):
            src_file = os.path.join(manuals_dir, f)
            dst_file = os.path.join(official_dir, f)
            print(f"[+] Moving new manual: {f} -> Archive/official/")
            try:
                # Move the file (overwrites if destination already exists)
                if os.path.exists(dst_file):
                    os.remove(dst_file)
                shutil.move(src_file, dst_file)
                new_files_moved = True
            except Exception as e:
                print(f"[!] Error moving file {f}: {e}")

    # 5. Check what PDFs are currently in Archive/official
    current_official_pdfs = set()
    for f in os.listdir(official_dir):
        if f.lower().endswith(".pdf"):
            current_official_pdfs.add(f)

    # 6. Check if anything changed (moved new files, or files deleted in Archive/official)
    changed = new_files_moved or (db_pdfs != current_official_pdfs)

    if not changed:
        print("[*] No changes detected. PDF index is up to date.")
        conn.close()
        return

    print("[*] Rebuilding PDF index due to manual list changes...")

    # Clear old PDF chunks from the database
    print("[*] Clearing old PDF entries from database...")
    cursor.execute("DELETE FROM fts_chunks WHERE chunk_id IN (SELECT chunk_id FROM chunks WHERE source = 'official')")
    cursor.execute("DELETE FROM chunks WHERE source = 'official'")
    conn.commit()

    # 7. Extract chunks for current official PDF manuals
    new_pdf_chunks = []
    if current_official_pdfs:
        print(f"[*] Extracting text from PDF manuals in {official_dir}...")
        pdf_importer = PDFImporter(
            manuals_dir=official_dir,
            target_words=750,
            overlap_words=150
        )
        new_pdf_chunks = pdf_importer.import_documents()
    else:
        print("[*] No PDF manuals found in Archive/official.")

    # 8. Generate embeddings for the new PDF chunks
    new_pdf_embeddings = []
    if new_pdf_chunks:
        print(f"[*] Initializing embedding provider...")
        embeddings_provider = get_embeddings_provider(provider=provider)
        print(f"Embeddings Provider: {embeddings_provider.__class__.__name__}")
        
        batch_size = 50
        num_chunks = len(new_pdf_chunks)
        print(f"[*] Computing embeddings for {num_chunks} PDF chunks...")
        chunk_texts = [c['text'] for c in new_pdf_chunks]
        
        if tqdm:
            page_iter = tqdm(range(0, num_chunks, batch_size), desc="PDF Embeddings", unit="batch")
        else:
            page_iter = range(0, num_chunks, batch_size)
            
        for i in page_iter:
            if not tqdm and i > 0:
                print(f"     Embedding chunk {i}/{num_chunks}...")
            batch_texts = chunk_texts[i:i+batch_size]
            try:
                batch_embs = embeddings_provider.embed_documents(batch_texts)
                new_pdf_embeddings.extend(batch_embs)
            except Exception as e:
                print(f"[!] Error generating embeddings: {e}")
                # Mock fallback
                from embeddings.mock import MockEmbeddings
                mock = MockEmbeddings()
                batch_embs = mock.embed_documents(batch_texts)
                new_pdf_embeddings.extend(batch_embs)

        # Write new PDF chunks to SQLite
        print("[*] Writing PDF chunks to SQLite base...")
        chunks_data = []
        fts_data = []
        for chunk, emb in zip(new_pdf_chunks, new_pdf_embeddings):
            chunk_id = chunk["id"]
            thread_id = chunk["thread_id"]
            thread_title = chunk["thread_title"]
            url = chunk["url"]
            chunk_index = chunk["chunk_index"]
            text = chunk["text"]
            metadata_json = json.dumps(chunk["metadata"], ensure_ascii=False)
            source = "official"
            
            emb_bytes = np.array(emb, dtype=np.float32).tobytes()
            
            chunks_data.append((chunk_id, thread_id, thread_title, url, chunk_index, text, metadata_json, emb_bytes, source, None))
            fts_data.append((chunk_id, thread_title, text))
            
        cursor.executemany("INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", chunks_data)
        cursor.executemany("INSERT INTO fts_chunks VALUES (?, ?, ?)", fts_data)
        conn.commit()

    # 9. Retrieve ALL chunks (forums + PDFs) from SQLite to rebuild vector store
    print("[*] Loading all chunks from SQLite to build vector store...")
    cursor.execute("SELECT chunk_id, thread_id, thread_title, url, chunk_index, text, metadata_json, embedding, source FROM chunks")
    rows = cursor.fetchall()
    
    all_reconstructed_chunks = []
    all_reconstructed_embeddings = []
    
    for r in rows:
        chunk_id, thread_id, thread_title, url, chunk_index, text, metadata_json, emb_bytes, source = r
        metadata = json.loads(metadata_json)
        emb = np.frombuffer(emb_bytes, dtype=np.float32).tolist()
        
        all_reconstructed_chunks.append({
            "id": chunk_id,
            "thread_id": thread_id,
            "thread_title": thread_title,
            "url": url,
            "chunk_index": chunk_index,
            "text": text,
            "metadata": metadata
        })
        all_reconstructed_embeddings.append(emb)

    conn.close()

    # 10. Rebuild FAISS index
    if all_reconstructed_chunks:
        print(f"[*] Rebuilding FAISS vector store index with {len(all_reconstructed_chunks)} items...")
        vector_store = get_vector_store(store_type=store)
        vector_store.add_documents(all_reconstructed_chunks, all_reconstructed_embeddings)
        vector_store.save(index_dir)
        print("[+] Vector store index successfully rebuilt and saved!")
    else:
        print("[!] No documents to index. Index is empty.")

    # 11. Update last sync dates (sync_dates.json)
    sync_data = {}
    if os.path.exists(sync_path):
        try:
            with open(sync_path, "r", encoding="utf-8") as f:
                sync_data = json.load(f)
        except Exception:
            pass

    # Recalculate official PDF stats
    if current_official_pdfs:
        newest_time = 0
        page_count = 0
        try:
            from pypdf import PdfReader
        except ImportError:
            PdfReader = None

        for f in os.listdir(official_dir):
            if f.lower().endswith(".pdf"):
                pdf_path = os.path.join(official_dir, f)
                mtime = os.path.getmtime(pdf_path)
                if mtime > newest_time:
                    newest_time = mtime
                if PdfReader:
                    try:
                        reader = PdfReader(pdf_path)
                        page_count += len(reader.pages)
                    except Exception:
                        pass
        
        if newest_time > 0:
            sync_data["official"] = {
                "date": datetime.date.fromtimestamp(newest_time).strftime("%Y/%m/%d"),
                "count": page_count
            }
    else:
        sync_data.pop("official", None)

    with open(sync_path, "w", encoding="utf-8") as f:
        json.dump(sync_data, f, ensure_ascii=False, indent=2)

    print("="*60)
    print("[+] Fast PDF Index Update Complete!")
    print("="*60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KM Print Fix Hub PDF-Only Indexer")
    parser.add_argument("--anonymize", action="store_true", help="Use Index_anon folder instead of Index")
    parser.add_argument("--provider", type=str, default=None, help="Force embedding provider")
    parser.add_argument("--store", type=str, default=None, help="Force vector store type")
    args = parser.parse_args()

    run_pdf_update(anonymize=args.anonymize, provider=args.provider, store=args.store)
