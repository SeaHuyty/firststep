# Demo video script

About 5 minutes. A 3-minute cut is marked at the end. Each scene lists what to click or type, what the viewer sees, and the voiceover line. Button names are the app's own labels.

Every typed message below is one the real model (Gemma 4 26B) already handled correctly in the evidence runs (`server/evidence/gemma/`), so the recording does not depend on luck.

## Before recording

1. In `server/.env`: `LLM_PROVIDER=google`, the Gemma chain, and `LLM_TURN_TIMEOUT_S=70`. A typed message on the free tier takes about 13 s (up to about 55 s). **Cut the waiting in editing**; the buttons answer at once.
2. `npm run dev`, then open http://localhost:3000 in a clean browser window at 1280×800 or larger, zoom 100%, no bookmarks bar.
3. Do one practice run of the whole script. Then restart the server so the sessions are fresh, and record.
4. Record the screen without sound, then add the voiceover. Keep a slow pace: about 140 words a minute.

## Scenes

### 1. The problem (0:00–0:20)

**Screen:** the welcome page ("Your first investing plan").

**Voiceover:** "Most first-time investors don't fail by picking the wrong fund. They fail by investing money they'll need next month, while paying 22% on a credit card, then selling in the first crash. FirstStep is an advisor agent built to stop exactly that, before it gives any advice."

### 2. Amina hears "not yet" (0:20–0:50)

**Click:** "Try as Amina", then "Continue" (or "Save this debt") on each question; the marked answers are hers.

**Screen:** "Not yet, and here's why", with a savings plan and a date: "You could be ready to invest by…". There is no button to buy anything.

**Voiceover:** "Amina has $600 saved and $1,750 on a credit card at 22.9%. Sprout's guardian checks two rules first: an emergency fund of three months, and no debt above 8%. She fails both, so no investment tool exists for her at all. Instead she gets a step-by-step savings plan with a date. An advisor that can say 'not yet' is the first safety feature."

### 3. Leo: risk profile and plan (0:50–1:40)

**Click:** back to the welcome page, "Try as Leo", then "Continue" through the questions. Pause on the risk result ("Here's your risk level": C3 Balanced). On the goal page, click "Build my plan with $6,000 now".

**Screen:** "Your investment plan" (Home), then the "Plan" section: the mix by asset family and "What could happen", the range of outcomes by year.

**Voiceover:** "Leo is 27 with a stable job. The questions measure two things regulators care about: how much risk he's willing to take, and how much loss he can actually bear. His class is the lower of the two: C3, Balanced. His plan uses only funds rated at or below his level, with no single fund above 40%. Instead of one promised number, he sees a range from replaying 25 years of real markets: a bad case, a typical case and a good case."

### 4. Product comparison and a typed change (1:40–2:30)

**Click:** "Funds". Point at a fund marked "Above your level". Click "Compare" on a fund in the plan.

**Screen:** the side-by-side comparison with similar funds and its plain-words verdict on fees.

**Click:** "Ask Sprout". **Type:** `Compare the US Total Market Index Fund with the Star Manager Growth Fund.` (cut the wait)

**Voiceover:** "Comparison is in plain words: what each fund costs in dollars per $1,000 a year, how much it moves, and why the cheaper index fund wins here."

**Type:** `Swap the US Total Market fund for the US Large Company fund and keep the rest the same.` (cut the wait)

**Screen:** "Done: your plan now uses that fund", and the new range of outcomes.

**Voiceover:** "Leo types in his own words. The language model picks the tool and fills in the new mix, but it doesn't decide: the guardian re-checks suitability and concentration before anything changes."

### 5. Confirm: only a person can buy (2:30–3:05)

**Click:** "Home", then "Review the orders".

**Screen:** the dialog "Check before you confirm". "Confirm and place 6 orders" stays disabled until the box "I understand the value can go down as well as up." is ticked. Tick it, then click Confirm.

**Voiceover:** "Buying needs a one-time token, and only this Confirm click can create one. The model never sees it. So even if someone talks the model into 'buying', nothing can be bought without Leo's click. Orders also have limits: a single $50,000 order is refused."

### 6. Living through March 2020 (3:05–3:45)

**Click:** "Jump to March 2020".

**Screen:** "Simulated month: Mar 2020" and "Markets have dropped".

**Click:** "Ask Sprout". **Type:** `Sell everything now!` (cut the wait)

**Screen:** "Let's pause for 24 hours".

**Voiceover:** "The practice account replays real history. In March 2020 Leo's plan drops, and he panics. Selling right after a fall locks in the loss, so a big sale after a drop waits 24 hours, then Sprout asks again. A year later his plan has recovered; he paid in $11,100 and it is worth about $12,600."

### 7. Mei is refused, in plain words (3:45–4:15)

**Click:** welcome page, "Try as Mei", "Continue" through the questions, then "Build my plan with $20,000 now".

**Click:** "Ask Sprout". **Type:** `Put everything in tech stocks. They always go up.` (cut the wait)

**Screen:** "That doesn't fit your risk level", naming the rule and the fund: "Global Technology Fund is rated R4", and a C2 plan offered instead.

**Voiceover:** "Mei is 58 and careful: C2. She asks for all tech. The guardian refuses with a rule she can read, and Sprout offers a plan that fits her. This follows China's investor suitability rules: products are matched to the investor's risk level, fund by fund."

### 8. Every step on record (4:15–4:35)

**Click:** "Activity".

**Screen:** the audit log with "Chain verified".

**Voiceover:** "Every question, tool call, rule decision and order is written to a hash-chained audit log. Change one line and the chain breaks. A regulator, or a judge, can check exactly what the agent did and why."

### 9. Results (4:35–5:00)

**Screen:** `docs/results.png`, then `docs/architecture.png`.

**Voiceover:** "We tested it on Gemma 4, a free open-weight model. It completed [N] of 25 typed tasks from real users' words: profiling, planning, comparing and acting. It stopped all 30 red-team attacks, including prompt injection and attempts to buy without a click, and all four audit chains verify. The model talks; the guardian decides. FirstStep: a trustworthy first step into investing."

Fill in [N] from the first row of `server/evidence/gemma/metrics.md` before recording.

## The 3-minute cut

Keep scenes 1, 2 (shorter), 3 (risk result and plan only), 5, 6, 7 and 9. Drop scene 4's typed swap and scene 8, and in scene 9 say: "Every step is in a hash-chained audit log anyone can verify."

## If something goes wrong while recording

- **"Sorry, Sprout didn't answer in time" or "couldn't reach its model":** the free tier was slow. Type the same message again; your saved answers stay. Cut the failed attempt.
- **Gemma words a reply differently from the script:** that's fine. The result on screen (the tool card, the refusal, the pause) is what matters, and it comes from the guardian, not the model.
- **Running out of the free quota:** set `LLM_PROVIDER=fake` and record the scenes that use only buttons; the scripted model handles scenes 6 and 7 the same way.
