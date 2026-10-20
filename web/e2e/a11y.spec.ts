import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function violations(page: import("@playwright/test").Page) {
  await page.waitForTimeout(900); // let entrance animations (<= 0.5s) finish before measuring contrast
  const r = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  return r.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`);
}

for (const scheme of ["light", "dark"] as const) {
  test.describe(`axe WCAG A/AA (${scheme})`, () => {
    test.use({ colorScheme: scheme });

    test("ask: empty, answer and refusal states", async ({ page }) => {
      await page.goto("/");
      expect(await violations(page)).toEqual([]);
      await page.getByLabel("Your question").fill("What is the management fee?");
      await page.getByRole("button", { name: "Ask", exact: true }).click();
      await page.getByTestId("answer").getByRole("button", { name: /Open source/ }).click();
      expect(await violations(page)).toEqual([]);
      await page.getByLabel("Your question").fill("What is the clawback provision?");
      await page.getByRole("button", { name: "Ask", exact: true }).click();
      await expect(page.getByTestId("refusal")).toBeVisible();
      expect(await violations(page)).toEqual([]);
    });

    test("report, evaluation, library", async ({ page }) => {
      await page.goto("/report");
      await page.getByRole("button", { name: /Draft report/ }).click();
      await expect(page.getByTestId("coverage")).toBeVisible();
      expect(await violations(page)).toEqual([]);
      for (const path of ["/eval", "/library"]) {
        await page.goto(path);
        await page.waitForLoadState("networkidle");
        expect(await violations(page)).toEqual([]);
      }
    });
  });
}

// Table states that the fixture server does not produce. The JSON below exists only inside this
// test (mocked responses) to exercise layout and contrast; it is never served by the app.
const MOCK_METRICS = {
  n: 10, answer_accuracy: 0.5, auto_answer_rate: 0.4, auto_answer_rate_answerable: 0.5,
  citation_precision: 0.5, citation_recall: 0.5, faithfulness: 1, refusal_precision: 1,
  refusal_recall: 1, answered: 5, hallucinations: 0, hallucination_rate: 0,
  hallucination_upper_95: 0.43, by_category: {},
}; // prettier-ignore

for (const scheme of ["light", "dark"] as const) {
  test(`axe on populated eval and library tables (${scheme})`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await page.route("**/api/eval", (r) =>
      r.fulfill({ json: { available: true, metrics: { "mock-config": MOCK_METRICS } } }),
    );
    await page.route("**/api/documents", (r) =>
      r.fulfill({
        json: {
          documents: [
            { doc: "mock-doc", chunks: 3, pages: 2, date: null, url: "https://example.org/x.pdf",
              publisher: "Mock", date_pulled: "2026-01-01T00:00:00+00:00", sha256: "abcdef0123456789" },
          ],
        },
      }),
    );
    for (const path of ["/eval", "/library"]) {
      await page.goto(path);
      await expect(page.getByRole("table")).toBeVisible();
      expect(await violations(page)).toEqual([]);
    }
  });
}
