import sys, asyncio, re
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
        if document_fonts := True:
            await page.evaluate("document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()")
        adds=page.locator(".item .add")
        assert await adds.count() == 12
        assert await adds.first.text_content() == "Find at retailer"
        for i in [0,2,3,4,5,9]:
            await page.locator(".item .add").nth(i).click()
        await page.wait_for_timeout(1200)
        prog=await page.text_content("#progText")
        filled=await page.locator(".slot.filled").count()
        bar=await page.text_content("#buyBar")
        status=await page.locator(".item.added .status").first.text_content()
        print("progress:",prog,"| filled slots:",filled,"| bar:",bar,"| popups:",len(popups)-0)
        print("row status:", " ".join(status.split()) if status else None)
        body=await page.content()
        print("has Mockup link:", "Mockup link" in body)
        print("has Your box is:", "Your box is" in body)
        hrefs=await page.eval_on_selector_all(".add","els=>els.map(e=>e.href)")
        print("sample href:",hrefs[3])
        affiliate=any(re.search(r"([?&](tag|ref|ascsubtag|linkCode|camp|creative|psc)=)", h, re.I) for h in hrefs)
        print("affiliate tags:", affiliate)
        # First list row vs sticky bar at 390x844
        await page.evaluate("window.scrollTo(0,0)"); await page.wait_for_timeout(400)
        row_box=await page.locator(".item").first.bounding_box()
        bar_box=await page.locator(".buybar").bounding_box()
        svg_box=await page.locator("#boxSvg").bounding_box()
        visible_h=min(row_box["y"]+row_box["height"], bar_box["y"]) - row_box["y"]
        full_row=row_box["y"]>=0 and (row_box["y"]+row_box["height"]) <= bar_box["y"] + 0.5
        print("svg height:", round(svg_box["height"],1), "svg y:", round(svg_box["y"],1))
        print("first row y:", round(row_box["y"],1), "h:", round(row_box["height"],1), "bar y:", round(bar_box["y"],1), "visible_h:", round(max(0,visible_h),1), "full_row_above_bar:", full_row)
        # slot label visual size
        label_info=await page.evaluate("""() => {
          const svg=document.getElementById('boxSvg');
          const t=svg.querySelector('.lbl');
          if(!t) return null;
          const scale=svg.getBoundingClientRect().width/400;
          const fs=parseFloat(t.style.fontSize||getComputedStyle(t).fontSize);
          return {text:t.textContent, userFs:fs, visual:fs*scale, length:t.getComputedTextLength(), slotW:+t.closest('.slot').dataset.w};
        }""")
        print("label sample:", label_info)
        await page.screenshot(path=f"{OUT}/mobile.png")
        await page.screenshot(path=f"{OUT}/mobile-full.png",full_page=True)
        # tabs
        for t in ["power","car","pets","home"]:
            await page.click(f"#tab-{t}"); await page.wait_for_timeout(200)
            print(t, await page.text_content("#boxTitle"), await page.text_content("#progText"), await page.locator(".slot").count(), "filled", await page.locator(".slot.filled").count())
        # MAP label on car tab
        await page.click("#tab-car"); await page.wait_for_timeout(200)
        shorts=await page.evaluate("() => Array.from(document.querySelectorAll('#boxSvg .lbl')).map(t=>t.getAttribute('data-full')||t.textContent)")
        print("car shorts:", shorts)
        print("has MAP:", "MAP" in shorts)
        await page.click("#tab-home"); await page.wait_for_timeout(200)
        # modal
        await page.click("#buyBar"); await page.wait_for_timeout(200)
        print("modal open:", await page.evaluate("document.getElementById('buyModal').open"), "title:", await page.text_content("#buyModalTitle"), "items:", await page.locator("#mlist li").count(), "links:", await page.locator("#mlist a").count())
        print("modal has Mockup link:", "Mockup link" in (await page.locator("#buyModal").inner_text()))
        await page.click("#closeModal")
        # reload persistence
        await page.reload(wait_until="networkidle"); print("after reload:", await page.text_content("#progText"))
        # start again inline confirm
        await page.click("#resetBtn"); await page.wait_for_timeout(100)
        prompt=await page.text_content("#resetPrompt")
        hidden=await page.evaluate("document.getElementById('resetConfirm').hidden")
        print("confirm:", prompt, "hidden:", hidden)
        await page.click("#resetNo"); await page.wait_for_timeout(100)
        print("after no:", await page.text_content("#progText"), "confirm hidden:", await page.evaluate("document.getElementById('resetConfirm').hidden"))
        await page.click("#resetBtn"); await page.click("#resetYes"); await page.wait_for_timeout(200)
        print("after yes:", await page.text_content("#progText"), "filled:", await page.locator(".slot.filled").count())
        # re-add for desktop shot consistency is handled in desktop context
        # desktop
        d=await b.new_context(viewport={"width":1280,"height":800})
        await d.route("**/www.amazon.co.uk/**",lambda r:r.fulfill(status=200,body="stub",content_type="text/html"))
        dp=await d.new_page(); dp.on("pageerror",lambda e: errs.append(str(e))); dp.on("console",lambda m: errs.append(m.text) if m.type=="error" else None)
        await dp.goto(URL,wait_until="networkidle")
        await dp.evaluate("localStorage.clear()"); await dp.reload(wait_until="networkidle")
        await dp.evaluate("document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()")
        for i in [0,2,3,4,5,9]:
            await dp.locator(".item .add").nth(i).click()
        for pg in d.pages:
            if pg!=dp: await pg.close()
        await dp.evaluate("window.scrollTo(0,0)"); await dp.wait_for_timeout(800)
        # column top alignment
        tops=await dp.evaluate("""() => {
          const box=document.querySelector('.box-card').getBoundingClientRect();
          const list=document.querySelector('.list-card').getBoundingClientRect();
          return {boxTop:box.top, listTop:list.top, delta:Math.abs(box.top-list.top)};
        }""")
        print("column tops:", tops)
        # status one line
        st=await dp.locator(".item.added .status").first.bounding_box()
        print("status line height:", round(st["height"],1) if st else None)
        await dp.screenshot(path=f"{OUT}/desktop.png")
        # print emulation
        await dp.emulate_media(media="print")
        await dp.pdf(path="/tmp/brb-print.pdf")
        print("console errors:",errs)
        await b.close()
asyncio.run(main())
