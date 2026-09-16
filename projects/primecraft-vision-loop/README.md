# Primecraft

Minimal vision first Minecraft actor. Python owns one model decision loop; the bridge owns Mineflayer, screenshots, and movement telemetry.

```powershell
$env:PRIMECRAFT_ADAPTER_URL='http://127.0.0.1:18765'
python -m primecraft.cli doctor
python -m primecraft.cli observe
$env:PRIMECRAFT_MODEL_API_KEY='...'
python -m primecraft.cli run --goal 'Reach the visible tree and return'
python -m primecraft.cli logs
```

Runs fail when no image is present; there is no silent text fallback. Configure `PRIMECRAFT_MODEL_URL` and `PRIMECRAFT_MODEL` by environment. Credentials are never stored in artifacts.
