// The three demo personas, clicked through like a first-time user (docs/standards/frontend.md
// section 5). Screenshots of each main screen are saved for review at both widths.
import { expect, type Page, test } from "@playwright/test";

const shot = (page: Page, name: string) =>
  page.screenshot({ path: `e2e-results/${test.info().project.name}-${name}.png`, fullPage: true });

async function startAs(page: Page, name: string) {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Your first investing plan/ })).toBeVisible();
  await shot(page, "welcome");
  await page.getByRole("button", { name: new RegExp(`^${name}`) }).click();
  await expect(page).toHaveURL(/\/s\//);
  await expect(page.getByText(`Demo: you are ${name}`)).toBeVisible();
}

/** Tap the suggested ("demo answer") chip or the debt answer, question by question, waiting
 * for Sprout to finish typing each one, like a person would. */
async function answerAsSuggested(page: Page, untilText: RegExp) {
  const done = page.getByText(untilText).filter({ visible: true }).first();
  for (let i = 0; i < 30; i++) {
    const suggested = page.getByRole("button").filter({ hasText: "demo answer" }).first();
    const saveDebts = page.getByRole("button", { name: /^Save( this debt| these \d+ debts)?$/ });
    const noDebts = page.getByRole("button", { name: "No debts" });
    await suggested.or(saveDebts).or(noDebts).or(done).first().waitFor({ timeout: 10_000 });
    if (await done.isVisible()) return;
    if (await suggested.isVisible()) await suggested.click();
    else if (await saveDebts.isVisible()) await saveDebts.click();
    else await noDebts.click();
    await expect(page.getByText("Sprout is thinking…")).toHaveCount(0, { timeout: 10_000 });
  }
  await expect(done).toBeVisible();
}

function planOrChat(page: Page, which: "My plan" | "Chat") {
  return async () => {
    const tab = page.getByRole("tab", { name: which });
    if (await tab.isVisible()) await tab.click();
  };
}

test("Leo confirms a plan, lives through March 2020 and a panic sale waits", async ({ page }) => {
  await startAs(page, "Leo");
  await answerAsSuggested(page, /what are you investing for/i);
  await page.getByRole("button", { name: /Build my plan with \$6,000 now/ }).click();
  await planOrChat(page, "My plan")();
  await expect(page.getByRole("heading", { name: /if you stick with the plan/ })).toBeVisible();
  await expect(page.getByText("C3 Balanced").filter({ visible: true }).first()).toBeVisible();
  await shot(page, "leo-plan");
  await planOrChat(page, "Chat")();
  await page.getByRole("button", { name: "Review the orders" }).click();
  await page.getByRole("button", { name: "Review 6 orders" }).click();

  const dialog = page.getByRole("dialog", { name: "Check before you confirm" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Cancel" })).toBeFocused();
  const confirm = dialog.getByRole("button", { name: "Confirm and place 6 orders" });
  await expect(confirm).toBeDisabled();
  await shot(page, "leo-confirm");
  await dialog.getByLabel("I understand the value can go down as well as up.").check();
  await confirm.click();
  await expect(dialog).toBeHidden();

  await planOrChat(page, "My plan")();
  await expect(page.getByRole("heading", { name: /is invested/ })).toBeVisible();
  await page.getByRole("button", { name: "Jump to March 2020" }).click();
  await expect(page.getByText("Simulated month: Mar 2020")).toBeVisible();
  await planOrChat(page, "Chat")();
  await expect(page.getByText("Markets have dropped").filter({ visible: true }).first()).toBeVisible();
  await page.getByLabel("Message Sprout").fill("Sell everything now!");
  await page.getByLabel("Message Sprout").press("Enter");
  await expect(page.getByText("Let's pause for 24 hours").filter({ visible: true }).first()).toBeVisible();
  await shot(page, "leo-cooling-off");
});

test("Amina hears 'not yet' and gets a savings plan, with no way to order", async ({ page }) => {
  await startAs(page, "Amina");
  await answerAsSuggested(page, /Not yet, and here's why/);
  await expect(page.getByText(/You could be ready to invest by/).filter({ visible: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: /Review/ })).toHaveCount(0);
  await planOrChat(page, "My plan")();
  await shot(page, "amina-not-yet");
});

test("Mei asks for all tech, is refused, and is offered a C2 plan", async ({ page }) => {
  await startAs(page, "Mei");
  await answerAsSuggested(page, /what are you investing for/i);
  await page.getByRole("button", { name: /Build my plan with \$20,000 now/ }).click();
  await expect(page.getByText(/Here's a range of what could happen|range of what could happen/).filter({ visible: true }).first()).toBeVisible();
  await page.getByLabel("Message Sprout").fill("Put everything in tech stocks. They always go up.");
  await page.getByLabel("Message Sprout").press("Enter");
  await expect(page.getByText("That doesn't fit your risk level").filter({ visible: true }).first()).toBeVisible();
  await expect(page.getByText(/Global Technology Fund is rated R4/).filter({ visible: true }).first()).toBeVisible();
  await shot(page, "mei-refusal");
});

test("the audit log verifies its chain", async ({ page }) => {
  await startAs(page, "Leo");
  const tab = page.getByRole("tab", { name: "Audit log" });
  if (await tab.isVisible()) await tab.click();
  else await page.getByText("See the audit log").click();
  await expect(page.getByText("Chain verified").filter({ visible: true })).toBeVisible();
});
