# preprocessing/cleaner.py
import re
import copy
import urllib.parse
from bs4 import BeautifulSoup

def clean_html_text(element, base_url="https://forum.trade-print.ru/"):
    """
    Converts a BeautifulSoup element (e.g. post message div) into clean text.
    Preserves paragraph structure, code blocks, lists, and links as absolute URLs.
    """
    if element is None:
        return ""
        
    # Copy element to prevent changing original DOM
    el = copy.copy(element)
    
    # 1. Format code blocks
    for pre in el.find_all(['pre', 'code']):
        code_text = pre.get_text()
        pre.replace_with(f"\n```\n{code_text}\n```\n")
        
    # 2. Format links
    for a in el.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)
        if href.startswith('#') or not text:
            continue
        try:
            abs_href = urllib.parse.urljoin(base_url, href)
        except ValueError:
            abs_href = href
        if text == abs_href or text.startswith('http'):
            a.replace_with(f" {abs_href} ")
        else:
            a.replace_with(f" [{text}]({abs_href}) ")
            
    # 3. Format line breaks
    for br in el.find_all('br'):
        br.replace_with("\n")
        
    # 4. Format paragraphs and block containers
    for div in el.find_all(['div', 'p', 'blockquote']):
        div.insert_before("\n")
        div.insert_after("\n")
        
    # 5. Format lists
    for li in el.find_all('li'):
        li.insert_before("\n* ")
        
    # 6. Format table rows (if any remaining)
    for tr in el.find_all('tr'):
        tr.insert_after("\n")
        
    # Extract raw text
    raw_text = el.get_text()
    
    # 7. Clean up lines
    lines = []
    for line in raw_text.split('\n'):
        # Strip trailing/leading spaces on each line
        cleaned_line = re.sub(r'[ \t]+', ' ', line).strip()
        # Filter out BBCode regex if any remaining
        cleaned_line = re.sub(r'\[/?[a-zA-Z*=\d\s#\-]+\]', '', cleaned_line)
        lines.append(cleaned_line)
        
    text = "\n".join(lines)
    
    # Remove signatures or dashed separators
    for sep in ["__________________", "------------------", "________________\n", "________________\r"]:
        if sep in text:
            text = text.split(sep)[0]
            
    # Remove multiple empty lines (max 2 consecutive newlines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def extract_quotes_and_clean(post_html_content, base_url="https://forum.trade-print.ru/"):
    """
    Parses post HTML, extracts quote metadata and texts, decomposes the quotes,
    and returns a tuple: (clean_message_text, list_of_quotes).
    
    Each quote dict in the list contains:
      - 'author': username of the quoted author (if found)
      - 'text': cleaned text of the quote
    """
    if not post_html_content:
        return "", []
        
    soup = BeautifulSoup(post_html_content, 'lxml')
    # Find the post message container if the whole HTML is supplied,
    # otherwise default to the whole body
    pm = soup.find('div', id=lambda val: val and val.startswith('post_message_'))
    if not pm:
        pm = soup.select_one('.bbWrapper') or soup.select_one('.js-post__content-text') or soup
        
    quotes = []
    
    # 1. XenForo quote blocks (blockquote.bbCodeBlock--quote)
    xf_quotes = []
    for bq in pm.find_all('blockquote', class_=lambda val: val and 'quote' in val):
        parent_bq = bq.find_parent('blockquote', class_=lambda val: val and 'quote' in val)
        if not parent_bq:
            xf_quotes.append(bq)
            
    for bq in xf_quotes:
        quote_author = bq.get('data-quote')
        if not quote_author:
            title_el = bq.select_one('.bbCodeBlock-title')
            if title_el:
                quote_author = re.sub(r'\s+said:.*', '', title_el.get_text(strip=True), flags=re.I).strip()
        
        content_el = bq.select_one('.bbCodeBlock-expandContent') or bq.select_one('.bbCodeBlock-content') or bq
        quote_clean_text = clean_html_text(content_el, base_url=base_url)
        
        quotes.append({
            'author': quote_author or "unknown",
            'text': quote_clean_text
        })
        bq.decompose()
        
    # 2. vBulletin quote tables
    quote_tables = []
    for table in pm.find_all('table'):
        # Check if table represents a quote (usually has td with class alt2)
        if table.find('td', class_='alt2'):
            # Ensure it is a top-level quote table
            parent_table = table.find_parent('table')
            if not (parent_table and parent_table.find('td', class_='alt2')):
                quote_tables.append(table)
                
    for qt in quote_tables:
        # Extract quote text
        quote_raw_text = clean_html_text(qt, base_url=base_url)
        
        # Extract quote author if available (usually in strong tag inside quote table)
        strong = qt.find('strong')
        quote_author = strong.text.strip() if strong else None
        
        # Format the quote text slightly if needed (strip author name prefix if present)
        # e.g., "Сообщение от wizard" -> clean up
        quote_clean_text = quote_raw_text
        if quote_author and "Сообщение от" in quote_raw_text:
            # Strip the "Сообщение от wizard [кнопка]" line
            lines = quote_raw_text.split('\n')
            if len(lines) > 1:
                quote_clean_text = "\n".join(lines[1:]).strip()
                
        quotes.append({
            'author': quote_author or "unknown",
            'text': quote_clean_text
        })
        
        # Decompose the quote table and its preceding "Цитата:" header
        prev = qt.find_previous(class_='smallfont')
        if prev and any(keyword in prev.text for keyword in ["Цитата", "Quote"]):
            prev.decompose()
        qt.decompose()
        
    # 3. vBulletin 6 quote containers (.bbcode_quote / .quote_container)
    vb6_quotes = []
    for q_div in pm.find_all('div', class_=lambda val: val and ('bbcode_quote' in val or 'quote_container' in val)):
        # Ensure it is a top-level quote container
        parent_q = q_div.find_parent('div', class_=lambda val: val and ('bbcode_quote' in val or 'quote_container' in val))
        if not parent_q:
            vb6_quotes.append(q_div)
            
    for q_div in vb6_quotes:
        # Extract quote text
        quote_raw_text = clean_html_text(q_div, base_url=base_url)
        
        quote_author = "unknown"
        # Find author: usually inside originally posted by text
        orig_match = re.search(r'Originally\s+posted\s+by\s*([^\n\r]+)', quote_raw_text, re.I)
        if orig_match:
            quote_author = orig_match.group(1).strip()
            # Clean author
            quote_author = re.sub(r'\s+View\s+Post.*', '', quote_author, flags=re.I).strip()
            lines = quote_raw_text.split('\n')
            if len(lines) > 1 and "Originally posted by" in lines[0]:
                quote_raw_text = "\n".join(lines[1:]).strip()
                
        quotes.append({
            'author': quote_author,
            'text': quote_raw_text
        })
        q_div.decompose()
        
    # Get clean remaining message text
    clean_message = clean_html_text(pm, base_url=base_url)
    
    return clean_message, quotes
