# 🌐 Web Automation Setup Guide

This guide explains how to transition from the simulated **Nexus RPA** web scraping to a production-ready environment using **Selenium** or **Playwright**.

## 1. Choosing Your Engine

| Tool | Best For | Pros |
|---|---|---|
| **Selenium** | Legacy support, Large community | Supports every browser, huge ecosystem |
| **Playwright** | Modern web apps, Speed | Auto-waiting, better dev experience, faster |

---

## 2. Setup with Selenium (Python)

### Installation
```bash
pip install selenium webdriver-manager
```

### Basic Script Template
```python
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# Setup
options = webdriver.ChromeOptions()
options.add_argument('--headless') # Run without window
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

try:
    driver.get("https://example.com")
    print(f"Title: {driver.title}")
    
    # Example Scrape
    elements = driver.find_elements(By.CSS_SELECTOR, "h1")
    for el in elements:
        print(f"Found Heading: {el.text}")
        
finally:
    driver.quit()
```

---

## 3. Setup with Playwright (Modern)

### Installation
```bash
pip install playwright
playwright install chromium
```

### Basic Script Template
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://example.com")
    
    # Auto-waits for element
    content = page.inner_text("h1")
    print(f"Scraped Content: {content}")
    
    browser.close()
```

---

## 4. Production Tips
- **Headless Mode**: Always use `--headless` in server environments.
- **User Agents**: Rotate User-Agents to avoid being blocked.
- **Timeouts**: Always wrap your code in `try/except` blocks to handle `TimeoutException`.
- **Proxies**: Use proxy rotation for large-scale scraping.
