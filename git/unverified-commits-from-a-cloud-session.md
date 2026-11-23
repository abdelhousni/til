# Signed commits shown as "Unverified" on GitHub: the signature is checked against the committer

Commits pushed from a Claude Code cloud session (Claude Code running in a container hosted by Anthropic rather than on my machine) showed an orange **Unverified** badge in every pull request of this repository. They weren't unsigned. They were signed with a key that belongs to Claude's GitHub account, and they named me as the committer. GitHub checks a signature against the committer, so it found a key it couldn't tie to that person.

Two terms first. Every commit records an **author** (who wrote the change) and a **committer** (who made the commit); [`git config user.email` isn't the identity Git commits with](git-config-user-email-is-not-the-commit-identity.md) shows where each one comes from. A **signature** is a block stored in the commit, made with a private key, that anyone holding the matching public key can check. Git can sign with a GPG key or, as here, with an SSH key.

## What GitHub shows, and why

GitHub's [About commit signature verification](https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification) page gives three default statuses:

| Status | Meaning, in GitHub's words |
|---|---|
| Verified | "The commit is signed and the signature was successfully verified." |
| Unverified | "The commit is signed but the signature could not be verified." |
| No verification status | "The commit is not signed." |

So an unsigned commit gets no badge at all, unless its committer or author turned on [vigilant mode](https://docs.github.com/en/authentication/managing-commit-signature-verification/displaying-verification-statuses-for-all-of-your-commits). The orange badge means a signature is there and GitHub couldn't verify it.

The REST API gives the reason. For a public repository it needs no token:

```sh
curl -s https://api.github.com/repos/abdelhousni/til/commits/<sha> | jq .commit.verification
```

For one of the Unverified commits (I left `signature` and `payload` out):

```json
{
  "verified": false,
  "reason": "unknown_key",
  "verified_at": null
}
```

The [REST documentation](https://docs.github.com/en/rest/commits/commits#get-a-commit) defines `unknown_key` as "The key that made the signature has not been registered with any user's account". Its other reasons name the committer explicitly, for example `no_user`: "No user was associated with the committer email address in the commit." The author plays no part in the check.

## Where the signature and the committer came from

In the session, Git's configuration showed that every commit is signed:

```sh
git config --show-origin --get-regexp 'gpg|sign|user\.'
```

```text
file:/root/.gitconfig	user.name Claude
file:/root/.gitconfig	user.email noreply@anthropic.com
file:/root/.gitconfig	user.signingkey /home/claude/.ssh/commit_signing_key.pub
file:/root/.gitconfig	gpg.format ssh
file:/root/.gitconfig	gpg.ssh.program /tmp/code-sign
file:/root/.gitconfig	commit.gpgsign true
```

`commit.gpgsign true` signs every commit, `gpg.format ssh` makes it an SSH signature, and `gpg.ssh.program` names the program Git calls to produce it ([`git-config(1)`](https://git-scm.com/docs/git-config)). The private key isn't in the container: the Claude Code documentation says "git credentials and signing keys stay outside the sandbox" ([Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web)), and the public key file above is empty.

The signature is visible in the raw commit:

```sh
git cat-file commit HEAD
```

```text
author abdelhousni <23284113+abdelhousni@users.noreply.github.com> 1795465112 +0000
committer abdelhousni <23284113+abdelhousni@users.noreply.github.com> 1795465112 +0000
gpgsig -----BEGIN SSH SIGNATURE-----
 U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAg...
 -----END SSH SIGNATURE-----
```

The committer was me because I had set `GIT_COMMITTER_NAME` and `GIT_COMMITTER_EMAIL` in the cloud environment's variables, next to `GIT_AUTHOR_NAME` and `GIT_AUTHOR_EMAIL`, so that commits would carry my identity and not `Claude <noreply@anthropic.com>`. The result was a commit signed with Claude's key and committed in my name, and my GitHub account doesn't hold that key.

## Three commits, three answers

All three from the API call above, on 2026-11-23:

| Commit | Author | Committer | `verified` | `reason` |
|---|---|---|---|---|
| `99cf69d`, from a cloud session | me | me | `false` | `unknown_key` |
| `8b5356a`, from a cloud session in September, before I set the committer variables | me | Claude | `true` | `valid` |
| `ea9a337`, a squash merge made by GitHub | me | GitHub | `true` | `valid` |

A *squash merge* is GitHub combining a pull request's commits into one new commit on the target branch. GitHub makes that commit itself and signs it: "GitHub will automatically use GPG to sign commits you make using the web interface" (same About page). That is why `main` showed Verified all along and only the commits inside pull requests didn't.

## The fix: keep the author, give the committer back

Only the committer has to match the key. The lasting fix is to remove the two committer variables from the environment's settings and keep the two author variables. For a commit in a session that still has them, `env -u` runs a command without the named variables:

```sh
env -u GIT_COMMITTER_NAME -u GIT_COMMITTER_EMAIL git commit -m "..."
git log -1 --format='author=%an <%ae>%ncommitter=%cn <%ce>'
```

```text
author=abdelhousni <23284113+abdelhousni@users.noreply.github.com>
committer=Claude <noreply@anthropic.com>
```

Pushed, that commit (`96c5254`) came back as `"verified": true, "reason": "valid"`, with me as its author and the `claude` account as its committer. GitHub's commit list shows it as "abdelhousni authored and claude committed".

What didn't work, or wasn't available:

- **Making Claude the author too**, with `git commit --amend --reset-author`. It gives Verified as well, but the commit then no longer says who it belongs to.
- **Signing with my own key.** The session's signing program and key are outside the container, and a personal private key doesn't belong in one.
- **Fixing the commits already pushed.** Changing a committer rewrites the commit, which means a force push ([what that does to other clones](resync-clone-after-force-push.md)). The ones already merged are covered by the squash commit on `main`.

One thing can't be checked from inside the session: `git log --show-signature` fails with `gpg.ssh.allowedSignersFile needs to be configured and exist for ssh signature verification`, because Git has no list of trusted SSH keys there. GitHub's answer is the one that counts for the badge.

## Sources

- [About commit signature verification](https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification), GitHub Docs: the statuses, SSH signatures, commits signed by GitHub.
- [Displaying verification statuses for all of your commits](https://docs.github.com/en/authentication/managing-commit-signature-verification/displaying-verification-statuses-for-all-of-your-commits), GitHub Docs: vigilant mode.
- [REST API endpoints for commits](https://docs.github.com/en/rest/commits/commits#get-a-commit), GitHub Docs: the `verification` object and its `reason` values.
- [`git-config(1)`](https://git-scm.com/docs/git-config): `commit.gpgSign`, `gpg.format`, `gpg.ssh.program`, `user.signingKey`.
- [Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web), "Security and isolation": where the signing keys are. It doesn't say which identity the key belongs to; the three API answers above are the evidence for that.

Commands ran with Git 2.43.0 in a Claude Code cloud session on 2026-11-23. I didn't test a commit signed on my own machine.
