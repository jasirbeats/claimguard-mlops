# Apply the SRE 87 control-cycle patch

```bash
unzip -o claimguard-sre87-control-cycle-patch.zip -d /tmp/claimguard-sre87
cp -a /tmp/claimguard-sre87/claimguard-sre87-control-cycle-patch/. .
chmod +x scripts/run-sre87-demo.sh
uv sync --all-extras --dev
uv run pytest -q
```
