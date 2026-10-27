import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

type Preference = { provider: string; model: string };
const gemini = [
  "gemini-3.8-flash",
  "gemini-3.6-flash",
  "gemini-3.5-flash-lite",
  "gemini-2.5-flash",
];
const nvidia = ["nvidia/nemotron-3-ultra-550b-a55b"];
async function mockWorkspace(page: Page) {
  let active: Preference | null = null;
  let verified = false;
  let limited = false;
  let refreshes = 0;
  let generations = 0;
  const seen: Preference[] = [];
  const ws = {
    id: "models-workspace",
    name: "Model Studio",
    industry: "",
    website: "",
    description: "",
  };
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    let body: unknown = {};
    let status = 200;
    if (path.endsWith("/auth/me"))
      body = {
        user: { id: "user", name: "Taylor Reed", email: "taylor@example.com" },
        workspaces: [ws],
      };
    else if (path.endsWith("/workspaces")) body = [ws];
    else if (path.endsWith("/stages")) body = [];
    else if (path.endsWith("/qualification/templates"))
      body = { items: [], examples: {}, can_manage: true };
    else if (path.endsWith("/leads")) body = { items: [], next_cursor: null };
    else if (path.endsWith("/overview"))
      body = {
        total_leads: 0,
        qualified_leads: 0,
        active_leads: 0,
        qualification_rate: 0,
        sources: [],
        pipeline: [],
        recent_leads: [],
      };
    else if (path.endsWith("/ai/settings")) {
      if (request.method() === "PUT") {
        active = request.postDataJSON();
        body = active;
      } else
        body = {
          active,
          can_manage: true,
          providers: [
            { id: "gemini", name: "Google Gemini", configured: true },
            { id: "nvidia", name: "NVIDIA NIM", configured: true },
          ],
        };
    } else if (path.endsWith("/ai/models")) {
      if (url.searchParams.has("refresh")) refreshes++;
      const provider = url.searchParams.get("provider");
      body = {
        provider,
        models: (provider === "gemini" ? gemini : nvidia).map((id) => ({
          id,
          resource_name: provider === "gemini" ? `models/${id}` : id,
          name: id,
          family:
            provider === "gemini" ? `Gemini ${id.split("-")[1]}` : "Nemotron",
          capabilities: ["generateContent"],
          availability: limited
            ? "rate_limited"
            : verified
              ? "verified_working"
              : "available",
          source: "provider",
          free_tier: "unverified",
          checked_at: verified ? new Date().toISOString() : null,
        })),
        fetched_at: new Date().toISOString(),
        cached: false,
        stale: false,
        error: null,
      };
    } else if (path.endsWith("/ai/test")) {
      generations++;
      seen.push(request.postDataJSON());
      if (limited) {
        status = 429;
        body = {
          error: {
            code: "provider_rate_limit",
            message:
              "Provider rate limit or quota reached. Check quota reset time.",
          },
        };
      } else {
        verified = true;
        body = { ...request.postDataJSON(), text: "Connected", latency_ms: 8 };
      }
    } else if (path.endsWith("/ai/generate")) {
      generations++;
      body = {
        ...active,
        text: "A response from the saved model",
        latency_ms: 15,
        input_tokens: 3,
        output_tokens: 7,
      };
    }
    await route.fulfill({ status, json: body });
  });
  await page.goto("/#Settings");
  await expect(
    page.getByRole("heading", { name: "Workspace settings" }),
  ).toBeVisible();
  return {
    seen,
    refreshes: () => refreshes,
    generations: () => generations,
    limit: () => {
      limited = true;
    },
  };
}

test("dynamic catalogue search, refresh, explicit test, persistence and playground", async ({
  page,
}) => {
  const state = await mockWorkspace(page);
  await expect(
    page.getByLabel("Model", { exact: true }).locator("option"),
  ).toHaveCount(5);
  await expect(
    page.getByRole("button", { name: "Save as Default" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Refresh Models" }).click();
  await expect.poll(state.refreshes).toBe(1);
  expect(state.generations()).toBe(0);
  await page.getByRole("searchbox", { name: "Search models" }).fill("3.8");
  await expect(
    page.getByLabel("Model", { exact: true }).locator("option"),
  ).toHaveCount(2);
  await page
    .getByLabel("Model", { exact: true })
    .selectOption("gemini-3.8-flash");
  await expect(
    page.getByText("Free-tier eligibility unverified", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Test Model", exact: true }).click();
  await expect(page.locator(".success-box")).toContainText(
    "Verified working: gemini-3.8-flash",
  );
  expect(state.generations()).toBe(1);
  await page.screenshot({
    path: "../docs/evidence/ai-models-upgrade-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Save as Default" }).click();
  await expect(page.locator(".active-model")).toContainText("gemini-3.8-flash");
  await page.reload();
  await expect(page.getByLabel("Model", { exact: true })).toHaveValue(
    "gemini-3.8-flash",
  );
  await page.getByRole("radio", { name: /NVIDIA NIM/ }).click();
  await page.getByLabel("Model", { exact: true }).selectOption(nvidia[0]);
  await page.getByRole("button", { name: "Test Model", exact: true }).click();
  await expect(page.locator(".success-box")).toContainText(nvidia[0]);
  expect(state.seen.map((item) => item.provider)).toEqual(["gemini", "nvidia"]);
  await page.getByRole("button", { name: "Save as Default" }).click();
  await expect(page.locator(".active-model")).toContainText(nvidia[0]);
  await page
    .getByRole("button", { name: "AI Qualification AI", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Text playground", exact: true })
    .click();
  await page.getByLabel("Your AI prompt").fill("Hello");
  await page.getByRole("button", { name: "Send prompt" }).click();
  await expect(page.locator(".response-message")).toContainText(nvidia[0]);
});

test("quota errors are actionable and never claim free-tier verification", async ({
  page,
}) => {
  const state = await mockWorkspace(page);
  await page.getByLabel("Model", { exact: true }).selectOption(gemini[0]);
  state.limit();
  await page.getByRole("button", { name: "Test Model", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("quota reset time");
  await expect(page.locator(".model-availability")).toHaveText("Rate-limited");
  await expect(
    page.getByText("Free-tier eligibility unverified", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".success-box")).toHaveCount(0);
});

test("AI Models stays usable at mobile width and shows empty/error states", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockWorkspace(page);
  await page.getByLabel("Model", { exact: true }).selectOption(gemini[0]);
  await page.screenshot({
    path: "../docs/evidence/ai-models-upgrade-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.route("**/ai/models?**", (route) =>
    route.fulfill({
      json: {
        provider: "gemini",
        models: [],
        fetched_at: null,
        cached: false,
        stale: false,
        error: {
          code: "provider_auth",
          message: "API key is invalid or expired. Replace the server API key.",
        },
      },
    }),
  );
  await page.getByRole("button", { name: "Refresh Models" }).click();
  await expect(page.getByRole("alert")).toContainText("invalid or expired");
  await expect(
    page.getByText("No text-generation models found.", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Test Model", exact: true }),
  ).toBeDisabled();
});
