import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const password = "correct-horse-battery";
const admin = {
  first: "Ada",
  last: "Admin",
  email: "ada@example.com",
};
const learner = {
  first: "Lee",
  last: "Learner",
  email: "lee@example.com",
};

function setupToken() {
  const started = Date.now();
  let logs = "";
  while (Date.now() - started < 60_000) {
    logs = execFileSync("docker", ["compose", "logs", "backend"], {
      cwd: root,
      encoding: "utf8",
    });
    const matches = [...logs.matchAll(/GHOSTLINE SETUP TOKEN: (\S+)/g)];
    if (matches.length > 0) {
      return matches[matches.length - 1][1];
    }
    execFileSync("sleep", ["1"]);
  }
  throw new Error("The backend did not print a setup token");
}

async function signIn(page, email) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Signed in as");
}

async function signOut(page) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("link", { name: "Login" })).toBeVisible();
}

test.describe.configure({ mode: "serial" });

test("setup creates the admin", async ({ page }) => {
  const token = setupToken();
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Create the admin account" })).toBeVisible();
  await page.getByLabel("Setup token").fill(token);
  await page.getByLabel("First name").fill(admin.first);
  await page.getByLabel("Last name").fill(admin.last);
  await page.getByLabel("Email").fill(admin.email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create admin" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await signIn(page, admin.email);
  await expect(page.getByText("ada@example.com")).toBeVisible();
});

test("the demo lesson opens without an account", async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto("/demo");
  await expect(page.getByRole("heading", { name: "Try a lesson" })).toBeVisible();
  await page.getByRole("link", { name: "Start" }).first().click();
  await expect(page.getByRole("heading", { name: "List the files" })).toBeVisible();
  await expect(page.getByText("Type the command that lists every file")).toBeVisible();
  await context.close();
});

test("signup and a typed lesson", async ({ page }) => {
  await page.goto("/signup");
  await page.getByLabel("First name").fill(learner.first);
  await page.getByLabel("Last name").fill(learner.last);
  await page.getByLabel("Email").fill(learner.email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByText("Account created. You can sign in and start practicing.")).toBeVisible();

  await signIn(page, learner.email);
  await page.getByRole("link", { name: "Continue: List the files" }).click();
  await expect(page.getByRole("heading", { name: "List the files" })).toBeVisible();
  const editor = page.locator(".cm-content");
  await editor.click();
  await page.keyboard.type("ls -la", { delay: 40 });
  await expect(page.getByText("Passed.")).toBeVisible();
});

test("an admin can add a module", async ({ page }) => {
  await signIn(page, admin.email);
  await page.getByRole("link", { name: "Content", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Content" })).toBeVisible();
  const title = page.getByLabel("New module in Bash");
  await title.fill("Release check");
  await title.locator("xpath=..").getByRole("button", { name: "Add module" }).click();
  await expect(page.getByRole("button", { name: "Release check · draft" })).toBeVisible();
});
