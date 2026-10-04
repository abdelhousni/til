# Adding a certificate to a Java keystore/truststore with keytool

`keytool` ships with every OpenJDK install — no separate package needed. It manages both kinds of Java cert stores: a **keystore** (holds a private key plus its certificate, for a service presenting TLS) and a **truststore** (just trusted CA certificates, so the JVM knows who to trust when *connecting* to something). Same file format, same command, different purpose — most commonly you're adding a CA cert to a truststore so a Java app stops rejecting your internal PKI.

## Import a CA certificate into the JVM-wide truststore

The JVM-wide truststore is a file named `cacerts`, in `$JAVA_HOME/lib/security/`:

```sh
keytool -importcert -trustcacerts \
  -alias my-internal-ca \
  -file myca.crt \
  -keystore "$JAVA_HOME/lib/security/cacerts" \
  -storepass changeit
```

`keytool -cacerts` is a shorter way to name the same file, in place of `-keystore "$JAVA_HOME/lib/security/cacerts"`. It'll show the cert's fingerprint and ask "Trust this certificate?" — add `-noprompt` to skip that when running non-interactively, e.g. from a shell script or an Ansible task.

`changeit` is the default password of a JKS `cacerts`. Whether your `cacerts` is JKS depends on where your JDK came from (next section). On a password-less one, `-storepass changeit` is simply ignored, so the command above works with both.

Verify it landed:

```sh
keytool -list -keystore "$JAVA_HOME/lib/security/cacerts" -storepass changeit -alias my-internal-ca -v
```

## Which `cacerts` you have depends on where your JDK came from

There are two keystore formats: **JKS**, Java's own, and **PKCS12**, the standard format other tools read too. OpenJDK changed the format of the `cacerts` it ships in JDK 18 (JDK-8275253, *Migrate cacerts from JKS to password-less PKCS12*), but Linux distributions replace that file with their own. Four JDKs, checked with `keytool -list -cacerts` on 2026-10-04:

| JDK | `cacerts` | Format | Password |
|---|---|---|---|
| Temurin 17 (upstream build) | the file in the JDK | JKS | `changeit`, required |
| Temurin 21 (upstream build) | the file in the JDK | PKCS12 | none: any password, or none, works |
| Ubuntu 24.04 `openjdk-21-jre-headless` | a symlink to `/etc/ssl/certs/java/cacerts`, from `ca-certificates-java` | JKS | `changeit`, required |
| Fedora 44 `java-25-openjdk-headless` | a symlink to `/etc/pki/ca-trust/extracted/java/cacerts`, from `ca-certificates` | JKS | `changeit`, required |

On the password-less PKCS12 store, importing with `-storepass changeit` didn't add a password: the store still listed without one afterwards. A wrong password on a JKS store stops `keytool` with *"Keystore was tampered with, or password was incorrect"*.

`keytool` reads the format of an existing file itself, so importing into `cacerts` works the same on all four, with no `-storetype`.

## New keystores are PKCS12, whatever `cacerts` is

Since JDK 9 (JEP 229, *Create PKCS12 Keystores by Default*), `keytool` creates **new** keystores as PKCS12. Creating an app-specific truststore from scratch —

```sh
keytool -importcert -alias my-internal-ca -file myca.crt -keystore my-app-truststore
```

— produces a PKCS12 file even with no `.p12` extension and no format mentioned anywhere in the command; Temurin 17 and 21 both did. That's fine for the JVM (it reads PKCS12 truststores natively), but it'll surprise you if some other tool or script assumes anything ending in `truststore` must be JKS, as the distributions' own `cacerts` still is. Pin it explicitly either way if it matters: `-storetype PKCS12` or `-storetype JKS`.

## On a distribution JDK, add the CA to the system trust store

On Ubuntu and Fedora, `cacerts` is generated from the system's trust store, the CA certificates every program on the machine trusts. A `keytool` import into it may not last:

- **Fedora:** a certificate imported with `keytool` was gone after the next `update-ca-trust extract`, which rebuilds the file from scratch.
- **Ubuntu:** it survived `update-ca-certificates`, even with `--fresh`: `ca-certificates-java` only adds and removes the system's certificates.

The way that lasts on both is the system trust store, which also makes the CA trusted by everything else on the machine:

```sh
# Fedora, RHEL
sudo cp myca.crt /etc/pki/ca-trust/source/anchors/my-internal-ca.crt
sudo update-ca-trust extract

# Debian, Ubuntu
sudo cp myca.crt /usr/local/share/ca-certificates/my-internal-ca.crt
sudo update-ca-certificates
```

Either way the CA appeared in Java's `cacerts`, under an alias the tool picked: `myinternalca` on Fedora, `debian:my-internal-ca.pem` on Ubuntu.

## Replacing an existing alias

`keytool` refuses to import over an alias that's already there ("Certificate not imported, alias `<alias>` already exists"). Delete first, then re-import:

```sh
keytool -delete -alias my-internal-ca -keystore "$JAVA_HOME/lib/security/cacerts" -storepass changeit
```

## It's not always the JVM-wide store

Plenty of Java apps (Tomcat, Kafka clients, anything with its own `-Djavax.net.ssl.trustStore=...` setting) keep a separate, app-specific truststore instead of relying on the shared `cacerts`. Same `keytool -importcert` command — just point `-keystore` at that app's file instead of `$JAVA_HOME/lib/security/cacerts`, and restart the app afterward, since it's loaded into memory once at startup, not re-read live.

## Sources

- OpenJDK bug tracker: [JDK-8275253](https://bugs.openjdk.org/browse/JDK-8275253), *Migrate cacerts from JKS to password-less PKCS12*, fix version 18; [JDK-8044445](https://bugs.openjdk.org/browse/JDK-8044445), *JEP 229: Create PKCS12 Keystores by Default*, fix version 9.
- Tested on 2026-10-04 with Eclipse Temurin 17.0.20.1 and 21.0.12.1, Ubuntu 24.04's `openjdk-21-jre-headless` with `ca-certificates-java`, and Fedora 44's `java-25-openjdk-headless` 25.0.4.1 with `ca-certificates` 2026.2.90, the last two in containers.
