#!/usr/bin/env python3
# index_kb.py
# Preprocesses forum archive, chunks threads, computes embeddings, and builds local vector store index.

import os

# Используем зеркало Hugging Face для надежной и быстрой загрузки моделей в РФ
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import json
import argparse
import sqlite3
import numpy as np
from tqdm import tqdm

import config
from preprocessing.importer import ForumImporter, PDFImporter
from embeddings.factory import get_embeddings_provider
from vector_store.factory import get_vector_store

def save_to_sqlite(index_dir, chunks, embeddings):
    db_path = os.path.join(index_dir, "knowledge_base.db")
    print(f"[*] Сохранение {len(chunks)} документов в SQLite FTS5 базу '{db_path}'...")
    
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception as e:
            print(f"[!] Ошибка удаления старой БД: {e}")
            
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Создаем таблицу чанков
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
        source TEXT
    )
    """)
    
    # Создаем виртуальную таблицу FTS5 для поиска
    cursor.execute("""
    CREATE VIRTUAL TABLE fts_chunks USING fts5(
        chunk_id UNINDEXED,
        thread_title,
        text
    )
    """)
    
    chunks_data = []
    fts_data = []
    
    for chunk, emb in zip(chunks, embeddings):
        chunk_id = chunk["id"]
        thread_id = chunk["thread_id"]
        thread_title = chunk["thread_title"]
        url = chunk["url"]
        chunk_index = chunk["chunk_index"]
        text = chunk["text"]
        metadata_json = json.dumps(chunk["metadata"], ensure_ascii=False)
        source = chunk["metadata"].get("source", "tradeprint")
        
        # Конвертируем вектор в байты float32
        emb_bytes = np.array(emb, dtype=np.float32).tobytes()
        
        chunks_data.append((chunk_id, thread_id, thread_title, url, chunk_index, text, metadata_json, emb_bytes, source))
        fts_data.append((chunk_id, thread_title, text))
        
    cursor.executemany("INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", chunks_data)
    cursor.executemany("INSERT INTO fts_chunks VALUES (?, ?, ?)", fts_data)
    
    conn.commit()
    conn.close()
    print("[+] SQLite база данных успешно сохранена!")

def build_index(force_provider=None, force_store=None, anonymize=False):
    archive_dir = config.ARCHIVE_DIR
    index_dir = "Index_anon" if anonymize else config.INDEX_DIR
    
    if not os.path.exists(archive_dir):
        print(f"[!] Error: Archive directory '{archive_dir}' does not exist. Run parser first.")
        return
        
    print("="*60)
    print(f"Initializing Knowledge Base Indexer Pipeline (anonymize={anonymize})")
    print(f"Archive Directory: {archive_dir}")
    print(f"Target Index Directory: {index_dir}")
    
    # 1. Initialize embeddings provider
    embeddings_provider = get_embeddings_provider(provider=force_provider)
    print(f"Embeddings Provider: {embeddings_provider.__class__.__name__} (Model: {config.EMBEDDING_MODEL})")
    
    # 2. Initialize vector store
    vector_store = get_vector_store(store_type=force_store)
    print(f"Vector Store Type: {vector_store.__class__.__name__}")
    print("="*60)
    # 3. Read threads and build chunk list via Importers
    all_chunks = []
    
    # 3.1 Forum Importer
    forum_importer = ForumImporter(
        archive_dir=archive_dir,
        target_words=config.CHUNK_SIZE_WORDS,
        overlap_posts=config.CHUNK_OVERLAP_POSTS,
        include_quotes=config.INCLUDE_QUOTES_IN_INDEX,
        anonymize=anonymize
    )
    all_chunks.extend(forum_importer.import_documents())
    
    # 3.2 Copy PDF files from Service_manuals to Archive/official first
    official_dir = os.path.join(archive_dir, "official")
    os.makedirs(official_dir, exist_ok=True)
    
    manuals_dir = "Service_manuals"
    if os.path.exists(manuals_dir):
        import shutil
        for f in os.listdir(manuals_dir):
            if f.lower().endswith(".pdf"):
                src_file = os.path.join(manuals_dir, f)
                dst_file = os.path.join(official_dir, f)
                if not os.path.exists(dst_file) or os.path.getsize(src_file) != os.path.getsize(dst_file):
                    print(f"[*] Copying {f} to {official_dir}...")
                    shutil.copy2(src_file, dst_file)
                    
    # 3.3 PDF Importer: Scan Archive/official so that previously copied manuals
    # are indexed even if they are deleted from Service_manuals/
    if os.path.exists(official_dir):
        pdf_importer = PDFImporter(
            manuals_dir=official_dir,
            target_words=750,
            overlap_words=150
        )
        all_chunks.extend(pdf_importer.import_documents())
                    
    total_chunks = len(all_chunks)
    print(f"[*] Preprocessing complete. Total generated chunks: {total_chunks}")
    
    if total_chunks == 0:
        print("[!] No chunks generated. Exiting.")
        return
        
    # 4. Generate embeddings and add to vector store
    batch_size = 50
    print(f"[*] Generating embeddings and adding to index (batch size: {batch_size})...")
    
    chunk_texts = [c['text'] for c in all_chunks]
    all_embeddings = []
    
    for i in tqdm(range(0, total_chunks, batch_size), desc="Generating Embeddings"):
        batch_texts = chunk_texts[i:i+batch_size]
        try:
            batch_embs = embeddings_provider.embed_documents(batch_texts)
            all_embeddings.extend(batch_embs)
        except Exception as e:
            print(f"[!] Error generating embeddings for batch {i//batch_size + 1}: {e}")
            from embeddings.mock import MockEmbeddings
            mock = MockEmbeddings()
            batch_embs = mock.embed_documents(batch_texts)
            all_embeddings.extend(batch_embs)
            
    if len(all_embeddings) != total_chunks:
        print(f"[!] Error: Expected {total_chunks} embeddings, but got {len(all_embeddings)}")
        return
        
    print("[*] Adding documents to vector store index...")
    vector_store.add_documents(all_chunks, all_embeddings)
    
    # 5. Save the index
    print(f"[*] Saving vector index to '{index_dir}'...")
    vector_store.save(index_dir)
    
    # 6. Save metadata and FTS tables to SQLite
    save_to_sqlite(index_dir, all_chunks, all_embeddings)
    
    # 7. Extract and save last sync dates
    print("[*] Extracting last synchronization dates and counts...")
    sync_data = {}
    counts = {}
    latest_dates = {}
    import datetime
    
    if os.path.exists(archive_dir):
        for root, dirs, files in os.walk(archive_dir):
            for d in dirs:
                if d == "official" or not d.startswith("thread_"):
                    continue
                t_path = os.path.join(root, d)
                json_path = os.path.join(t_path, "thread.json")
                if os.path.exists(json_path):
                    try:
                        with open(json_path, "r", encoding="utf-8") as f:
                            thread_data = json.load(f)
                        source = os.path.basename(os.path.dirname(t_path))
                        
                        posts_list = thread_data.get("posts", [])
                        counts[source] = counts.get(source, 0) + len(posts_list)
                        
                        # Find newest post date
                        for post in posts_list:
                            date_str = post.get("date")
                            if date_str:
                                parts = date_str.split(",")[0].split(".")
                                if len(parts) == 3:
                                    d_val = datetime.date(int(parts[2]), int(parts[1]), int(parts[0]))
                                    if source not in latest_dates or d_val > latest_dates[source]:
                                        latest_dates[source] = d_val
                    except Exception:
                        continue
                        
        for src, d_val in latest_dates.items():
            sync_data[src] = {
                "date": d_val.strftime("%Y/%m/%d"),
                "count": counts.get(src, 0)
            }

    # Add official manuals date and page count
    official_dir = os.path.join(archive_dir, "official")
    if os.path.exists(official_dir):
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
            
    with open(os.path.join(index_dir, "sync_dates.json"), "w", encoding="utf-8") as f:
        json.dump(sync_data, f, ensure_ascii=False, indent=2)
    print(f"[+] Saved last sync dates and counts to Index/sync_dates.json: {sync_data}")
    
    print("[+] Knowledge base index compiled successfully!")
    print("="*60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trade-Print Forum Knowledge Base Indexer (Stage 2)")
    parser.add_argument("--provider", type=str, default=None, help="Force embedding provider (mock, sentence-transformers, lm-studio, huggingface)")
    parser.add_argument("--store", type=str, default=None, help="Force vector store type (simple, faiss)")
    parser.add_argument("--anonymize", action="store_true", help="Compile an anonymized version of the index (author names replaced by Пользователь X / User X)")
    args = parser.parse_args()
    
    build_index(force_provider=args.provider, force_store=args.store, anonymize=args.anonymize)
