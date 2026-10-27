import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";

function pdfFixture() {
  const stream =
    "BT /F1 12 Tf 50 700 Td (Fictional delivery takes 5 days.) Tj ET";
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
  ];
  let raw = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((object, index) => {
    offsets.push(raw.length);
    raw += `${index + 1} 0 obj\n${object}\nendobj\n`;
  });
  const xref = raw.length;
  raw +=
    "xref\n0 6\n0000000000 65535 f \n" +
    offsets
      .slice(1)
      .map((offset) => `${String(offset).padStart(10, "0")} 00000 n \n`)
      .join("");
  return Buffer.from(
    raw + `trailer << /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`,
  );
}

async function navigate(page: Page, name: string) {
  const menu = page.getByRole("button", { name: "Open navigation" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name, exact: true }).click();
}

test("review-first PDF knowledge, real-record analytics and mobile layout", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page
    .getByRole("button", { name: "Create a workspace", exact: true })
    .click();
  await page.getByLabel("Your name").fill("Release Tester");
  await page
    .getByLabel("Workspace name", { exact: true })
    .fill("Fictional release workspace");
  await page
    .getByLabel("Work email")
    .fill(`s5-${crypto.randomUUID()}@example.com`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("Session5-browser-test-password!");
  await page
    .getByRole("button", { name: "Create your workspace", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Lead qualification pipeline" }),
  ).toBeVisible();
  await navigate(page, "Analytics");
  await expect(
    page.getByText("No leads were created in this window.", { exact: false }),
  ).toBeVisible();
  await navigate(page, "Knowledge Base");
  await page.getByRole("button", { name: "PDF document", exact: true }).click();
  await page
    .getByLabel("Source title", { exact: true })
    .fill("Fictional delivery policy");
  await page.getByLabel("Text PDF", { exact: true }).setInputFiles({
    name: "fictional-policy.pdf",
    mimeType: "application/pdf",
    buffer: pdfFixture(),
  });
  await page
    .getByLabel("I am authorized to import this business content.")
    .check();
  await page
    .getByRole("button", { name: "Import for review", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Review business source", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "Extracted text", exact: true }),
  ).toHaveValue("Fictional delivery takes 5 days.");
  await page.getByRole("button", { name: "Close dialog", exact: true }).click();
  await page.getByLabel("Business question", { exact: true }).fill("delivery");
  await page
    .getByRole("button", { name: "Search approved sources", exact: true })
    .click();
  await expect(
    page.getByText("No approved source supports this query.", { exact: false }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Review source", exact: true })
    .click();
  await page
    .getByLabel("I reviewed the text and approve it for retrieval")
    .check();
  await page
    .getByRole("button", { name: "Save source review", exact: true })
    .click();
  await expect(
    page.getByText("Source review saved.", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Search approved sources", exact: true })
    .click();
  await expect(page.locator("blockquote")).toContainText(
    "Fictional delivery takes 5 days.",
  );
  await page.screenshot({
    path: "../docs/evidence/session-5-knowledge-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page
        .locator(".sidebar")
        .evaluate((element) => element.getBoundingClientRect().right <= 0),
    )
    .toBe(true);
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
  await page.screenshot({
    path: "../docs/evidence/session-5-knowledge-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page
    .getByRole("button", { name: "Remove source", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm removal", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Start with trusted information" }),
  ).toBeVisible();
  await navigate(page, "Analytics");
  await page.getByLabel("Start date (UTC, inclusive)").fill("2099-01-01");
  await page.getByRole("button", { name: "Apply dates", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "A fresh perspective starts here" }),
  ).toBeVisible();
  await page
    .getByText("Metric definitions and exclusions", { exact: true })
    .click();
  await expect(
    page.getByText("Currently qualified leads divided", { exact: false }),
  ).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
  await page.screenshot({
    path: "../docs/evidence/session-5-analytics-mobile.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
