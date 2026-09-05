# Getting a remote file's properties with curl, without downloading it

A `GET` request pulls the whole body. Most of the time I actually want is in the headers — size, type, whether it changed — and there's a way to get each of those without pulling anything.

## Headers only: `-I`

```sh
curl -I https://example.com/file.zip
```

Uses an actual HTTP `HEAD` request, so the server (in theory) sends the same headers a `GET` would, minus the body. In practice not every server implements HEAD faithfully — some return a different `Content-Length` than the real GET would, or skip headers that only get computed while generating the body. If something looks off, cross-check with `curl -s -o /dev/null -w` (below) against a real GET.

## The exact field you want, nothing else: `-w`/`--write-out`

Rather than piping `-I` output through `grep`, ask curl for one specific value:

```sh
curl -s -o /dev/null -w '%{content_type} %{size_download} %{http_code}\n' https://example.com/file.zip
```

`-o /dev/null` throws the body away, `-s` silences the progress meter, and `-w` prints exactly the fields asked for. Useful ones: `content_type`, `size_download`, `http_code`, `time_total`, `filename_effective` (the final URL after redirects, handy when scripting against a link that might bounce somewhere else).

## Only fetch it if it changed: `-z`

```sh
curl -z ~/.cache/file.zip -o file.zip https://example.com/file.zip
```

`-z` takes either a date string or, as here, an existing local file — curl reads that file's mtime and only downloads if the remote copy is newer (`If-Modified-Since` under the hood). Prefix the value with `-` to invert it and match files *older* than the given time instead of newer.

## Keep the remote timestamp after downloading: `-R`

```sh
curl -R -o file.zip https://example.com/file.zip
```

Sets the downloaded file's local mtime to match the server's `Last-Modified` header, instead of "just now." Combine it with `-z` above and repeated runs of the same command become a proper incremental sync: skip if unchanged, and the local timestamp stays accurate when it does download.

## Use the server's suggested filename: `-J -O`

```sh
curl -J -O https://example.com/download?id=42
```

`-O` alone saves using the URL's own basename — which is useless for a URL like that one. `-J` tells curl to read the `Content-Disposition` header instead and use whatever filename the server actually suggests.

## Check just a byte range, without the whole file: `-r`

```sh
curl -r 0-99 -o first-100-bytes https://example.com/file.zip
```

Handy for peeking at a file's format (magic bytes) or confirming a server actually supports partial content (`Accept-Ranges: bytes` in a `-I` response) before committing to a resumable download.
