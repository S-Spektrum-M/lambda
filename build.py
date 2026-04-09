#!/usr/bin/env python3
"""Converts markdown files in posts/ to HTML in _site/. That's it."""

import argparse
import os
import re
import shutil
from collections import defaultdict
from datetime import date
from html import unescape
import markdown

POSTS_DIR = "posts"
SITE_DIR = "_site"
TEMPLATE = open("template.html").read()


def extract_title(md_text):
    """Pull the first # heading, or fall back to 'Untitled'."""
    m = re.match(r"^#\s+(.+)", md_text.strip())
    return m.group(1) if m else "Untitled"


def extract_date(fname):
    """Pull a YYYY-MM-DD prefix from filename, or return empty string."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", fname)
    return m.group(1) if m else ""


def slugify_heading(text):
    """Convert heading text into a stable fragment id."""
    slug = unescape(text).lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug).strip("-")
    return slug or "section"


def assign_heading_slugs(headings):
    """Attach unique slugs to heading entries while preserving order."""
    counts = defaultdict(int)
    items = []
    for level, text in headings:
        base = slugify_heading(text)
        counts[base] += 1
        slug = base if counts[base] == 1 else f"{base}-{counts[base]}"
        items.append({"level": level, "text": text, "slug": slug})
    return items


def build_toc(headings):
    """Build a TOC from heading metadata."""
    if not headings:
        return ""
    items = []
    for heading in headings:
        cls = f'toc-h{heading["level"]}'
        items.append(f'<li class="{cls}"><a href="#{heading["slug"]}">{heading["text"]}</a></li>')
    return '<nav class="toc" id="toc"><ul>' + "\n".join(items) + "</ul></nav>"


def add_heading_ids(html, headings):
    """Add id attributes to h2/h3/h4 tags for TOC anchor links."""
    heading_iter = iter(headings)

    def make_id(match):
        tag = match.group(1)
        attrs = match.group(2)
        text = match.group(3)
        heading = next(heading_iter, None)
        if heading is None:
            return match.group(0)
        return f'<{tag}{attrs} id="{heading["slug"]}">{text}</{tag}>'

    return re.sub(r"<(h[234])([^>]*)>(.+?)</\1>", make_id, html)


def add_callouts(html):
    """Convert blockquotes starting with [!TYPE] into callouts."""
    def repl(match):
        ctype = match.group(1).lower()
        title = match.group(1).capitalize()
        return f'<blockquote class="callout callout-{ctype}"><p><strong class="callout-title">{title}</strong><br>'
    return re.sub(r'<blockquote>\s*<p>\[!([A-Z]+)\]\s*', repl, html)


def build_post(md_path):
    md_text = open(md_path).read()
    headings = re.findall(r"^(#{2,4})\s+(.+)", md_text, re.MULTILINE)
    heading_data = assign_heading_slugs([(len(hashes), text) for hashes, text in headings])
    html = markdown.markdown(md_text, extensions=["fenced_code", "tables"])
    html = add_heading_ids(html, heading_data)
    html = add_callouts(html)
    title = extract_title(md_text)
    toc = build_toc(heading_data)
    page = (TEMPLATE
            .replace("{{TITLE}}", title)
            .replace("{{CONTENT}}", html)
            .replace("{{SEARCH}}", "")
            .replace("{{TOC}}", toc)
            .replace("{{BASE_URL}}", "../"))
    slug = re.sub(r"-?\d{4}-\d{2}-\d{2}", "", os.path.splitext(os.path.basename(md_path))[0]).strip("-")
    date = extract_date(os.path.basename(md_path))
    return slug, title, date, page


def render_inline(text):
    """Convert backtick-wrapped text to <code> tags."""
    return re.sub(r'`+(.+?)`+', r'<code>\1</code>', text)


def build_index(posts):
    items = []
    for slug, title, date in posts:
        date_html = f'<span class="post-meta">{date}</span>' if date else ""
        title_html = render_inline(title)
        items.append(
            f'<li data-title="{title.lower()}"><a href="{slug}/">{title_html}{date_html}</a></li>')
    items_html = "\n".join(items)

    search_html = """<div class="search-wrap">
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
  <input type="text" id="search" placeholder="Search posts..." autocomplete="off">
</div>"""

    content = f"""<h1>Posts</h1>
<ul class="post-list" id="post-list">
{items_html}
</ul>
<p class="no-results" id="no-results">No posts found.</p>
<script>
document.addEventListener('keydown', function(e) {{
  if (e.key === '/' && document.activeElement !== document.getElementById('search')) {{
    e.preventDefault();
    document.getElementById('search').focus();
  }}
}});
document.getElementById('search').addEventListener('input', function() {{
  var q = this.value.toLowerCase();
  var items = document.querySelectorAll('#post-list li');
  var visible = 0;
  items.forEach(function(li) {{
    var match = li.getAttribute('data-title').indexOf(q) !== -1;
    li.style.display = match ? '' : 'none';
    if (match) visible++;
  }});
  document.getElementById('no-results').style.display = visible === 0 ? 'block' : 'none';
}});
</script>"""
    return TEMPLATE.replace("{{TITLE}}", "Spektrum's Wavelength").replace("{{CONTENT}}", content).replace("{{SEARCH}}", search_html).replace("{{TOC}}", "").replace("{{BASE_URL}}", "./")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Include future-dated posts")
    args = parser.parse_args()

    if os.path.exists(SITE_DIR):
        shutil.rmtree(SITE_DIR)
    os.makedirs(SITE_DIR)

    shutil.copy("style.css", os.path.join(SITE_DIR, "style.css"))

    if os.path.exists("assets"):
        shutil.copytree("assets", os.path.join(SITE_DIR, "assets"))

    today = date.today()
    posts = []
    for fname in sorted(os.listdir(POSTS_DIR)):
        if not fname.endswith(".md") or fname.startswith("DRAFT-") or fname.startswith("TEMPLATE-") or fname == "PLANNING.md":
            continue
        slug, title, post_date, page = build_post(os.path.join(POSTS_DIR, fname))
        if not args.all and post_date and date.fromisoformat(post_date) > today:
            print(f"Skipping future post: {fname} ({post_date})")
            continue
        posts.append((slug, title, post_date, page))

    posts.sort(key=lambda p: p[2] or "", reverse=True)

    for slug, title, post_date, page in posts:
        post_dir = os.path.join(SITE_DIR, slug)
        os.makedirs(post_dir)
        open(os.path.join(post_dir, "index.html"), "w").write(page)

    open(os.path.join(SITE_DIR, "index.html"), "w").write(build_index([(s, t, d) for s, t, d, _ in posts]))
    print(f"Built {len(posts)} post(s) -> {SITE_DIR}/")


if __name__ == "__main__":
    main()
