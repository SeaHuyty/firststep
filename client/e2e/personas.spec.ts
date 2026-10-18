// The three demo personas, clicked through like a first-time user: the question pages, then the
// dashboard (Home, Plan, Funds, Activity) with Sprout in the chat panel. Screenshots of each main
// screen are saved for review at both widths.
import { expect, type Page, test } from "@playwright/test";

// Phones scroll as one page; desktop shows the viewport.
const shot = async (page: Page, name: string) => {
  // Let the words, cards and charts finish arriving, so the picture shows the settled screen.
  await page.waitForTimeout(1500);
  await page.screenshot({
    path: `e2e-results/${test.info().project.name}-${name}.png`,
    fullPage: test.info().project.name === "phone",
  });
};

async function startAs(page: Page, name: string) {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Your first investing plan/ })).toBeVisible();
  await expect(page.getByText("How old are you?")).toBeVisible();
  await shot(page, "welcome");
  await page.getByRole("button", { name: new RegExp(`^${name}`) }).click();
  await expect(page).toHaveURL(/\/s\//);
  await expect(page.getByText(`Demo as ${name}`)).toBeVisible();
}

/** Go through the question pages with the demo person's marked answers, like a person would. */
async function answerAsSuggested(page: Page, until: RegExp) {
  const done = page.getByText(until).filter({ visible: true }).first();
  for (let i = 0; i < 30; i++) {
    const cont = page.getByRole("button", { name: /^Continue/ });
    const save = page.getByRole("button", { name: /^Save( this debt| these \d+ debts)?$/ });
    await cont.or(save).or(done).first().waitFor({ timeout: 15_000 });
    if (await done.isVisible()) return;
    const heading = page.getByRole("heading", { level: 1 });
    const before = await heading.textContent();
    if (await cont.isVisible()) await cont.click();
    else await save.filter({ visible: true }).first().click();
    // Wait for the next page (a new question or result) before answering again.
    await expect(heading).not.toHaveText(before ?? "", { timeout: 15_000 });
  }
  await expect(done).toBeVisible();
}

const nav = (page: Page, name: "Home" | "Plan" | "Funds" | "Activity") =>
  page.getByRole("navigation", { name: "Sections" }).getByRole("button", { name, exact: true }).click();

async function askSprout(page: Page, text: string) {
  await page.getByRole("button", { name: "Ask Sprout" }).click();
  await page.getByLabel("Message Sprout").fill(text);
  await page.getByLabel("Message Sprout").press("Enter");
}

test("Leo compares funds, confirms a plan, lives through March 2020 and a panic sale waits", async ({ page }) => {
  await startAs(page, "Leo");
  await shot(page, "leo-question");
  await answerAsSuggested(page, /What are you investing for/);
  await page.getByRole("button", { name: /Build my plan with \$6,000 now/ }).click();
  await expect(page.getByRole("heading", { name: "Your investment plan" })).toBeVisible();
  await expect(page.getByText("C3 Balanced").filter({ visible: true }).first()).toBeVisible();
  await shot(page, "leo-home");

  await nav(page, "Plan");
  await expect(page.getByRole("heading", { name: "C3 Balanced plan" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /if you stick with the plan/ })).toBeVisible();
  await shot(page, "leo-plan");

  // Product comparison and the fund library: the fund in the plan next to a peer.
  await nav(page, "Funds");
  await expect(page.getByRole("heading", { name: "The fund library" })).toBeVisible();
  await expect(page.getByText(/Above your level/).filter({ visible: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Compare" }).first().click();
  await expect(page.getByText(/next to similar funds/).filter({ visible: true }).first()).toBeVisible();
  await shot(page, "leo-compare");

  await nav(page, "Home");
  await page.getByRole("button", { name: "Review the orders" }).click();
  const dialog = page.getByRole("dialog", { name: "Check before you confirm" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Cancel" })).toBeFocused();
  const confirm = dialog.getByRole("button", { name: "Confirm and place 6 orders" });
  await expect(confirm).toBeDisabled();
  await shot(page, "leo-confirm");
  await dialog.getByLabel("I understand the value can go down as well as up.").check();
  await confirm.click();
  await expect(dialog).toBeHidden();

  await expect(page.getByRole("heading", { name: "Your practice account" })).toBeVisible();
  await page.getByRole("button", { name: "Jump to March 2020" }).click();
  await expect(page.getByText("Simulated month: Mar 2020")).toBeVisible();
  await expect(page.getByText("Markets have dropped").filter({ visible: true }).first()).toBeVisible();
  await askSprout(page, "Sell everything now!");
  await expect(page.getByText("Let's pause for 24 hours").filter({ visible: true }).first()).toBeVisible();
  await shot(page, "leo-cooling-off");
});

test("Amina hears 'not yet' and gets a savings plan, with no way to order", async ({ page }) => {
  await startAs(page, "Amina");
  await answerAsSuggested(page, /Your plan for now/);
  await expect(page.getByText("Not yet, and here's why").filter({ visible: true }).first()).toBeVisible();
  await expect(page.getByText(/You could be ready to invest by/).filter({ visible: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: /Review/ })).toHaveCount(0);
  await shot(page, "amina-not-yet");

  // The audit log is one page away and verifies its chain.
  await nav(page, "Activity");
  await expect(page.getByText("Chain verified")).toBeVisible();
});

test("Mei asks for all tech, is refused, and is offered a C2 plan", async ({ page }) => {
  await startAs(page, "Mei");
  await answerAsSuggested(page, /What are you investing for/);
  await page.getByRole("button", { name: /Build my plan with \$20,000 now/ }).click();
  await expect(page.getByRole("heading", { name: "Your investment plan" })).toBeVisible();
  await askSprout(page, "Put everything in tech stocks. They always go up.");
  await expect(page.getByText("That doesn't fit your risk level").filter({ visible: true }).first()).toBeVisible();
  await expect(page.getByText(/Global Technology Fund is rated R4/).filter({ visible: true }).first()).toBeVisible();
  await shot(page, "mei-refusal");
});

test("a visitor answers the first question on the welcome page and carries on", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("How old are you?")).toBeVisible();
  await page.getByRole("button", { name: "25–34" }).click();
  await expect(page).toHaveURL(/\/s\//);
  // The answer is saved: the next question page is about income, and stays so after a reload.
  await expect(page.getByRole("heading", { name: /How much money comes in each month/ })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: /How much money comes in each month/ })).toBeVisible();
  // Back to the welcome page: everything works again (it is kept alive, not reloaded).
  await page.goBack();
  await expect(page.getByRole("button", { name: "35–44" })).toBeEnabled();
  await expect(page.getByRole("button", { name: /Try as Leo/ })).toBeEnabled();
});

test("going back after starting a demo leaves the welcome page usable", async ({ page }) => {
  await startAs(page, "Leo");
  await page.goBack();
  await expect(page.getByRole("button", { name: /Try as Mei/ })).toBeEnabled();
  await expect(page.getByRole("button", { name: "18–24" })).toBeEnabled();
});
