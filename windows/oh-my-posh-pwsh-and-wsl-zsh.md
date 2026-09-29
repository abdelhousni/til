# Oh My Posh in PowerShell and in WSL2 zsh, with one config file

[Oh My Posh](https://ohmyposh.dev/) draws the same prompt in any shell from one JSON config. On a Windows machine with WSL2, that means PowerShell and the Linux zsh can share a prompt. There are two installs, one font, and one file. Tested with Oh My Posh 29.14, PowerShell 7.6 and zsh 5.9.

## Install

Windows, for PowerShell:

```powershell
winget install JanDeDobbeleer.OhMyPosh --source winget
```

WSL2, for zsh. The script installs into `~/bin` or `~/.local/bin`, whichever exists; that directory must be on your `PATH`:

```sh
curl -s https://ohmyposh.dev/install.sh | bash -s
```

## The font goes on Windows, not in WSL

Branch and folder icons need a [Nerd Font](https://www.nerdfonts.com/). Windows Terminal draws the WSL shell too, so install the font once, on the Windows side:

```powershell
oh-my-posh font install meslo
```

Then set it in Windows Terminal, under *Settings → Profiles → Defaults → Appearance → Font face*. Pick `MesloLGM Nerd Font` there, for PowerShell and every WSL profile. A font installed inside WSL is never used. The docs say fonts "need to be installed on the host system as this is a UI setting".

## A small config with a few segments

Save this as `%UserProfile%\my.omp.json`. WSL can read it as `/mnt/c/Users/<you>/my.omp.json`.

```json
{
  "$schema": "https://raw.githubusercontent.com/JanDeDobbeleer/oh-my-posh/main/themes/schema.json",
  "version": 3,
  "final_space": true,
  "blocks": [
    {
      "type": "prompt",
      "alignment": "left",
      "segments": [
        { "type": "session", "style": "plain", "foreground": "yellow",
          "template": "{{ if .SSHSession }}{{ .UserName }}@{{ .HostName }} {{ end }}" },
        { "type": "path", "style": "plain", "foreground": "blue",
          "options": { "style": "agnoster_short", "max_depth": 3 },
          "template": "{{ .Path }} " },
        { "type": "git", "style": "plain", "foreground": "magenta",
          "options": { "fetch_status": true },
          "template": "{{ .HEAD }}{{ if .Working.Changed }} *{{ end }} " },
        { "type": "status", "style": "plain", "foreground": "red",
          "template": "{{ if .Error }}✘ {{ .Code }} {{ end }}" },
        { "type": "text", "style": "plain", "foreground": "green", "template": "❯" }
      ]
    },
    {
      "type": "prompt",
      "alignment": "right",
      "segments": [
        { "type": "executiontime", "style": "plain", "foreground": "darkGray",
          "options": { "threshold": 2000, "style": "round" },
          "template": "{{ .FormattedMs }}" }
      ]
    }
  ]
}
```

| Segment | Shows |
|---|---|
| `session` | `user@host`, only over SSH (`.SSHSession`) |
| `path` | The last 3 directories |
| `git` | The branch, and `*` when the working tree has changes (`fetch_status`) |
| `status` | `✘` and the exit code, only after a failed command |
| `executiontime` | On the right, the duration of commands that took over 2 s |

Rendered in `~/src/demo`, a git repository with an uncommitted change, after a 5-second command that exited with 3 (the space before `master` is the branch icon):

```text
~/src/demo  master * ✘ 3 ❯                                5s
```

The segment types and their options are listed in the [docs](https://ohmyposh.dev/docs/segments/system/path). The `$schema` line gives completion in VS Code.

## Load it in each shell

PowerShell: add this line to `$PROFILE`, then run `. $PROFILE`:

```powershell
oh-my-posh init pwsh --config "$env:USERPROFILE\my.omp.json" | Invoke-Expression
```

zsh: add this line to `~/.zshrc`, then run `exec zsh`:

```sh
eval "$(oh-my-posh init zsh --config /mnt/c/Users/<you>/my.omp.json)"
```

Both shells read the same file at each prompt, so an edit shows up in both at their next prompt. To avoid reading the config through `/mnt/c` on every prompt, copy it into WSL instead.

With Oh My Zsh, leave `ZSH_THEME=""` and put the `eval` line after `source $ZSH/oh-my-zsh.sh`, so Oh My Posh sets the prompt last.

## Sources

- Oh My Posh docs:
  - [Windows](https://ohmyposh.dev/docs/installation/windows) and [Linux](https://ohmyposh.dev/docs/installation/linux) installation;
  - [prompt setup](https://ohmyposh.dev/docs/installation/prompt) and [fonts](https://ohmyposh.dev/docs/installation/fonts).
- Tested with `oh-my-posh print primary`, and through the zsh and pwsh init scripts, with the config above.
