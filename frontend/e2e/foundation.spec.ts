import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";

async function register(page: Page) {
  const email = `browser-${crypto.randomUUID()}@example.com`;
  await page.goto("/");
  await page
    .getByRole("button", { name: "Create a workspace", exact: true })
    .click();
  await page.getByLabel("Your name").fill("Taylor Reed");
  await page
    .getByLabel("Workspace name", { exact: true })
    .fill("Browser workspace");
  await page.getByLabel("Work email").fill(email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("Browser-test-password-2026!");
  await page
    .getByRole("button", { name: "Create your workspace", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Lead qualification pipeline" }),
  ).toBeVisible();
  return email;
}

async function createLead(page: Page) {
  await page.getByRole("button", { name: "New lead", exact: true }).click();
  await page.getByLabel("Full name", { exact: true }).fill("Sam Rivera");
  await page.getByLabel("Company", { exact: true }).fill("Orbit Studio");
  await page.getByLabel("Email address").fill("sam@example.com");
  await page.getByLabel("Potential value (USD)").fill("12500");
  await page
    .getByLabel("Summary", { exact: true })
    .fill("Ready for a product walkthrough.");
  await page.getByRole("button", { name: "Create lead", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Open Orbit Studio" }),
  ).toBeVisible();
}

test("register, CRUD, notes, persisted drag-and-drop and search", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await register(page);
  await createLead(page);
  await page.getByRole("button", { name: "Open Orbit Studio" }).click();
  await page.getByLabel("Add a note").fill("Follow up on Tuesday");
  await page.getByRole("button", { name: "Add note", exact: true }).click();
  await expect(
    page.getByText("Follow up on Tuesday", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Qualification status", { exact: true })
    .selectOption("qualified");
  await page.getByRole("button", { name: "Save changes" }).click();
  const card = page.locator(".lead-card").filter({ hasText: "Orbit Studio" });
  const contacted = page.locator(".kanban-column").filter({
    has: page.getByRole("heading", { name: "Contacted", exact: true }),
  });
  await card.dragTo(contacted);
  await expect(
    contacted.getByRole("button", { name: "Open Orbit Studio" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    contacted.getByRole("button", { name: "Open Orbit Studio" }),
  ).toBeVisible();
  await page.getByLabel("Search leads", { exact: true }).fill("not-found");
  await expect(
    page.getByRole("button", { name: "Open Orbit Studio" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Clear search", exact: true }).click();
  await page.getByLabel("Search workspace leads").fill("Orbit");
  await page
    .locator(".search-results")
    .getByRole("button")
    .filter({ hasText: "Sam Rivera" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Good people. Great possibilities." }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Sam Rivera sam@example.com/ }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /Sam Rivera sam@example.com/ })
    .click();
  await page.getByRole("button", { name: "Delete lead", exact: true }).click();
  await page.getByRole("button", { name: "Keep lead", exact: true }).click();
  await page.getByRole("button", { name: "Delete lead", exact: true }).click();
  await page.getByRole("button", { name: "Delete lead", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "A fresh start for your pipeline" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("AI preferences survive reload and playground displays real missing-key errors", async ({
  page,
}) => {
  await register(page);
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByRole("radio", { name: /NVIDIA NIM/ }).click();
  await page
    .getByLabel("Model", { exact: true })
    .selectOption("nvidia/nemotron-3-ultra-550b-a55b");
  await page.getByRole("button", { name: "Save as Default" }).click();
  await expect(
    page.getByText("Workspace default", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByRole("radio", { name: /NVIDIA NIM/ })).toHaveAttribute(
    "aria-checked",
    "true",
  );
  await page.getByRole("button", { name: "Test Model", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("NVIDIA_API_KEY");
  await page
    .getByRole("button", { name: "AI Qualification AI", exact: true })
    .click();
  await page.getByLabel("Your AI prompt").fill("Hello from the browser test");
  await page.getByRole("button", { name: "Send prompt" }).click();
  await expect(page.getByRole("alert")).toContainText("NVIDIA_API_KEY");
  await expect(
    page
      .locator(".prompt-message")
      .getByText("Hello from the browser test", { exact: true }),
  ).toBeVisible();
});

test("workspace switching isolates data and logout revokes the session", async ({
  page,
}) => {
  await register(page);
  await createLead(page);
  await page.getByLabel("Current workspace").selectOption("__new");
  await page
    .getByRole("dialog")
    .getByLabel("Workspace name", { exact: true })
    .fill("Isolated workspace");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Create workspace", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Your pipeline" }),
  ).toContainText("Isolated workspace");
  await expect(
    page.getByRole("button", { name: "Open Orbit Studio" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(
    page.getByRole("heading", { name: "Good to see you again." }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Good to see you again." }),
  ).toBeVisible();
});

test("mobile navigation and dialogs fit within the viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await register(page);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await createLead(page);
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Workspace settings" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("button", { name: "Inbox", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Every conversation, connected." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "About EasyCRM" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
