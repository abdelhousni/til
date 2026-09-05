# robots.txt for a small static site is basically a pointer to the sitemap

I'd assumed `robots.txt` needed some thought — which paths to block, which crawlers to allow or disallow. For a small public site with nothing private on it, it turns out to be three lines:

```
User-agent: *
Allow: /

Sitemap: https://abdelhousni.github.io/til/sitemap.xml
```

`Allow: /` for every user-agent just states explicitly what's already true by default (nothing is disallowed) — it costs nothing and removes any ambiguity for a crawler that expects an explicit rule. The `Sitemap:` line is the part that actually does something: it tells any crawler that fetches `robots.txt` (which most do, first, before crawling anything else) exactly where to find the full list of URLs, without it needing to guess a filename or wait for you to submit it manually everywhere.

Generated it as a one-line format call alongside the sitemap, since it references the same `SITE_URL` constant everything else in the build already uses:

```python
ROBOTS_TXT = """User-agent: *
Allow: /

Sitemap: {site_url}/sitemap.xml
"""
```

The lesson: don't reach for a robots.txt generator or complicate this file speculatively. If you have nothing to hide from crawlers, the file's only real job is pointing them at your sitemap.
