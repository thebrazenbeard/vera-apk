# Vera Phone: private local inference (V2 experimental)

This APK is a **response-only companion**. It does not possess Vera's identity,
vault key, goal or effect authority, and it never directly exposes Ollama.

## Topology

```
Android + Tailscale
  -> HTTPS https://lappy.<tailnet>.ts.net:8443 (tailnet-only Tailscale Serve)
  -> 127.0.0.1:18777 (separate token-authenticated Vera gateway)
  -> 127.0.0.1:11434 (local Ollama)
```

**The Synology NAS is not required for the first route.** The existing
Synology/Tailscale path can remain a network member without acting as a relay;
Tailscale already handles direct or DERP connectivity. No router port forward,
public DNS A record, public Funnel, or raw Ollama port exposure is permitted.

## Lappy setup

Use a trusted, interactive PowerShell on Lappy. The source is
`gateway/vera_inference_gateway.py`. First provision a per-phone token in a
private local file (do not commit or publish it). Create it once using Python:

```powershell
$p = Join-Path $env:LOCALAPPDATA 'VeraPhoneGateway\pairing-token.txt'
New-Item -ItemType Directory -Path (Split-Path $p) -Force | Out-Null
if (!(Test-Path $p)) {
    py -3 -c "import secrets,pathlib,os; p=pathlib.Path(os.environ['LOCALAPPDATA'])/'VeraPhoneGateway'/'pairing-token.txt'; p.write_text(secrets.token_urlsafe(36), encoding='ascii')"
}
icacls $p /inheritance:r /grant:r "$($env:USERNAME):(R)" "SYSTEM:(F)" "Administrators:(F)"
```

The token must be copied **privately from Lappy to the phone**; never publish it
in a chat, PR, screenshot or Blotter. Keep the secret file outside the repository.

Start the gateway while logged in:

```powershell
py -3 D:\VERA\vera-apk-phone-20261028\gateway\vera_inference_gateway.py --token-file "$env:LOCALAPPDATA\VeraPhoneGateway\pairing-token.txt"
```

The gateway binds only to **127.0.0.1:18777**. In a second PowerShell,
add a separate HTTPS listener without replacing existing Tailscale Serve routes:

```powershell
& "C:\Program Files\Tailscale\tailscale.exe" serve --bg --https=8443 http://127.0.0.1:18777
& "C:\Program Files\Tailscale\tailscale.exe" serve status
```

Test the live gateway and bad-token rejection before relying on it. Running
the foreground process is not proof of automatic startup across logout/reboot;
a separate, reviewed Windows scheduled task or service is necessary for that.

## Samsung Galaxy phone setup

1. Install Tailscale on the phone, sign into the **same tailnet**, and enable it.
2. Download the `vera-companion-debug` artifact from the successful exact-commit
   GitHub Actions run in this repository. Inside the ZIP is `app-debug.apk`.
3. Install the APK (Android may require granting your file manager permission
   to install unknown apps). This is a development-signed APK, not a Play Store release.
4. Enter `https://lappy.<tailnet>.ts.net:8443` as the endpoint and enter the
   privately transferred token; tap **SAVE** then **CONNECT**.
5. Select a model, write a prompt and tap **SEND**. All messages stay in volatile
   UI memory and are sent only by explicit user action; **UNPAIR** removes stored
   credentials. To revoke a compromised phone, rotate the token on Lappy.

## Security & currentness

- Only HTTPS `.ts.net` hostnames on ports 443/8443 are accepted by the APK.
- TLS certificate/hostname validation uses the Android system trust manager.
  Redirects, HTTP cleartext and public-host fallback are disabled.
- Bearer pairing token is encrypted using Android Keystore AES-GCM, with
  backup disabled and no secret logging.
- The gateway also verifies the bearer token, restricts endpoint paths and
  model inventory, rejects system/tool messages and limits request size.
- No backend writes, agent tool invocation, memory integration, or autonomous
  tasks are available. Android cache and chat UI are not Vera canonical memory.
- Tailnet ACLs should restrict this host/port to the user's phone device.
- A passing APK build qualifies **packaging**, not actual Galaxy installation.
- A successful Lappy loopback test qualifies **local inference**, not remote
  Android/Tailscale connectivity. Phone network and user credential installation
  still require device-level testing.

**Existing Vera UI at 127.0.0.1:8788 is deliberately not proxied.**
