import sys, asyncio, re
from playwright.async_api import async_playwright
URL=sys.argv[1]; OUT=sys.argv[2] if len(sys.argv)>2 else "shots"

LABEL_JS = """() => {
  const svg=document.getElementById('boxSvg');
  const scale=svg.getBoundingClientRect().width/400;
  return Array.from(document.querySelectorAll('#boxSvg .slot')).map(g=>{
    const cell=g.querySelector('.cell').getBoundingClientRect();
    const text=g.querySelector('.lbl');
    const tb=text.getBoundingClientRect();
    const lines=[...text.querySelectorAll('tspan')].map(s=>s.textContent);
    const shown=lines.length?lines:[text.textContent];
    const pad=0.75;
    const clip=tb.left<cell.left-pad || tb.right>cell.right+pad || tb.top<cell.top-pad || tb.bottom>cell.bottom+pad;
    return {
      id:g.dataset.id,
      full:text.getAttribute('data-full'),
      shown,
      ls:getComputedStyle(text).letterSpacing,
      fontUser:parseFloat(text.style.fontSize||getComputedStyle(text).fontSize),
      visual:parseFloat(text.style.fontSize||getComputedStyle(text).fontSize)*scale,
      clip,
      overflow:{
        l:+(cell.left-tb.left).toFixed(2),
        r:+(tb.right-cell.right).toFixed(2),
        t:+(cell.top-tb.top).toFixed(2),
        b:+(tb.bottom-cell.bottom).toFixed(2)
      }
    };
  });
}"""

async def setup(page):
    await page.goto(URL, wait_until="networkidle")
    await page.evaluate("localStorage.clear()")
    await page.reload(wait_until="networkidle")
    await page.evaluate("document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()")
    await page.wait_for_timeout(200)

async def add_six(page):
    for i in [0,2,3,4,5,9]:
        await page.locator(".item .add").nth(i).click()
    await page.wait_for_timeout(400)

async def labels_for_all_tabs(page, tag):
    issues=[]
    for tab in ["home","power","car","pets"]:
        await page.click(f"#tab-{tab}")
        await page.wait_for_timeout(250)
        rows=await page.evaluate(LABEL_JS)
        print(f"[{tag} {tab}]")
        for r in rows:
            shown=" / ".join(r["shown"]).upper()
            flag=" CLIP" if r["clip"] else ""
            print(f"  {r['full']!r:12} -> {shown!r:20} vis={r['visual']:.2f} ls={r['ls']}{flag} ov={r['overflow']}")
            if r["clip"]:
                issues.append((tag,tab,r))
            # never cut the source words
            joined=" ".join(r["shown"]).strip()
            if joined.replace(" ","").lower()!=r["full"].replace(" ","").lower() and r["full"]!="MAP":
                # MAP should stay MAP; case may differ due to paint of literal
                if r["full"]=="MAP" and shown=="MAP":
                    pass
                else:
                    issues.append((tag,tab,{"cut":True,**r}))
                    print("    CUT from source word")
    return issues

async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        errs=[]
        # --- 390 x 844 mobile (screenshots + fold + labels) ---
        ctx=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
        await ctx.route("**/www.amazon.co.uk/**",lambda r:r.fulfill(status=200,body="amazon stub",content_type="text/html"))
        popups=[]
        ctx.on("page",lambda pg: popups.append(pg))
        page=await ctx.new_page()
        page.on("console",lambda m: errs.append(m.text) if m.type=="error" else None)
        page.on("pageerror",lambda e: errs.append(str(e)))
        await setup(page)
        assert await page.locator(".item .add").first.text_content()=="Find at retailer"
        # progress note is below the segment bar
        order=await page.evaluate("""() => {
          const p=document.querySelector('.progress');
          return [...p.children].map(el=>el.id||el.className);
        }""")
        print("progress children:", order)
        await add_six(page)
        prog=await page.text_content("#progText")
        filled=await page.locator(".slot.filled").count()
        bar=await page.text_content("#buyBar")
        print("progress:",prog,"| filled slots:",filled,"| bar:",bar)
        hrefs=await page.eval_on_selector_all(".add","els=>els.map(e=>e.href)")
        print("sample href:",hrefs[3], "affiliate:", any(re.search(r"([?&](tag|ref|ascsubtag|linkCode|camp|creative|psc)=)", h, re.I) for h in hrefs))
        body=await page.content()
        print("has Mockup link:", "Mockup link" in body, "| has Your box is:", "Your box is" in body)

        await page.evaluate("window.scrollTo(0,0)"); await page.wait_for_timeout(300)
        row_box=await page.locator(".item").first.bounding_box()
        bar_box=await page.locator(".buybar").bounding_box()
        visible_h=min(row_box["y"]+row_box["height"], bar_box["y"]) - row_box["y"]
        full_row=row_box["y"]>=0 and (row_box["y"]+row_box["height"]) <= bar_box["y"] + 0.5
        print("first row y:", round(row_box["y"],1), "h:", round(row_box["height"],1), "bar y:", round(bar_box["y"],1), "visible_h:", round(max(0,visible_h),1), "full_row_above_bar:", full_row)

        issues390=await labels_for_all_tabs(page, "390")
        await page.click("#tab-home"); await page.wait_for_timeout(200)
        # required words on home / car
        home_shown=await page.evaluate("() => Array.from(document.querySelectorAll('#boxSvg .lbl')).map(t=>({full:t.getAttribute('data-full'), shown:[...t.querySelectorAll('tspan')].map(s=>s.textContent).join(' ')||t.textContent}))")
        print("home labels:", home_shown)
        await page.click("#tab-car"); await page.wait_for_timeout(200)
        car_shown=await page.evaluate("() => Array.from(document.querySelectorAll('#boxSvg .lbl')).map(t=>t.getAttribute('data-full'))")
        print("car full:", car_shown)

        await page.click("#tab-home"); await page.wait_for_timeout(200)
        await page.evaluate("window.scrollTo(0,0)"); await page.wait_for_timeout(200)
        await page.screenshot(path=f"{OUT}/mobile.png")
        await page.screenshot(path=f"{OUT}/mobile-full.png",full_page=True)

        # modal + confirm still work
        await page.click("#buyBar"); await page.wait_for_timeout(200)
        print("modal:", await page.text_content("#buyModalTitle"), "items:", await page.locator("#mlist li").count())
        await page.click("#closeModal")

        # --- 360 viewport labels ---
        ctx3=await b.new_context(viewport={"width":360,"height":800},device_scale_factor=2,is_mobile=True,has_touch=True)
        await ctx3.route("**/www.amazon.co.uk/**",lambda r:r.fulfill(status=200,body="stub",content_type="text/html"))
        p360=await ctx3.new_page()
        p360.on("pageerror",lambda e: errs.append(str(e)))
        await setup(p360)
        await add_six(p360)
        issues360=await labels_for_all_tabs(p360, "360")

        # --- desktop 1280 ---
        d=await b.new_context(viewport={"width":1280,"height":800})
        await d.route("**/www.amazon.co.uk/**",lambda r:r.fulfill(status=200,body="stub",content_type="text/html"))
        dp=await d.new_page(); dp.on("pageerror",lambda e: errs.append(str(e))); dp.on("console",lambda m: errs.append(m.text) if m.type=="error" else None)
        await setup(dp)
        await add_six(dp)
        for pg in d.pages:
            if pg!=dp: await pg.close()
        await dp.evaluate("window.scrollTo(0,0)"); await dp.wait_for_timeout(500)
        issues1280=await labels_for_all_tabs(dp, "1280")
        await dp.click("#tab-home"); await dp.wait_for_timeout(200)
        tops=await dp.evaluate("""() => {
          const box=document.querySelector('.box-card').getBoundingClientRect();
          const list=document.querySelector('.list-card').getBoundingClientRect();
          return {boxTop:box.top, listTop:list.top, delta:Math.abs(box.top-list.top)};
        }""")
        print("column tops:", tops)
        await dp.evaluate("window.scrollTo(0,0)"); await dp.wait_for_timeout(200)
        await dp.screenshot(path=f"{OUT}/desktop.png")
        print("CLIP/CUT issues 360:", len(issues360), "390:", len(issues390), "1280:", len(issues1280))
        if issues360 or issues390 or issues1280:
            print("ISSUES DETAIL:", issues360+issues390+issues1280)
        print("console errors:", errs)
        await b.close()
asyncio.run(main())
