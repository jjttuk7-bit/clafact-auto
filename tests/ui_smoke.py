from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("http://127.0.0.1:8501", wait_until="networkidle")
    assert "CLAFACT-AUTO" in page.locator("body").inner_text()
    page.get_by_label("검증할 뉴스 문장").fill("2024년 전국 고용률은 70%였다.")
    page.get_by_label("기사 기준일 (YYYY-MM-DD)").fill("invalid-date")
    page.get_by_role("button", name="자동 검증 실행").click()
    page.wait_for_timeout(2500)
    body = page.locator("body").inner_text()
    assert "HOLD: 기사 기준일은 YYYY-MM-DD 형식이어야 합니다." in body
    page.screenshot(path="C:/tmp/clafact-auto-hold.png", full_page=True)
    browser.close()

