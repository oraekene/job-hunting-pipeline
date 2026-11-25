#!/usr/bin/env python3
"""Test Playwright with system Chrome against Bing to verify real result extraction."""
import sys, json, time
from playwright.sync_api import sync_playwright

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

with sync_playwright() as p:
    try:
        browser = p.chromium.launch(channel="chrome", headless=False, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    except Exception as e:
        print(f"Chrome channel failed: {e}, trying chromium")
        browser = p.chromium.launch(headless=False, args=["--no-sandbox"])
    page = browser.new_page()
    page.set_extra_http_headers({"User-Agent": UA})
    q = 'site:reddit.com "hiring" "product manager" remote'
    url = "https://www.bing.com/search?q=" + "+".join(q.split(" "))
    print(f"Navigating to: {url}")
    page.goto(url, wait_until="networkidle", timeout=30000)
    time.sleep(2)
    # Extract result links from b_algo
    results = page.eval_on_selector_all("li.b_algo a", "els => els.map(a => ({href: a.href, text: a.innerText.slice(0,80)}))", [])
    print(f"b_algo links found: {len(results)}")
    for r in results[:15]:
        print(f"  {r['text']} -> {r['href'][:100]}")
    # Count Reddit links
    reddit = [r for r in results if "reddit.com" in r["href"]]
    print(f"reddit links: {len(reddit)}")
    title = page.title()
    print(f"page title: {title}")
    browser.close()
