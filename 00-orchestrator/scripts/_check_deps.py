#!/usr/bin/env python
mods = {}
for m in ["docx", "yaml"]:
    try:
        mod = __import__(m)
        mods[m] = getattr(mod, "__version__", "ok")
    except Exception as e:
        mods[m] = f"MISSING: {e}"
print("python-docx:", mods.get("docx"))
print("yaml:", mods.get("yaml"))
