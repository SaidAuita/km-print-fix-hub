import re

class LLMContextOptimizer:
    def __init__(self):
        # Noise patterns to filter out conversational noise lines
        self.noise_patterns = [
            r'^\s*(всем\s+)?привет(ствование)?(\s+всем)?\s*[\!\?]*\s*$',
            r'^\s*здравствуйте\s*[\!\?]*\s*$',
            r'^\s*добрый\s+(день|вечер|утр[оа])\s*[\!\?]*\s*$',
            r'^\s*(заранее\s+)?спасибо(чки)?\s*[\!\?]*\s*$',
            r'^\s*(буду\s+)?благодарен\s*[\!\?]*\s*$',
            r'^\s*с\s+уважением\s*[\!\?]*\s*$',
            r'^\s*с\s+уважением\b.*$',
            r'^\s*thanks?(\s+in\s+advance)?\s*[\!\?]*\s*$',
            r'^\s*regards\b.*$',
            r'^\s*best\s+regards\b.*$',
            r'^\s*hello\s*[\!\?]*\s*$',
            r'^\s*hi\s*[\!\?]*\s*$',
        ]
        self.compiled_noise = [re.compile(p, re.IGNORECASE) for p in self.noise_patterns]

    def _strip_quotes(self, text):
        """
        Removes [Цитата от ...] quote blocks to reduce token usage.
        """
        # Match "[Цитата от ...]:\n" and all lines up to next double newline, --- Автор, or end of string.
        pattern = r'\[Цитата от [^\]]+\]:\s*\n.*?(?=\n\n|\Z|--- Автор)'
        cleaned = re.sub(pattern, '', text, flags=re.DOTALL)
        # Collapse multiple newlines
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        return cleaned.strip()

    def _clean_noise_lines(self, text):
        """
        Removes conversational noise/filler lines (greetings, thanks, signatures).
        """
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            # If the line is a header (like --- Автор: ...), don't filter it
            if line.startswith("--- Автор:"):
                cleaned_lines.append(line)
                continue
            
            # Check against noise patterns
            is_noise = False
            for pattern in self.compiled_noise:
                if pattern.match(line):
                    is_noise = True
                    break
            
            if not is_noise:
                cleaned_lines.append(line)
                
        return '\n'.join(cleaned_lines).strip()

    def _parse_posts(self, text):
        """
        Parses a formatted chunk text back into individual posts.
        Returns a list of dicts: [{'author': ..., 'post_no': ..., 'date': ..., 'text': ...}]
        """
        pattern = r'--- Автор:\s*(.*?)\s*\(Пост\s*#\s*(.*?),\s*Дата:\s*(.*?)\)\n'
        parts = re.split(pattern, text)
        posts = []
        if len(parts) > 1:
            # First part is text before first post (ignored or saved)
            for i in range(1, len(parts), 4):
                if i + 3 < len(parts):
                    posts.append({
                        'author': parts[i].strip(),
                        'post_no': parts[i+1].strip(),
                        'date': parts[i+2].strip(),
                        'text': parts[i+3].strip()
                    })
        else:
            # If parsing header fails (e.g. PDF manual page), treat the whole text as one block
            posts.append({
                'author': 'Unknown',
                'post_no': '0',
                'date': 'Unknown',
                'text': text.strip()
            })
        return posts

    def _get_post_number_numeric(self, post_no_str):
        """
        Extracts the first number in post_no for sorting.
        """
        m = re.search(r'\d+', post_no_str)
        if m:
            return int(m.group(0))
        return 99999

    def optimize(self, documents):
        """
        Optimizes the list of retrieved document tuples: [(doc_dict, score), ...]
        Returns a list of optimized tuples: [(optimized_doc_dict, score), ...]
        """
        if not documents:
            return []

        # 1. Deduplicate by chunk ID or text lowercased/trimmed
        seen_ids = set()
        seen_texts = set()
        unique_docs = []
        
        for doc, score in documents:
            doc_id = doc.get("id")
            text_norm = doc.get("text", "").strip().lower()
            
            # Skip if ID or text already seen
            if doc_id and doc_id in seen_ids:
                continue
            if text_norm in seen_texts:
                continue
                
            seen_ids.add(doc_id)
            seen_texts.add(text_norm)
            unique_docs.append((doc, score))

        # 2. Group documents by thread URL / document name to merge overlaps
        groups = {} # group_key -> list of (doc, score)
        
        for doc, score in unique_docs:
            source = doc.get("metadata", {}).get("source", "tradeprint")
            if source == "official":
                group_key = f"pdf_{doc.get('metadata', {}).get('document', 'unknown')}"
            else:
                url = doc.get("url", "")
                thread_url = re.sub(r'#post\d+$', '', url)
                thread_url = re.sub(r'\?p=\d+', '', thread_url)
                group_key = f"forum_{thread_url}" if thread_url else f"doc_{doc.get('id')}"
                
            groups.setdefault(group_key, []).append((doc, score))

        optimized_results = []

        for group_key, items in groups.items():
            if group_key.startswith("forum_"):
                # Merge forum thread chunks
                items.sort(key=lambda x: x[1], reverse=True)
                base_doc, best_score = items[0]
                
                # Parse all posts from all chunks in this group
                all_posts = []
                seen_post_keys = set()
                
                for doc, _ in items:
                    posts = self._parse_posts(doc.get("text", ""))
                    for p in posts:
                        post_key = (p['author'], p['post_no'])
                        if post_key not in seen_post_keys:
                            seen_post_keys.add(post_key)
                            all_posts.append(p)
                
                # Sort posts chronologically by post number
                all_posts.sort(key=lambda x: self._get_post_number_numeric(x['post_no']))
                
                # Process each post: remove quotes, filter out noise lines
                optimized_posts_text = []
                merged_authors = set()
                
                for p in all_posts:
                    cleaned_body = self._strip_quotes(p['text'])
                    cleaned_body = self._clean_noise_lines(cleaned_body)
                    
                    if cleaned_body:
                        # Re-format post header & clean body
                        header = f"--- Автор: {p['author']} (Пост #{p['post_no']}, Дата: {p['date']})\n"
                        optimized_posts_text.append(header + cleaned_body)
                        # Exclude only anonymized author placeholders (e.g. "User 1" or "Пользователь 2")
                        is_placeholder = bool(p['author'] and re.match(r'^(User|Пользователь)\s+\d+$', p['author']))
                        if p['author'] and not is_placeholder:
                            merged_authors.add(p['author'])
                            
                if optimized_posts_text:
                    merged_text = "\n\n".join(optimized_posts_text)
                    
                    # Create optimized copy of base doc
                    opt_doc = base_doc.copy()
                    opt_doc["text"] = merged_text
                    
                    # Update metadata
                    opt_metadata = base_doc.get("metadata", {}).copy()
                    if merged_authors:
                        opt_metadata["authors"] = sorted(list(merged_authors))
                    opt_doc["metadata"] = opt_metadata
                    
                    optimized_results.append((opt_doc, best_score))
            else:
                # For official PDF or single uncategorized document, process text individually
                for doc, score in items:
                    cleaned_text = self._strip_quotes(doc.get("text", ""))
                    cleaned_text = self._clean_noise_lines(cleaned_text)
                    
                    if cleaned_text:
                        opt_doc = doc.copy()
                        opt_doc["text"] = cleaned_text
                        optimized_results.append((opt_doc, score))

        # Sort final results by score descending
        optimized_results.sort(key=lambda x: x[1], reverse=True)
        return optimized_results
