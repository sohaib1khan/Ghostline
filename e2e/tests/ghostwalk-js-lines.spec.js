import { expect, test } from "@playwright/test";

/** Second move hits a wall; goal is unreachable by move alone. */
const BUMP_ON_LINE_TWO = {
  grid: ["#####", "#S.##", "##G##", "#####"],
  start: { row: 1, col: 1, facing: "E" },
  allowed: ["move", "at_goal"],
  goal: { reach_goal: true },
  max_steps: 500,
};

async function bumpLineTwo(browserType, baseURL) {
  const browser = await browserType.launch();
  const page = await browser.newPage();
  try {
    await page.goto("about:blank");
    await page.addScriptTag({ url: `${baseURL}/ghostwalk/world.js` });
    return await page.evaluate((level) => {
      const code = "hero.move();\nhero.move();\n";
      return globalThis.GhostwalkWorld.runLearnerCode(level, code);
    }, BUMP_ON_LINE_TWO);
  } finally {
    await browser.close();
  }
}

test.describe("Ghostwalk JS line tracking", () => {
  test("wall bump on line 2 reports error_line 2 in Chromium", async ({
    playwright,
    baseURL,
  }) => {
    const result = await bumpLineTwo(playwright.chromium, baseURL);
    expect(result.ok).toBe(false);
    expect(result.error_line).toBe(2);
  });

  test("wall bump on line 2 reports error_line 2 in Firefox", async ({
    playwright,
    baseURL,
  }) => {
    test.skip(!playwright.firefox, "Firefox browser not installed");
    const result = await bumpLineTwo(playwright.firefox, baseURL);
    expect(result.ok).toBe(false);
    expect(result.error_line).toBe(2);
  });
});
