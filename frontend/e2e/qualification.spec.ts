import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";

async function register(page: Page) {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Create a workspace", exact: true })
    .click();
  await page.getByLabel("Your name").fill("Qualification Tester");
  await page
    .getByLabel("Workspace name", { exact: true })
    .fill("Fictional Session 3 business");
  await page
    .getByLabel("Work email")
    .fill(`s3-${crypto.randomUUID()}@example.com`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("Session3-browser-test-password!");
  await page
    .getByRole("button", { name: "Create your workspace", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Lead qualification pipeline" }),
  ).toBeVisible();
}

async function navigate(page: Page, name: string) {
  const menu = page.getByRole("button", { name: "Open navigation" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name, exact: true }).click();
}

async function prepare(page: Page) {
  await register(page);
  await navigate(page, "Settings");
  await page.getByRole("radio", { name: /NVIDIA NIM/ }).click();
  await page
    .getByLabel("Model", { exact: true })
    .selectOption("nvidia/nemotron-3-ultra-550b-a55b");
  await page.getByRole("button", { name: "Save as Default" }).click();
  await expect(
    page.getByText("Workspace default", { exact: true }),
  ).toBeVisible();
  await navigate(page, "AI Qualification AI");
  await page
    .getByRole("button", { name: "Qualification rules", exact: true })
    .click();
  await page.getByRole("button", { name: "Use generic B2B example" }).click();
  await page.getByLabel("Template name").fill("Fictional B2B rules");
  await page.getByRole("button", { name: "Save new rule version" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Saved Fictional B2B rules" }),
  ).toBeVisible();
}

test("rule editor, persisted opt-out, blocked resumption and responsive UI", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await prepare(page);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page
    .getByRole("button", { name: "Conversation simulator", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Create fictional sample lead" })
    .click();
  await page
    .getByLabel("Prospect message")
    .fill("Please unsubscribe and do not contact me");
  await page.getByRole("button", { name: "Send simulator message" }).click();
  await expect(page.locator(".qualification-score")).toContainText("Closed");
  await expect(page.locator(".qualification-score")).toContainText(
    "Customer opted out",
  );
  await expect(
    page.getByRole("button", { name: "Resume AI", exact: true }),
  ).toBeDisabled();
  const selection = await page
    .getByLabel("CRM lead", { exact: true })
    .inputValue();
  await page.reload();
  await page.getByLabel("CRM lead", { exact: true }).selectOption(selection);
  await expect(page.locator(".qualification-score")).toContainText("Closed");
  await expect(
    page.getByText("Message saved · AI did not reply", { exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../docs/evidence/session-3-mobile.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("full simulator uses test provider with real persistence, citations, scoring and CRM override", async ({
  page,
}) => {
  test.skip(
    process.env.PLAYWRIGHT_QUALIFICATION_FIXTURE !== "1",
    "Requires the explicit fictional provider fixture launcher",
  );
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await prepare(page);
  await page
    .getByRole("button", { name: "Business sources", exact: true })
    .click();
  await page.getByLabel("Source title").fill("Fictional delivery policy");
  await page.getByLabel("Verified source text").fill("Delivery takes 5 days.");
  await page.getByRole("checkbox", { name: /I have reviewed/ }).check();
  await page.getByRole("button", { name: "Add business source" }).click();
  await expect(
    page.getByRole("heading", { name: "Fictional delivery policy" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Conversation simulator", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Create fictional sample lead" })
    .click();
  await page
    .getByLabel("Prospect message")
    .fill(
      "I need software next month, I am the owner. What is your delivery policy?",
    );
  await page.getByRole("button", { name: "Send simulator message" }).click();
  await expect(page.locator(".qualification-score")).toContainText("75");
  await expect(page.locator(".qualification-turn blockquote")).toContainText(
    "Delivery takes 5 days.",
  );
  await expect(page.locator(".response-message")).toContainText(
    "What is your budget in USD?",
  );
  await page.getByLabel("Prospect message").fill("My budget is 5000");
  await page.getByRole("button", { name: "Send simulator message" }).click();
  await expect(page.locator(".qualification-score")).toContainText("Qualified");
  await expect(page.locator(".qualification-score > div > strong")).toHaveText(
    "100",
  );
  await expect(
    page.getByRole("heading", { name: "Human control", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "../docs/evidence/session-3-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "View CRM lead" }).click();
  await page.getByRole("button", { name: /Simulator prospect/ }).click();
  await expect(
    page.getByRole("dialog").locator(".qualification-score"),
  ).toContainText("100");
  await page
    .getByLabel("Reason for control change")
    .fill("Fictional human review exercise");
  await page
    .getByLabel("Human decision", { exact: true })
    .selectOption("needs_human");
  await page.getByRole("button", { name: "Record human override" }).click();
  await expect(
    page.getByRole("dialog").locator(".qualification-score"),
  ).toContainText("Needs human");
  await expect(
    page.getByLabel("Qualification status", { exact: true }),
  ).toHaveValue("needs-human");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("table")).toContainText("Needs human");
  await page.reload();
  await expect(page.locator(".badge.needs-human").first()).toBeVisible();
  expect(errors).toEqual([]);
});
