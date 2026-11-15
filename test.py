import sys, asyncio
from playwright.async_api import async_playwright
URL=sys.argv[1]; OUT=sys.argv[2] if len(sys.argv)>2 else "shots"
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        ctx=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
        await ctx.route("**/www.amazon.co.uk/**",lambda r:r.fulfill(status=200,body="amazon stub",content_type="text/html"))
        errs=[]
        popups=[]
        ctx.on("page",lambda pg: popups.append(pg))
        page=await ctx.new_page()
        page.on("console",lambda m: errs.append(m.text) if m.type=="error" else None)
        page.on("pageerror",lambda e: errs.append(str(e)))
        await page.goto(URL,wait_until="networkidle")
        await page.evaluate("localStorage.clear()"); await page.reload(wait_until="networkidle")
        adds=page.locator(".item .add")
        for i in [0,2,3,4,5,9]:
            await page.locator(".item .add").nth(i).click()
        await page.wait_for_timeout(1200)
        prog=await page.text_content("#progText")
        filled=await page.locator(".slot.filled").count()
        bar=await page.text_content("#buyBar")
        print("progress:",prog,"| filled slots:",filled,"| bar:",bar,"| popups:",len(popups)-0)
        for pg in popups:
            if pg!=page: await pg.close()
        hrefs=await page.eval_on_selector_all(".add","els=>els.map(e=>e.href)")
        print("sample href:",hrefs[3])
        await page.evaluate("window.scrollTo(0,0)"); await page.wait_for_timeout(300)
        await page.screenshot(path=f"{OUT}/mobile.png")
        await page.screenshot(path=f"{OUT}/mobile-full.png",full_page=True)
        # tabs
        for t in ["power","car","pets","home"]:
            await page.click(f"#tab-{t}"); await page.wait_for_timeout(200)
            print(t, await page.text_content("#boxTitle"), await page.text_content("#progText"), await page.locator(".slot").count(), "filled", await page.locator(".slot.filled").count())
        # modal
        await page.click("#buyBar"); await page.wait_for_timeout(200)
        print("modal open:", await page.evaluate("document.getElementById('buyModal').open"), await page.locator("#mlist li").count())
        await page.click("#closeModal")
        # reload persistence
        await page.reload(wait_until="networkidle"); print("after reload:", await page.text_content("#progText"))
        # desktop
        d=await b.new_context(viewport={"width":1280,"height":800})
        await d.route("**/www.amazon.co.uk/**",lambda r:r.fulfill(status=200,body="stub",content_type="text/html"))
        dp=await d.new_page(); dp.on("pageerror",lambda e: errs.append(str(e))); dp.on("console",lambda m: errs.append(m.text) if m.type=="error" else None)
        await dp.goto(URL,wait_until="networkidle")
        for i in [0,2,3,4,5,9]:
            await dp.locator(".item .add").nth(i).click()
        for pg in d.pages:
            if pg!=dp: await pg.close()
        await dp.evaluate("window.scrollTo(0,0)"); await dp.wait_for_timeout(800)
        await dp.screenshot(path=f"{OUT}/desktop.png")
        # print emulation
        await dp.emulate_media(media="print")
        await dp.pdf(path="/tmp/brb-print.pdf")
        print("console errors:",errs)
        await b.close()
asyncio.run(main())
