import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

test.use({ timezoneId: "Asia/Kolkata" });

async function navigate(page: Page, name: string) {
  const menu = page.getByRole("button", { name: "Open navigation" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name, exact: true }).click();
}

async function register(page: Page) {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Create a workspace", exact: true })
    .click();
  await page.getByLabel("Your name").fill("Channel Tester");
  await page
    .getByLabel("Workspace name", { exact: true })
    .fill("Fictional channel test business");
  await page
    .getByLabel("Work email")
    .fill(`s4-${crypto.randomUUID()}@example.com`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("Session4-browser-test-password!");
  await page
    .getByRole("button", { name: "Create your workspace", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Lead qualification pipeline" }),
  ).toBeVisible();
}

test("website setup, durable processing, inbox controls and secret rotation", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await register(page);
  await navigate(page, "Integrations");
  await expect(
    page.getByRole("heading", { name: "Connect your channels" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Create integration", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Save your new signing secret" }),
  ).toBeVisible();
  const secret = await page.locator(".channel-secret").textContent();
  expect(secret?.length).toBe(64);
  await page.getByRole("button", { name: "I have saved the secret" }).click();
  await expect(page.locator(".channel-secret")).toHaveCount(0);
  await page.getByRole("button", { name: "Queue fictional test" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Fictional test queued" }),
  ).toBeVisible();
  execFileSync(
    resolve("../backend/.venv/bin/python"),
    ["-m", "app.channel_worker", "--once"],
    {
      cwd: resolve("../backend"),
      env: {
        ...process.env,
        GEMINI_API_KEY: "",
        NVIDIA_API_KEY: "",
        META_CONNECTIONS: "{}",
      },
    },
  );
  await navigate(page, "Inbox");
  await expect(
    page.getByRole("heading", { name: "Webhook test prospect" }),
  ).toBeVisible();
  await expect(page.getByLabel("Message history")).toContainText(
    "Explicit integration test",
  );
  await expect(page.getByLabel("Manual reply")).toBeDisabled();
  await page
    .getByLabel("Control reason")
    .fill("Resume qualification for new enquiries");
  await page.getByRole("button", { name: "Resume AI", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Enable integration AI policy first",
  );
  await navigate(page, "Integrations");
  await page
    .getByRole("button", { name: "Enable AI qualification", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Disable AI qualification", exact: true }),
  ).toBeVisible();
  await navigate(page, "Inbox");
  await page
    .getByLabel("Control reason")
    .fill("Resume qualification for new enquiries");
  await page.getByRole("button", { name: "Resume AI", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Take over", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Control reason")
    .fill("A salesperson is handling this enquiry");
  await page.getByRole("button", { name: "Take over", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Resume AI", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Message history")).toContainText(
    "A salesperson is handling this enquiry",
  );
  await page.screenshot({
    path: "../docs/evidence/session-4-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(async () =>
      page
        .locator(".sidebar")
        .evaluate((element) =>
          Math.round(element.getBoundingClientRect().right),
        ),
    )
    .toBeLessThanOrEqual(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../docs/evidence/session-4-mobile.png",
    fullPage: true,
  });
  await navigate(page, "Integrations");
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByRole("button", { name: "Rotate secret", exact: true })
    .click();
  await expect(page.locator(".channel-secret")).toBeVisible();
  expect(await page.locator(".channel-secret").textContent()).not.toBe(secret);
  await page.reload();
  await expect(page.locator(".channel-secret")).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});
