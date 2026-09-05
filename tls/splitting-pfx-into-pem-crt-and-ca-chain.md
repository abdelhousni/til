# Splitting a .pfx into a certificate, key, and CA chain with openssl

A `.pfx`/`.p12` file bundles a certificate, its private key, and (usually) the CA chain into one password-protected file — common on Windows and from some CAs. Most Linux tools (nginx, Apache, HAProxy) want those as separate PEM files instead, so it needs splitting apart.

## The three extractions

```sh
# the certificate itself, no key
openssl pkcs12 -in cert.pfx -clcerts -nokeys -out cert.crt

# the private key, unencrypted
openssl pkcs12 -in cert.pfx -nocerts -noenc -out cert.key

# just the CA chain, no client cert or key
openssl pkcs12 -in cert.pfx -cacerts -nokeys -out ca.pem
```

Each will prompt for the PFX's export password. `-clcerts` means "client certificate" (the leaf cert, not any CA certs in the bundle), `-cacerts` is the opposite, and `-nokeys`/`-nocerts` filter out whichever of the other two you don't want in that particular output file.

If a server wants the leaf certificate and the CA chain concatenated into one "fullchain" file (nginx's `ssl_certificate` directive expects exactly this):

```sh
cat cert.crt ca.pem > fullchain.pem
```

## `-noenc`, not `-nodes`

Most guides you'll find online say `-nodes` for an unencrypted private key output. That flag is deprecated as of OpenSSL 3.0 in favor of `-noenc` — it still works for now, but `-noenc` is the one that won't eventually disappear. If your key needs to stay encrypted (some tools require it, and you'll supply the passphrase at service start instead of baking it in unencrypted), just drop `-noenc` entirely — OpenSSL 3.0 encrypts private key output with AES-256-CBC by default, versus 1.1.1's weaker 3DES default.

## The other OpenSSL 3.0 gotcha: `-legacy`

A `.pfx` exported years ago by an old Windows box or IIS often used RC2-40-CBC or 3DES for its internal encryption — algorithms OpenSSL 3.0 moved out of its default provider set. Trying to read one of these without warning fails with something like `Mac verify error: invalid password?` even though the password is correct. The fix is adding `-legacy` to load the legacy provider:

```sh
openssl pkcs12 -in old-export.pfx -legacy -clcerts -nokeys -out cert.crt
```

## Confirming the key actually matches the cert

After splitting, it's worth checking the key and certificate are actually a pair — trivial to end up with the wrong key file if you're juggling several exports. Compare the modulus hash of each:

```sh
openssl x509 -noout -modulus -in cert.crt | openssl md5
openssl rsa  -noout -modulus -in cert.key | openssl md5
```

Same output on both lines means they match. (For an EC key, swap `openssl rsa` for `openssl ec` — the modulus check is RSA-specific.)
