# Adding a certificate to a Java keystore/truststore with keytool

`keytool` ships with every OpenJDK install — no separate package needed. It manages both kinds of Java cert stores: a **keystore** (holds a private key plus its certificate, for a service presenting TLS) and a **truststore** (just trusted CA certificates, so the JVM knows who to trust when *connecting* to something). Same file format, same command, different purpose — most commonly you're adding a CA cert to a truststore so a Java app stops rejecting your internal PKI.

## Import a CA certificate into the JVM-wide truststore

```sh
keytool -importcert -trustcacerts \
  -alias my-internal-ca \
  -file myca.crt \
  -keystore "$JAVA_HOME/lib/security/cacerts" \
  -storepass changeit
```

`changeit` is the well-known default password on the stock `cacerts` file (still true today — nobody bothers changing it, since the file only holds public certificates anyway, nothing secret). It'll show the cert's fingerprint and ask "Trust this certificate?" — add `-noprompt` to skip that when running non-interactively, e.g. from a shell script or an Ansible task.

Verify it landed:

```sh
keytool -list -keystore "$JAVA_HOME/lib/security/cacerts" -storepass changeit -alias my-internal-ca -v
```

## The gotcha: two different defaults for "keystore type"

Since JDK 9, `keytool`'s *default* format for a **newly created** keystore is PKCS12, not the older JKS. But the **system `cacerts` file that ships with the JDK is still JKS format** — a different default for a different situation. `keytool` auto-detects the type of an existing file, so importing into the stock `cacerts` above just works without specifying `-storetype`. Where it bites: creating a **new**, app-specific truststore from scratch —

```sh
keytool -importcert -alias my-internal-ca -file myca.crt -keystore my-app-truststore
```

— produces a PKCS12 file even with no `.p12` extension and no format mentioned anywhere in the command. That's fine for the JVM (it reads PKCS12 truststores natively), but it'll surprise you if some other tool or script assumes anything ending in `truststore` must be JKS. Pin it explicitly either way if it matters: `-storetype PKCS12` or `-storetype JKS`.

## Replacing an existing alias

`keytool` refuses to import over an alias that's already there ("Certificate not imported, alias `<alias>` already exists"). Delete first, then re-import:

```sh
keytool -delete -alias my-internal-ca -keystore "$JAVA_HOME/lib/security/cacerts" -storepass changeit
```

## It's not always the JVM-wide store

Plenty of Java apps (Tomcat, Kafka clients, anything with its own `-Djavax.net.ssl.trustStore=...` setting) keep a separate, app-specific truststore instead of relying on the shared `cacerts`. Same `keytool -importcert` command — just point `-keystore` at that app's file instead of `$JAVA_HOME/lib/security/cacerts`, and restart the app afterward, since it's loaded into memory once at startup, not re-read live.
