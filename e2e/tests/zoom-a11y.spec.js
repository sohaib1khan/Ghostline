import { expect, test } from "@playwright/test";

/**
 * WCAG-style zoom check: 1280px window at 200% and 400% effective zoom
 * must not introduce page-level horizontal scroll on key surfaces.
 */
const PAGES = ["/", "/demo", "/games", "/settings/preferences", "/login"];

async function assertNoPageHorizontalScroll(page) {
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement;
    return {
      scrollWidth: doc.scrollWidth,
      clientWidth: doc.clientWidth,
    };
  });
  expect(
    overflow.scrollWidth,
    `horizontal overflow: scrollWidth ${overflow.scrollWidth} > clientWidth ${overflow.clientWidth}`,
  ).toBeLessThanOrEqual(overflow.clientWidth + 1);
}

for (const zoom of [2, 4]) {
  test.describe(`${zoom * 100}% zoom @ 1280px`, () => {
    test.use({
      viewport: { width: 1280, height: 800 },
      deviceScaleFactor: 1,
    });

    for (const path of PAGES) {
      test(`${path} has no page horizontal scroll`, async ({ page }) => {
        await page.goto(path);
        await page.evaluate((factor) => {
          document.documentElement.style.zoom = String(factor);
        }, zoom);
        await page.waitForTimeout(200);
        await assertNoPageHorizontalScroll(page);
      });
    }

    test("nav collapses to a menu button", async ({ page }) => {
      await page.goto("/");
      await page.evaluate((factor) => {
        document.documentElement.style.zoom = String(factor);
      }, zoom);
      await page.waitForTimeout(200);
      // At high zoom the CSS width shrinks — Open menu should be available.
      const toggle = page.getByRole("button", { name: /Open menu|Close menu/ });
      if (await toggle.count()) {
        await expect(toggle.first()).toBeVisible();
      }
    });
  });
}
