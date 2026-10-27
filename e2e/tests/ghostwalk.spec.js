import { expect, test } from "@playwright/test";

test.describe("Ghostwalk zoom reflow", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  for (const zoom of [2, 4]) {
    test(`map has no page horizontal scroll at ${zoom * 100}%`, async ({ page }) => {
      await page.goto("/ghostwalk");
      await page.evaluate((factor) => {
        document.documentElement.style.zoom = String(factor);
      }, zoom);
      await page.waitForTimeout(200);
      const overflow = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      }));
      expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth + 1);
    });
  }
});
