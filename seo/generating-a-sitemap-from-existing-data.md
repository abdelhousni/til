# Don't hand-write a sitemap.xml, generate it from data you already have

A `sitemap.xml` just tells crawlers every URL on your site plus when it last changed, so they don't have to discover pages purely by following links. For a static site build script, there's no reason to maintain one by hand — it's a direct transformation of data the build already collects.

My `build_site.py` was already accumulating an `all_entries` list (title, date, url) for every TIL page, to build the topic index and the Atom feed. The sitemap is just another view of the same list:

```python
def build_sitemap(all_entries):
    urls = [SITEMAP_URL_TEMPLATE.format(loc=f"{SITE_URL}/", lastmod=max(e["date"] for e in all_entries))]
    urls += [
        SITEMAP_URL_TEMPLATE.format(loc=e["url"], lastmod=e["date"])
        for e in sorted(all_entries, key=lambda e: e["url"])
    ]
    return SITEMAP_TEMPLATE.format(urls="\n".join(urls))
```

producing:

```xml
<?xml version="1.0" encoding="utf-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url>
<loc>https://abdelhousni.github.io/til/proxmox/ripe-atlas-software-probe-lxc.html</loc>
<lastmod>2026-09-05</lastmod>
</url>
</urlset>
```

Every new TIL entry gets picked up automatically on the next build — there's no separate step to remember, and no chance of the sitemap drifting out of sync with what the site actually contains, because it's derived from the same source of truth as everything else.

I validated it the same boring way as the Atom feed: `xml.dom.minidom.parse()` on the output. If it parses, it's well-formed enough for a crawler to read.
