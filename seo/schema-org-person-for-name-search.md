# A schema.org Person block is what actually helps you rank for your own name

I wanted my TIL site to show up when someone searches my name, and went looking for an "SEO script" to do it. There isn't one — nothing you paste in makes a search engine rank you first. What actually helps is giving it structured, machine-readable proof of *who a page belongs to*, so it can confidently attach your name to it.

The relevant piece is a [schema.org](https://schema.org/Person) `Person` block, embedded as JSON-LD in the page `<head>`:

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Person",
  "name": "Abdellatif Housni",
  "url": "https://abdelhousni.github.io/til/",
  "sameAs": [
    "https://github.com/abdelhousni",
    "https://www.linkedin.com/in/abdelhousni/"
  ]
}
</script>
```

Two things matter more than they look like they should:

- **`name` has to match exactly what people type.** A search for "Abdellatif Housni" won't connect to a page whose structured data says "Abdel Housni" — the whole point is a literal string match a search engine can trust.
- **`sameAs` is not decorative.** It tells the search engine "this URL and these other URLs are the same entity." Linking your GitHub and LinkedIn profiles here is what lets it merge signals from multiple places into one confident identity, instead of treating your TIL site as an unrelated stranger to your other public profiles.

I generate this at build time in Python rather than hand-writing HTML, since a dict serialized with `json.dumps()` is much harder to get subtly wrong than string-templating quotes into JSON by hand:

```python
def build_person_schema():
    data = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": SITE_AUTHOR,
        "url": f"{SITE_URL}/",
        "sameAs": AUTHOR_SAME_AS,
    }
    return f'<script type="application/ld+json">\n{json.dumps(data, indent=2)}\n</script>'
```

No tracking, no third party involved — it's static JSON sitting in the page, same as any other meta tag.
