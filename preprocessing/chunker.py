# preprocessing/chunker.py
import re
import config
from preprocessing.cleaner import extract_quotes_and_clean

def split_post_by_paragraphs(post, include_quotes, max_words=600):
    """
    Splits an extremely large post into smaller pieces by paragraphs,
    preserving the metadata header on each part.
    """
    # First build full post text content
    content_text = ""
    if include_quotes and post.get('quotes'):
        for q in post['quotes']:
            q_author = q.get('author') or "пользователя"
            content_text += f"[Цитата от {q_author}]:\n{q['text']}\n\n"
    content_text += post.get('text', '')
    
    # Split content by double newlines (paragraphs)
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', content_text) if p.strip()]
    
    sub_posts = []
    current_para = []
    current_words = 0
    part_idx = 1
    
    for p in paragraphs:
        p_words = len(p.split())
        if current_words + p_words > max_words and current_para:
            # Create a sub-post
            sub_posts.append({
                'author': post['author'],
                'date': post['date'],
                'post_no': f"{post['post_no']} (Часть {part_idx})",
                'post_id': post['post_id'],
                'text': "\n\n".join(current_para),
                'quotes': [], # Already formatted inside text
                'attachments': post.get('attachments', []),
                'images': post.get('images', [])
            })
            part_idx += 1
            current_para = [p]
            current_words = p_words
        else:
            current_para.append(p)
            current_words += p_words
            
    if current_para:
        sub_posts.append({
            'author': post['author'],
            'date': post['date'],
            'post_no': f"{post['post_no']} (Часть {part_idx})" if part_idx > 1 else post['post_no'],
            'post_id': post['post_id'],
            'text': "\n\n".join(current_para),
            'quotes': [],
            'attachments': post.get('attachments', []),
            'images': post.get('images', [])
        })
        
    return sub_posts

def format_post_for_chunk(post, include_quotes):
    """
    Formats a single post dictionary into a clear conversational text block.
    """
    header = f"--- Автор: {post['author']} (Пост #{post['post_no']}, Дата: {post['date']})\n"
    body = ""
    if include_quotes and post.get('quotes'):
        for q in post['quotes']:
            q_author = q.get('author') or "пользователя"
            body += f"[Цитата от {q_author}]:\n{q['text']}\n\n"
    body += post.get('text', '')
    return header + body.strip()

def chunk_thread(thread_data, target_words=None, overlap_posts=None, include_quotes=None, anonymize=False):
    """
    Chunks a thread by grouping consecutive posts.
    Returns a list of chunk dictionaries:
    [
      {
        "id": "thread_12345_chunk_1",
        "thread_id": 12345,
        "thread_title": "...",
        "url": "...",
        "chunk_index": 1,
        "text": "...",
        "metadata": {
           "authors": [...],
           "post_ids": [...],
           "post_numbers": [...],
           "attachments": [...],
           "images": [...]
        }
      }
    ]
    """
    if target_words is None:
        target_words = getattr(config, 'CHUNK_SIZE_WORDS', 600)
    if overlap_posts is None:
        overlap_posts = getattr(config, 'CHUNK_OVERLAP_POSTS', 1)
    if include_quotes is None:
        include_quotes = getattr(config, 'INCLUDE_QUOTES_IN_INDEX', True)
        
    thread_id = thread_data['thread_id']
    thread_title = thread_data['title']
    thread_url = thread_data['url']
    
    # Anonymize mapping
    author_map = {}
    anon_counter = 1
    source = thread_data.get("source", "tradeprint")
    is_russian = (source == "tradeprint")
    anon_prefix = "Пользователь " if is_russian else "User "
    
    if anonymize:
        for post in thread_data.get('posts', []):
            author = post.get('author')
            if author and author not in author_map:
                author_map[author] = f"{anon_prefix}{anon_counter}"
                anon_counter += 1
    
    # Clean and pre-process all posts first
    processed_posts = []
    for post in thread_data.get('posts', []):
        # Extract quotes and clean remaining text
        clean_text, quotes = extract_quotes_and_clean(post.get('html', ''), base_url=thread_url)
        
        author = post.get('author')
        if anonymize and author in author_map:
            author = author_map[author]
            
        if anonymize and quotes:
            for q in quotes:
                q_author = q.get('author')
                if q_author and q_author in author_map:
                    q['author'] = author_map[q_author]
        
        post_dict = {
            'post_id': post.get('post_id'),
            'post_no': post.get('post_no'),
            'author': author,
            'date': post.get('date'),
            'text': clean_text,
            'quotes': quotes,
            'attachments': post.get('attachments', []),
            'images': post.get('images', [])
        }
        
        # Format post text to estimate word count
        post_text = format_post_for_chunk(post_dict, include_quotes)
        post_words = len(post_text.split())
        
        # If the post is exceptionally large, split it by paragraphs
        if post_words > target_words * 1.5:
            split_subposts = split_post_by_paragraphs(post_dict, include_quotes, max_words=target_words)
            processed_posts.extend(split_subposts)
        else:
            processed_posts.append(post_dict)
            
    chunks = []
    current_posts = []
    current_words = 0
    chunk_idx = 1
    
    def create_chunk_dict(posts_list, idx):
        # Format the combined text
        posts_text_blocks = []
        for p in posts_list:
            posts_text_blocks.append(format_post_for_chunk(p, include_quotes))
            
        combined_text = (
            f"Тема: {thread_title}\n"
            f"Ссылка: {thread_url}\n\n"
            + "\n\n".join(posts_text_blocks)
        )
        
        # Aggregate metadata
        authors = list(set(p['author'] for p in posts_list if p.get('author')))
        post_ids = [p['post_id'] for p in posts_list if p.get('post_id') is not None]
        post_nos = [str(p['post_no']) for p in posts_list if p.get('post_no') is not None]
        
        attachments = []
        images = []
        for p in posts_list:
            for att in p.get('attachments', []):
                if att not in attachments:
                    attachments.append(att)
            for img in p.get('images', []):
                if img not in images:
                    images.append(img)
                    
        source = thread_data.get("source", "tradeprint")
        return {
            "id": f"{source}_thread_{thread_id}_chunk_{idx}",
            "thread_id": thread_id,
            "thread_title": thread_title,
            "url": thread_url,
            "chunk_index": idx,
            "text": combined_text,
            "metadata": {
                "source": source,
                "authors": authors,
                "post_ids": post_ids,
                "post_numbers": post_nos,
                "attachments": attachments,
                "images": images
            }
        }
        
    for p in processed_posts:
        p_text = format_post_for_chunk(p, include_quotes)
        p_words = len(p_text.split())
        
        if current_words + p_words > target_words * 1.25 and current_posts:
            # Create chunk
            chunks.append(create_chunk_dict(current_posts, chunk_idx))
            chunk_idx += 1
            
            # Keep overlap posts
            if overlap_posts > 0:
                current_posts = current_posts[-overlap_posts:]
                # Recalculate word count for overlap
                current_words = sum(len(format_post_for_chunk(op, include_quotes).split()) for op in current_posts)
            else:
                current_posts = []
                current_words = 0
                
        current_posts.append(p)
        current_words += p_words
        
    if current_posts:
        chunks.append(create_chunk_dict(current_posts, chunk_idx))
        
    return chunks
