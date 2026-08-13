#!/usr/bin/env python3
"""Quick helper: pull datePosted from Ashby job pages for the discovery scan."""
import sys, re, time
try:
    import requests
except ImportError:
    print("requests not available")
    sys.exit(1)

urls = {
  "Runlayer-FoundingPM-ControlPlane": "https://jobs.ashbyhq.com/runlayer/89a7b99f-8242-4ed8-926f-796ec453b66d",
  "Counsel-SrPM-Enterprise": "https://jobs.ashbyhq.com/counsel/ff271d48-0b07-46ef-a06e-3a237d97f1de",
  "Kin-SrInsurance-PM": "https://jobs.ashbyhq.com/kin/aeea0d94-5305-47fc-a832-ae15d990dcde",
  "Camunda-SrPM-CorePlatform": "https://jobs.ashbyhq.com/camunda/b771e145-a5cf-4867-ad13-b54830e3b744",
  "Render-StaffPMPF": "https://jobs.ashbyhq.com/render/d5f62097-29f5-4078-ad24-3b604380c1c0",
}
h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
for name, url in urls.items():
    try:
        r = requests.get(url, headers=h, timeout=20)
        dp = re.search(r'"datePosted"\s*:\s*"([^"]*)"', r.text)
        deadline = re.search(r'Deadline to Apply[^<]*<[^>]*>([^<]+)', r.text)
        remote = "Remote" in r.text or "remote" in r.text
        print(f"{name}: posted={dp.group(1) if dp else 'NOT FOUND'} deadline={deadline.group(1).strip() if deadline else '?'} remote={remote} status={r.status_code}")
    except Exception as e:
        print(f"{name}: ERROR {e}")
    time.sleep(0.5)
