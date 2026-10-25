"""Browser smoke test. Run against a fresh, disposable API database.

Requires Python Playwright and Chromium (or CHROME_PATH). See README.md.
All game API requests are forwarded to API_ORIGIN; the frontend may keep using
its normal development backend for other games.
"""
import csv
import io
import json
import os
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://localhost:3000")
API_ORIGIN = os.environ.get("API_ORIGIN", "http://127.0.0.1:8001")
OUTPUT = Path(os.environ.get("PLAYTEST_OUTPUT", "/tmp/common-ground-playtest"))
OUTPUT.mkdir(parents=True, exist_ok=True)


def state(page):
    return page.evaluate("JSON.parse(localStorage.getItem('common-ground-v1'))")


def set_guess(page, value):
    slider = page.get_by_role("slider", name="Your sentiment guess")
    slider.focus()
    slider.press("Home")
    for _ in range(value):
        slider.press("ArrowRight")
    expect(slider).to_have_value(str(value))


with sync_playwright() as p:
    options = {"headless": True}
    if os.environ.get("CHROME_PATH"):
        options["executable_path"] = os.environ["CHROME_PATH"]
    browser = p.chromium.launch(**options)
    context = browser.new_context(viewport={"width": 1440, "height": 1050}, reduced_motion="reduce")
    page = context.new_page()
    page.set_default_timeout(10000)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    failures = {"annotation": True, "clue": True}
    submissions = []

    def api_proxy(route):
        request = route.request
        path = request.url.split("/api/games/wavelength", 1)[1]
        target = API_ORIGIN + "/api/games/wavelength" + path
        if request.method == "POST":
            submissions.append((path, request.post_data_json))
        if path == "/annotations" and request.method == "POST" and failures["annotation"]:
            failures["annotation"] = False
            route.fulfill(status=503, content_type="application/json", body='{"detail":"Test outage"}')
        elif path == "/clues" and request.method == "POST" and failures["clue"]:
            # The server commits but the browser loses the response. Retrying
            # must recover the same result without inserting another pair.
            failures["clue"] = False
            route.fetch(url=target)
            route.abort("failed")
        else:
            route.fulfill(response=route.fetch(url=target))

    context.route("**/api/games/wavelength**", api_proxy)
    initial = context.request.get(API_ORIGIN + "/api/games/wavelength/dataset").json()
    assert initial["summary"]["annotations"] == 0 and initial["summary"]["synthetic_pairs"] == 0, "Use a fresh disposable API database."
    page.goto(BASE_URL + "/games/wavelength")
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="Read the review", exact=True).click()
    expect(page.get_by_role("heading", name=re.compile("How .* does this customer sound"))).to_be_visible()
    page.screenshot(path=str(OUTPUT / "desktop.png"), full_page=True)
    assert "reference_score" not in context.request.get(API_ORIGIN + "/api/games/wavelength/reviews").text()
    expect(page.get_by_role("button", name="Lock in my guess")).to_be_disabled()
    page.get_by_role("button", name="How to play").click()
    expect(page.get_by_role("dialog", name="Find the feeling.")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.get_by_role("dialog")).not_to_be_visible()

    # Save failure, immutable payload, refresh, retry, then complete a set.
    set_guess(page, 73)
    page.get_by_role("radio", name="Open to interpretation").check()
    page.get_by_role("button", name="Lock in my guess").click()
    expect(page.get_by_role("alert")).to_be_visible()
    expect(page.get_by_role("slider")).to_be_disabled()
    pending_id = state(page)["solo"]["pending"]["submission_id"]
    page.reload()
    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("slider")).to_have_value("73")
    page.get_by_role("button", name="Retry save").click()
    expect(page.get_by_text("Your independent rating was saved before the reveal.")).to_be_visible()
    assert state(page)["solo"]["results"][0]["annotation_id"] == pending_id
    page.screenshot(path=str(OUTPUT / "solo-reveal.png"), full_page=True)
    for i in range(1, 5):
        page.get_by_role("button", name="Next review", exact=True).click()
        page.get_by_role("button", name="Read the review", exact=True).click()
        set_guess(page, 15 + i * 15)
        page.get_by_role("button", name="Lock in my guess").click()
        expect(page.get_by_text("Your independent rating was saved before the reveal.")).to_be_visible()
    page.get_by_role("button", name="See your results").click()
    expect(page.get_by_role("heading", name="A little more in tune.")).to_be_visible()
    first_deck = state(page)["solo"]["deck"]
    page.get_by_role("button", name="Play another set").click()
    assert not set(first_deck).intersection(state(page)["solo"]["deck"]), "No repeat reviews after feedback"

    # Pair play: privacy handoff, refresh behavior, response loss and replay.
    page.get_by_role("button", name="Pass & play").click()
    previous_scenario = None
    for i in range(5):
        page.get_by_role("button", name="Spin a feeling", exact=True).click()
        scenario = state(page)["pair"]["scenarioId"]
        assert scenario and scenario != previous_scenario
        previous_scenario = scenario
        expect(page.get_by_label("This round’s scenario")).to_be_visible()
        page.get_by_role("button", name="Write your review", exact=True).click()
        target = state(page)["pair"]["target"]
        assert page.get_by_role("slider").count() == 0
        expect(page.get_by_label("This round’s scenario")).to_be_visible()
        clue = f"Invented review {i + 1}: The service had its moments, but I left with mixed feelings."
        page.get_by_role("textbox", name="Your made-up review").fill(clue)
        page.screenshot(path=str(OUTPUT / "pair-write.png"), full_page=True)
        page.get_by_role("button", name="Hide target & pass the screen").click()
        expect(page.get_by_role("heading", name="Over to you, Player 2.")).to_be_visible()
        assert clue not in page.locator("main").inner_text()
        assert page.get_by_role("slider").count() == 0
        page.get_by_role("button", name="I’m Player 2. Let me guess.").click()
        expect(page.get_by_text("Secret target", exact=True)).not_to_be_visible()
        if i == 0:
            page.reload()
            page.wait_for_load_state("networkidle")
            page.get_by_role("button", name="Pass & play").click()
            expect(page.get_by_role("heading", name="Over to you, Player 2.")).to_be_visible()
            page.get_by_role("button", name="I’m Player 2. Let me guess.").click()
        set_guess(page, target)
        page.get_by_role("button", name="Reveal the target").click()
        if i == 0:
            expect(page.get_by_role("button", name="Retry save")).to_be_visible()
            page.get_by_role("button", name="Retry save").click()
        expect(page.get_by_text("Saved as a synthetic review with two separate signals.")).to_be_visible()
        expect(page.get_by_text("+100 pts", exact=True)).to_be_visible()
        if i < 4:
            page.get_by_role("button", name="Swap roles & continue").click()
    expect(page.get_by_text("500 / 500 points together")).to_be_visible()
    page.screenshot(path=str(OUTPUT / "pair-complete.png"), full_page=True)

    page.get_by_role("button", name="The data you make").click()
    expect(page.get_by_role("heading", name="Recent invented review pairs")).to_be_visible()
    for format in ("JSON", "CSV"):
        with page.expect_download() as event:
            page.get_by_role("button", name=format, exact=True).click()
        event.value.save_as(OUTPUT / ("export." + format.lower()))
    data = json.loads((OUTPUT / "export.json").read_text())
    assert data["summary"]["annotations"] == 5
    assert data["summary"]["synthetic_pairs"] == 5
    assert data["summary"]["independent_annotations"] == 5
    assert data["summary"]["unsure_annotations"] == 1
    assert all(r["axis_id"] in ("satisfaction", "anger", "happiness", "excitement") for r in data["annotations"] + data["synthetic_pairs"])
    assert all(r["source"] == "authored_demo" for r in data["annotations"])
    assert all(r["source"] == "player_authored_synthetic" for r in data["synthetic_pairs"])
    assert all(r["category"] != "Player-written" for r in data["synthetic_pairs"]), "Save the scenario with each invented review"
    assert len(list(csv.DictReader(io.StringIO((OUTPUT / "export.csv").read_text())))) == 10
    assert submissions[0][1] == submissions[1][1], "Retry must reuse the full annotation payload"
    page.screenshot(path=str(OUTPUT / "dataset.png"), full_page=True)

    # Mobile, keyboard, dialog and overflow checks use a clean browser identity.
    mobile = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    mobile.route("**/api/games/wavelength**", api_proxy)
    mp = mobile.new_page()
    mp.on("pageerror", lambda error: errors.append(str(error)))
    mp.goto(BASE_URL + "/games/wavelength")
    mp.wait_for_load_state("networkidle")
    assert mp.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Mobile page overflows horizontally"
    mp.screenshot(path=str(OUTPUT / "mobile.png"), full_page=True)
    mp.get_by_role("button", name="Read the review", exact=True).click()
    mp.get_by_role("button", name="Right in the middle? Keep 50.").click()
    expect(mp.get_by_role("button", name="Lock in my guess")).to_be_enabled()
    mp.get_by_role("button", name="Pass & play").click()
    mp.get_by_role("button", name="Spin a feeling", exact=True).click()
    mp.get_by_role("button", name="Write your review", exact=True).click()
    mp.get_by_role("textbox").fill("A perfectly decent experience, without much to write home about.")
    assert mp.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    mp.screenshot(path=str(OUTPUT / "mobile-pair.png"), full_page=True)
    mobile.close()

    # A valid JSON non-object must not brick game boot.
    page.evaluate("localStorage.setItem('common-ground-v1', 'null')")
    page.reload()
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="Read the review", exact=True).click()
    expect(page.get_by_role("heading", name=re.compile("How .* does this customer sound"))).to_be_visible()
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("link", name="Common Ground", exact=False)).to_be_visible()
    page.screenshot(path=str(OUTPUT / "home.png"), full_page=True)
    assert not errors, f"Browser errors: {errors}"
    # The normal-motion experience must animate in sequence, not only update
    # state correctly when reduced motion skips the transitions.
    animated = browser.new_context(viewport={"width": 1440, "height": 1050}, reduced_motion="no-preference")
    animated.route("**/api/games/wavelength**", api_proxy)
    ap = animated.new_page()
    ap.set_default_timeout(10000)
    ap.goto(BASE_URL + "/games/wavelength")
    ap.wait_for_load_state("networkidle")
    ap.get_by_role("button", name="Read the review", exact=True).click()
    ap.get_by_role("button", name="Pass & play").click()
    ap.get_by_role("button", name="Spin a feeling", exact=True).click()
    shuffle = ap.locator('[data-stage="shuffle"]')
    expect(shuffle).to_be_visible()
    assert shuffle.evaluate('(el) => el.getAnimations({subtree:true}).some(a => a.playState === "running")')
    ap.screenshot(path=str(OUTPUT / "emotion-shuffle.png"), full_page=True)
    ap.locator('[data-stage="wheel"]').wait_for()
    wheel = ap.locator('[data-spinning="true"]')
    assert wheel.evaluate('(el) => el.getAnimations({subtree:true}).some(a => a.playState === "running")')
    expect(wheel.locator("strong")).to_have_text("?")
    ap.screenshot(path=str(OUTPUT / "wheel-spinning.png"), full_page=True)
    target = state(ap)["pair"]["target"]
    ap.get_by_role("button", name="Write your review", exact=True).wait_for()
    expect(ap.locator('[data-spinning="false"] strong')).to_have_text(str(target) + "%")
    ap.screenshot(path=str(OUTPUT / "wheel-landed.png"), full_page=True)

    # Upgrade a legacy unfinished round: select a fresh emotion and don't
    # reinterpret the old slider position as a different emotion.
    legacy = state(ap)
    legacy["solo"].pop("axisId", None)
    legacy["solo"].pop("setup", None)
    legacy["solo"].update(guess=72, touched=True)
    ap.evaluate("value => localStorage.setItem('common-ground-v1', JSON.stringify(value))", legacy)
    ap.reload()
    ap.wait_for_load_state("networkidle")
    ap.get_by_role("button", name="Read the review", exact=True).click()
    expect(ap.get_by_role("slider")).to_have_value("50")
    assert state(ap)["solo"]["axisId"] in ("satisfaction", "anger", "happiness", "excitement")
    animated.close()
    browser.close()
    print("PASS: solo/pair five-round sets, emotion shuffle, sequential wheel spin and percentage reveal, keyboard guesses, legacy round upgrade, refresh recovery, failed-save retries, handoff privacy, exports, and mobile.")
    print(f"Screenshots and export artifacts: {OUTPUT}")
