# Adding a certificate to a Java keystore/truststore with keytool

`keytool` ships with every OpenJDK. It manages two kinds of store with the same file format: a **keystore** (a private key and its certificate, for a service presenting TLS) and a **truststore** (trusted CA certificates, for a JVM connecting to something). The usual job: add your internal CA to a truststore so a Java app stops rejecting your PKI.

## First, find out which `cacerts` you have

The JVM-wide truststore is `$JAVA_HOME/lib/security/cacerts`. Its format and password depend on where the JDK came from:

| JDK | `cacerts` | Format | Password |
|---|---|---|---|
| Upstream build, JDK 17 or older (Temurin 17) | in the JDK | JKS | `changeit` |
| Upstream build, JDK 18 or newer (Temurin 21) | in the JDK | PKCS12 | none |
| Debian, Ubuntu package (24.04, OpenJDK 21) | link to `/etc/ssl/certs/java/cacerts` | JKS | `changeit` |
| Fedora, RHEL package (Fedora 44, OpenJDK 25) | link to `/etc/pki/ca-trust/extracted/java/cacerts` | JKS | `changeit` |

OpenJDK moved its own `cacerts` to password-less PKCS12 in JDK 18 (JDK-8275253); distributions replace it with a JKS file generated from the system trust store. Check yours:

```sh
ls -l "$JAVA_HOME/lib/security/cacerts"         # a link means a distribution package
keytool -list -cacerts -storepass changeit | head -1   # Keystore type: JKS or PKCS12
```

## Distribution JDK: add the CA to the system trust store

This makes the CA trusted by Java and by everything else on the machine, and survives updates:

```sh
# Fedora, RHEL
sudo cp myca.crt /etc/pki/ca-trust/source/anchors/my-internal-ca.crt
sudo update-ca-trust extract

# Debian, Ubuntu
sudo cp myca.crt /usr/local/share/ca-certificates/my-internal-ca.crt
sudo update-ca-certificates
```

Don't `keytool -importcert` into a distribution's `cacerts`: on Fedora, the next `update-ca-trust extract` deleted the imported certificate. (Ubuntu's `update-ca-certificates` kept it, but the system route works on both.)

## Upstream JDK: import with keytool

```sh
keytool -importcert -trustcacerts -noprompt \
  -alias my-internal-ca -file myca.crt \
  -cacerts -storepass changeit

keytool -list -cacerts -storepass changeit -alias my-internal-ca -v   # check
```

- `-cacerts` names `$JAVA_HOME/lib/security/cacerts`; use `-keystore <file>` for any other store.
- `-noprompt` skips "Trust this certificate?", for scripts and Ansible tasks.
- `-storepass changeit` works on both formats: a password-less PKCS12 store ignores it, and importing with it doesn't add a password.
- `keytool` detects the format of an existing store, so no `-storetype` is needed.

To replace a certificate, delete the alias first; `keytool` refuses to import over an existing one:

```sh
keytool -delete -alias my-internal-ca -cacerts -storepass changeit
```

## App-specific truststores

Tomcat, Kafka clients and any app started with `-Djavax.net.ssl.trustStore=...` use their own file instead of `cacerts`. Same command, with `-keystore <that file>`, then restart the app: it reads the store once at startup.

A **new** store is created as PKCS12 since JDK 9 (JEP 229), even named `my-app-truststore` with no `.p12`. If another tool expects JKS, say so: `-storetype JKS`.

## Sources

- OpenJDK: [JDK-8275253](https://bugs.openjdk.org/browse/JDK-8275253) (*Migrate cacerts from JKS to password-less PKCS12*, JDK 18) and [JDK-8044445](https://bugs.openjdk.org/browse/JDK-8044445) (*JEP 229: Create PKCS12 Keystores by Default*, JDK 9).
- Tested on 2026-10-04: Temurin 17.0.20.1 and 21.0.12.1; Ubuntu 24.04 `openjdk-21-jre-headless` with `ca-certificates-java`; Fedora 44 `java-25-openjdk-headless` with `ca-certificates` 2026.2.90.
