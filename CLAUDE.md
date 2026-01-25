# Claude Instructions for poly-scout

## CRITICAL: Run Everything on Vultr

**NEVER run anything locally.** Local machine has geo-restrictions.

- NO local Python scripts
- NO local API calls
- NO local curl/web fetches to Polymarket

ALL Polymarket API calls, data fetches, and script execution MUST go through Vultr.

### Vultr Server
- **IP:** 95.179.138.245
- **User:** root
- **Key:** ~/.ssh/vultr_polymarket
- **Repo path:** /root/poly-scout

### How to Run Commands

**ALWAYS use SSH:**
```bash
ssh -o StrictHostKeyChecking=no -i ~/.ssh/vultr_polymarket root@95.179.138.245 "command here"
```

**Deploy changes:**
```bash
git add . && git commit -m "message" && git push
ssh -o StrictHostKeyChecking=no -i ~/.ssh/vultr_polymarket root@95.179.138.245 "cd /root/poly-scout && git pull"
```

**Run daemon:**
```bash
ssh -o StrictHostKeyChecking=no -i ~/.ssh/vultr_polymarket root@95.179.138.245 "cd /root/poly-scout && killall python3 2>/dev/null; nohup python3 -m src.daemon > /tmp/scout.log 2>&1 &"
```

**Check logs:**
```bash
ssh -o StrictHostKeyChecking=no -i ~/.ssh/vultr_polymarket root@95.179.138.245 "tail -100 /tmp/scout.log"
```

### NEVER Use PuTTY
- Do NOT use plink.exe
- Do NOT use .ppk key files
- ONLY use OpenSSH (ssh, scp)

### Goal
Generate REAL profit from Polymarket arbitrage and edge opportunities. Paper trading is for validation only - the end goal is real money execution.
