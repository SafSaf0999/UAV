import re
log = open("report_full.log").read()
errors = [l for l in log.splitlines() if l.startswith("!")]
warnings = [l for l in log.splitlines() if "Warning" in l and "fancyhdr" not in l and "rerunfilecheck" not in l]
print("ERRORS:", errors or "none")
print("WARNINGS:", warnings[:10] if warnings else "none")
