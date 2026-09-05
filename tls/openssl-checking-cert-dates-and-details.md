# Checking a TLS certificate's dates, issuer, and SANs with openssl

A handful of `openssl x509` flags cover almost everything I need when I just want to inspect a certificate — no need to dump the whole thing with `-text` unless I'm actually debugging something structural.

## From a local file

```sh
# validity window
openssl x509 -in cert.pem -noout -dates
# notBefore=Jan 15 00:00:00 2026 GMT
# notAfter=Apr 15 23:59:59 2026 GMT

# who issued it, who it's for
openssl x509 -in cert.pem -noout -subject -issuer

# Subject Alternative Names (the hostnames it's actually valid for)
openssl x509 -in cert.pem -noout -ext subjectAltName
```

`-noout` matters on every one of these — without it, `openssl x509` also prints the PEM-encoded certificate itself before the field you asked for.

## From a live server (no file needed)

Pull the certificate straight off the wire with `s_client`, then hand it to `x509` the same way:

```sh
echo | openssl s_client -connect example.com:443 -servername example.com 2>/dev/null \
  | openssl x509 -noout -dates -subject
```

`-servername` matters if the server uses SNI to serve different certificates for different hostnames on the same IP (basically every server behind a modern reverse proxy or CDN) — without it you might get whatever the default/first certificate happens to be, not the one for the host you actually asked about. The `echo |` is just there to close `s_client`'s stdin immediately, since it otherwise waits for interactive input.

## Scripting an expiry check

`-checkend` is the flag actually built for monitoring scripts — it takes a number of seconds and exits `0` if the certificate is still valid that far in the future, `1` if it isn't, so you don't have to parse and compare dates yourself:

```sh
# will it still be valid in 14 days?
openssl x509 -in cert.pem -noout -checkend 1209600 && echo "OK" || echo "renew me"
```

That's the same check a renewal cron job needs, already exit-coded for `&&`/`||` or a shell script's `if`.
