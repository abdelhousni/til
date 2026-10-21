# Uploading files larger than Artifactory's upload limit

Artifactory's **File Upload Max Size** (Administration → General → Settings, 100 MB by default) caps uploads made through the **web UI** only. Every other way in deploys through the REST API, which that setting doesn't touch.

| Method | Command | Why it gets through |
|---|---|---|
| JFrog CLI | `jf rt upload big.iso generic-local/isos/` | REST API; files over 200 MB are sent in parallel chunks (multipart upload), tuned with `--min-split` and `--split-count`, when the storage is S3-compatible |
| curl | `curl -u user:token -T big.iso https://company.jfrog.io/artifactory/generic-local/isos/big.iso` | Plain `PUT` to the [Deploy Artifact](https://jfrog.com/help/r/jfrog-rest-apis/deploy-artifact) endpoint |
| Checksum deploy | same `curl -X PUT`, no body, with `-H "X-Checksum-Deploy: true" -H "X-Checksum-Sha1: $(sha1sum big.iso \| cut -d' ' -f1)"` | Nothing is transferred if Artifactory already stores a binary with that checksum; it only adds a path pointing to it |
| Archive deploy | `curl -T bundle.zip -H "X-Explode-Archive: true" …/generic-local/dir/` | One upload of an archive, expanded server side into its files |
| Package clients | `mvn deploy`, `npm publish`, `docker push`, `helm push`… | Each speaks its repository's API; `docker push` additionally sends each layer separately, in chunks |

A token is an access token or API key generated in the user profile; `-T` makes curl send the file as the body of a `PUT`.

## When it still fails

A `413 Request Entity Too Large` outside the UI comes from in front of Artifactory, not from it: a reverse proxy's body limit, such as nginx's `client_max_body_size`, or a load balancer's timeout on a long upload. Raise it there; the CLI's chunked upload also helps, since each request stays small.

*The commands weren't run against an Artifactory instance; they follow the JFrog REST API and CLI documentation.*
