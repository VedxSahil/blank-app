import { expect, test } from "@playwright/test";

// Viva demo shape: three cited answers, then one refusal. Runs against the FIXTURE corpus.
const ANSWERED: [string, RegExp, string][] = [
  ["What is the management fee?", /management fee is 2%/, "fixture-doc, p.1"],
  ["What is the carried interest and hurdle rate?", /Carried interest is 20%/, "fixture-doc, p.1"],
  ["What is the net asset value of the fund?", /net asset value of the fund was 500 million/, "fixture-doc, p.2"],
];

test("three cited answers then one refusal", async ({ page }) => {
  await page.goto("/");
  for (const [q, text, cite] of ANSWERED) {
    await page.getByLabel("Your question").fill(q);
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    const answer = page.getByTestId("answer");
    await expect(answer).toContainText(text);
    const chip = answer.getByRole("button", { name: `Open source: ${cite}` });
    await expect(chip).toBeVisible();
    await chip.click();
    const panel = page.getByRole("complementary", { name: "Source viewer" });
    await expect(panel).toContainText(`page ${cite.split("p.")[1]}`);
    await expect(panel.locator("mark")).toBeVisible();
    await expect(answer).toContainText("Verified against cited pages");
  }
  await page.getByLabel("Your question").fill("What is the clawback provision?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByTestId("refusal")).toContainText("Not answerable from the provided documents");
  await expect(page.getByTestId("refusal")).toContainText("no_evidence");
  await expect(page.getByTestId("answer")).toHaveCount(0);
});

test("report builder binds lines to chunks and marks gaps", async ({ page }) => {
  await page.goto("/report");
  await page.getByRole("button", { name: /Draft report/ }).click();
  await expect(page.getByTestId("coverage")).toContainText("of 17 fields");
  await expect(page.getByText("Not disclosed in provided documents").first()).toBeVisible();
  await expect(page.getByText("fixture:p1:c0").first()).toBeVisible();
});

test("library and evaluation show honest empty/real states", async ({ page }) => {
  await page.goto("/library");
  await expect(page.getByRole("cell", { name: "3" }).first()).toBeVisible();
  await expect(page.getByRole("rowheader", { name: "fixture-doc" })).toBeVisible();
  await page.goto("/eval");
  await expect(page.getByTestId("no-eval")).toContainText("No numbers are shown until then");
});

test("reduced motion shows the answer immediately", async ({ browser }) => {
  const ctx = await browser.newContext({ reducedMotion: "reduce", baseURL: "http://127.0.0.1:3100" });
  const page = await ctx.newPage();
  await page.goto("/");
  await page.getByLabel("Your question").fill("What is the management fee?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByTestId("answer").getByRole("button", { name: /Open source/ })).toBeVisible({
    timeout: 1500,
  });
  await ctx.close();
});

test("no horizontal scroll at phone width on any screen", async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 375, height: 700 }, baseURL: "http://127.0.0.1:3100" });
  const page = await ctx.newPage();
  for (const path of ["/", "/report", "/eval", "/library"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, path).toBeLessThanOrEqual(0);
  }
  await ctx.close();
});


test("the notice banner from the API is shown on every screen", async ({ page }) => {
  for (const path of ["/", "/report", "/eval", "/library"]) {
    await page.goto(path);
    await expect(page.getByTestId("banner")).toContainText("FIXTURE TEXT (invented)");
  }
});
