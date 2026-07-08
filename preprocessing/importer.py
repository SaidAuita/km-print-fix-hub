# preprocessing/importer.py
import os
import re
import json
from bs4 import BeautifulSoup
from preprocessing.chunker import chunk_thread
import config

class DocumentImporter:
    def __init__(self, index_dir=None):
        self.index_dir = index_dir

    def import_documents(self):
        """
        Gathers documents, processes/chunks them, and returns a list of chunk dictionaries.
        """
        raise NotImplementedError

class ForumImporter(DocumentImporter):
    def __init__(self, archive_dir, target_words=600, overlap_posts=1, include_quotes=True, anonymize=False):
        super().__init__()
        self.archive_dir = archive_dir
        self.target_words = target_words
        self.overlap_posts = overlap_posts
        self.include_quotes = include_quotes
        self.anonymize = anonymize

    def import_documents(self):
        chunks = []
        if not os.path.exists(self.archive_dir):
            print(f"[!] Warning: Archive directory '{self.archive_dir}' does not exist.")
            return chunks

        thread_paths = []
        for root, dirs, files in os.walk(self.archive_dir):
            for d in dirs:
                # Do not walk into 'official' subdirectory
                if d == "official":
                    continue
                if d.startswith("thread_"):
                    thread_paths.append(os.path.join(root, d))

        print(f"[*] ForumImporter: Scanning {len(thread_paths)} threads (anonymize={self.anonymize})...")
        try:
            from tqdm import tqdm
            pbar = tqdm(thread_paths, desc="Parsing threads", unit="thread")
        except ImportError:
            pbar = thread_paths
            
        for t_path in pbar:
            json_path = os.path.join(t_path, "thread.json")
            if not os.path.exists(json_path):
                continue
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    thread_data = json.load(f)
                
                # Determine source based on parent folder name
                parent_dir = os.path.basename(os.path.dirname(t_path))
                thread_data["source"] = parent_dir
                
                thread_chunks = chunk_thread(
                    thread_data,
                    target_words=self.target_words,
                    overlap_posts=self.overlap_posts,
                    include_quotes=self.include_quotes,
                    anonymize=self.anonymize
                )
                chunks.extend(thread_chunks)
            except Exception as e:
                print(f"[!] ForumImporter: Error chunking thread {os.path.basename(t_path)}: {e}")

        return chunks

class PDFImporter(DocumentImporter):
    def __init__(self, manuals_dir, target_words=750, overlap_words=150):
        super().__init__()
        self.manuals_dir = manuals_dir
        self.target_words = target_words
        self.overlap_words = overlap_words

    def import_documents(self):
        chunks = []
        if not os.path.exists(self.manuals_dir):
            print(f"[!] Warning: manuals directory '{self.manuals_dir}' does not exist.")
            return chunks

        try:
            from pypdf import PdfReader
        except ImportError:
            print("[!] Error: 'pypdf' package is not installed.")
            return chunks

        pdf_files = [f for f in os.listdir(self.manuals_dir) if f.lower().endswith(".pdf")]
        print(f"[*] PDFImporter: Found {len(pdf_files)} PDFs in '{self.manuals_dir}'...")

        for pdf_name in pdf_files:
            pdf_path = os.path.join(self.manuals_dir, pdf_name)
            try:
                print(f"  -> Reading {pdf_name}...")
                reader = PdfReader(pdf_path)
                pages_text = []
                num_pages = len(reader.pages)
                
                try:
                    from tqdm import tqdm
                    page_iter = tqdm(enumerate(reader.pages), total=num_pages, desc=f"  Extracting {pdf_name[:20]}", unit="page", leave=False)
                except ImportError:
                    page_iter = enumerate(reader.pages)
                    print(f"  -> Extracting text from {num_pages} pages...")
                    
                for i, page in page_iter:
                    if not hasattr(page_iter, "total") and i % 100 == 0 and i > 0:
                        print(f"     Page {i}/{num_pages}...")
                    text = page.extract_text() or ""
                    pages_text.append((i + 1, text))
                
                # Process and chunk the text
                pdf_chunks = self._chunk_pdf_text(pdf_name, pages_text)
                chunks.extend(pdf_chunks)
                print(f"  -> Generated {len(pdf_chunks)} chunks for {pdf_name}")
            except Exception as e:
                print(f"[!] PDFImporter: Error processing PDF {pdf_name}: {e}")

        return chunks

    def _chunk_pdf_text(self, pdf_filename, pages_text):
        chunks = []
        thread_title = os.path.splitext(pdf_filename)[0]
        
        models_to_check = config.load_models_list()
        
        for page_num, text in pages_text:
            clean_text = re.sub(r'\s+', ' ', text).strip()
            if not clean_text or len(clean_text) < 10:
                continue
                
            words = clean_text.split()
            total_words = len(words)
            
            # If the page is small enough, it fits in one chunk
            if total_words <= self.target_words:
                self._add_page_chunk(chunks, thread_title, pdf_filename, page_num, clean_text, models_to_check)
            else:
                # If page text is very large, split it with sliding window
                start_idx = 0
                sub_idx = 1
                while start_idx < total_words:
                    end_idx = min(start_idx + self.target_words, total_words)
                    chunk_words = words[start_idx:end_idx]
                    chunk_text = " ".join(chunk_words)
                    
                    self._add_page_chunk(chunks, thread_title, pdf_filename, page_num, chunk_text, models_to_check, sub_idx)
                    sub_idx += 1
                    
                    next_start = start_idx + (self.target_words - self.overlap_words)
                    if next_start >= total_words or next_start <= start_idx:
                        break
                    start_idx = next_start
                    
        return chunks

    def _add_page_chunk(self, chunks, thread_title, pdf_filename, page_num, chunk_text, models_to_check, sub_idx=None):
        # Extract section heading
        section = ""
        lines = [line.strip() for line in chunk_text.split('\n') if line.strip()]
        for line in lines[:3]:
            if re.match(r'^(Section|Chapter|Part|Раздел|Глава)\s+\d+', line, re.I) or re.match(r'^\d+(\.\d+)+\s+[A-ZА-Я]', line):
                section = line
                break

        # Find matching models (checking both filename and chunk text)
        models_found = []
        filename_and_text = f"{pdf_filename} {chunk_text}".lower().replace('с', 'c')
        for m in models_to_check:
            pattern = r'\b' + re.escape(m.lower()) + r'\b'
            if re.search(pattern, filename_and_text):
                models_found.append(m)

        # Detect language
        language = "ru" if any(c in 'аяАЯёЁ' for c in chunk_text) else "en"

        section_prefix = f"Раздел: {section}\n" if section else ""
        formatted_text = (
            f"Документ: {pdf_filename}\n"
            f"Страница: {page_num}\n"
            + section_prefix +
            f"\n{chunk_text}"
        )

        chunk_suffix = f"_{sub_idx}" if sub_idx is not None else ""
        chunk_id = f"official_{thread_title}_page_{page_num}_chunk{chunk_suffix}"

        chunks.append({
            "id": chunk_id,
            "thread_id": 0,
            "thread_title": thread_title,
            "url": f"/archive/official/{pdf_filename}#page={page_num}",
            "chunk_index": len(chunks) + 1,
            "text": formatted_text,
            "metadata": {
                "source": "official",
                "document": pdf_filename,
                "page": page_num,
                "section": section,
                "machine": models_found,
                "language": language
            }
        })
