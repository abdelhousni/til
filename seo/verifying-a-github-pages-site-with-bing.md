# Verifying a GitHub Pages site with Bing Webmaster Tools (no DNS needed)

Bing Webmaster Tools also feeds DuckDuckGo and Yahoo results, so submitting a sitemap there covers more ground than just Google — worth doing once a sitemap already exists. The usual way to prove ownership of a site is a DNS TXT record, but that assumes you control the domain's DNS. A `username.github.io` site doesn't give you that (GitHub owns the DNS zone), so the DNS method is a dead end here.

The fallback that does work for GitHub Pages: a static meta tag on the homepage. Bing Webmaster Tools gives you a code like:

```html
<meta name="msvalidate.01" content="B109FF34ED264CD7CDA115D1B13A4C7F">
```

which just needs to appear in `index.html`'s `<head>` — no verification file upload, no DNS access required, and importantly no JavaScript, so it doesn't add any tracking behavior to the page. I added it as one more constant in the build script, alongside the description and canonical tags already generated there:

```python
BING_VERIFICATION_CODE = "B109FF34ED264CD7CDA115D1B13A4C7F"
```

templated into `index.html` only — Bing's instructions specifically ask for the homepage, not every page.

One detail worth remembering: this tag only proves ownership. It doesn't submit anything by itself — after Bing confirms the tag is live and you click "Verify," you still go to the Sitemaps section and paste in the sitemap URL separately. The two steps are independent.
