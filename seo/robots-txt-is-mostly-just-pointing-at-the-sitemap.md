# robots.txt for a small static site is basically a pointer to the sitemap

I'd assumed `robots.txt` needed some thought — which paths to block, which crawlers to allow or disallow. For a small public site with nothing private on it, it turns out to be three lines:

```
User-agent: *
Allow: /

Sitemap: https://til.housni.eu/sitemap.xml
```

`Allow: /` for every user-agent just states explicitly what's already true by default (nothing is disallowed) — it costs nothing and removes any ambiguity for a crawler that expects an explicit rule. The `Sitemap:` line is the part that actually does something: it tells any crawler that fetches `robots.txt` (which most do, first, before crawling anything else) exactly where to find the full list of URLs, without it needing to guess a filename or wait for you to submit it manually everywhere.

Generated it as a one-line format call alongside the sitemap, since it references the same `SITE_URL` constant everything else in the build already uses:

```python
ROBOTS_TXT = """User-agent: *
Allow: /

Sitemap: {site_url}/sitemap.xml
"""
```

One condition for any of this to count: the file has to sit at the root of the host. [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309) says *"The rules MUST be accessible in a file named "/robots.txt" (all lowercase) in the top-level path of the service."* While this site lived at `abdelhousni.github.io/til/`, its `robots.txt` was at `/til/robots.txt`, where no crawler looks. The host root, `abdelhousni.github.io/robots.txt`, returned 404, so the `Sitemap:` line was never read there. Moving the site to its own domain, `til.housni.eu`, put the file at `/robots.txt`, where it works. For a project site on `github.io`, submit the sitemap to search engines directly instead.

The lesson: don't reach for a robots.txt generator or complicate this file speculatively. If you have nothing to hide from crawlers, the file's only real job is pointing them at your sitemap.
