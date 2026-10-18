# Presentation: speaker notes

What to say on each slide, about 40 seconds each, 10 minutes in all. The slides are in [`pdf/presentation.pdf`](pdf/presentation.pdf); their source is [`slides/presentation.html`](slides/presentation.html).

## 1. FirstStep

Hello, we are [team name] from [university]. FirstStep is our answer to Topic B, the wealth advisory agent. In one line: it’s an advisor built for people investing for the first time, where the language model does the talking and a deterministic rules engine, the guardian, makes every decision. Nothing is bought until the person clicks Confirm.

## 2. First-time investors rarely fail by picking the wrong fund.

Our starting point: first-time investors rarely lose because they picked the wrong fund. They lose because they invest money they’ll need soon, while paying 20 percent on a credit card; because they take more risk than they can bear; and because they sell in the first crash. A chatbot advisor can make all three worse. It can be talked into promising returns, into recommending something unsuitable, or into placing an order the person never really approved. So we asked: what would a trustworthy first advisor look like?

## 3. A professional advisory workflow, as one closed loop

FirstStep follows the workflow a professional adviser uses, as one closed loop. First a money check: an emergency fund and no expensive debt. If you fail, Sprout says “not yet” and gives you a savings plan. Then risk profiling, product comparison, an allocation with a range of outcomes, execution in a sandbox account, and monitoring through real market history. Every step is a tool call, and every step has a named rule behind it, shown in the last column.

## 4. The LLM talks. The guardian decides.

This is the one idea the whole system is built on. The language model talks: it understands what the person typed, chooses a tool and explains the result in plain words. But it never decides. Every number comes from tested code, every tool call is checked by a deterministic guardian against rules with IDs, and buying needs a token that only the person’s Confirm click can create. The model never even sees that token.

## 5. Three ways in, one gate, one record

Here is the architecture. There are three ways in: tapping an answer button, typing a message, and pressing Confirm. All three reach one executor. Typed text first passes an input guard that masks personal data and flags injection attempts. Then the model picks a tool, but the guardian checks every call against the rules: is this tool allowed at this step, is the fund suitable, is the mix diversified, is it within limits, and was it really confirmed. Only then does the tool run. Refusals come back as plain-words cards. And every message, call, decision and fill goes into a hash-chained audit log, so any later edit is detectable.

## 6. Amina hears “not yet”

Our first demo person is Amina: 21, 600 dollars saved and 1,750 on a credit card at almost 23 percent. She fails both money checks. At this stage, no investment tool exists for her: not for the buttons, not for the model, whatever she types. Instead Sprout gives her a step-by-step plan with a date: a small buffer, then the card, then the emergency fund, about 20 months. Most robo-advisers would happily sell her a portfolio. We think saying “not yet” is the first safety feature.

## 7. Leo gets a C3 plan and a range, not a promise

Leo is 27 with a stable job. The questions come one per page, each with a reason. Following regulators’ guidance, we measure two things: how much risk he’s willing to take, and how much loss he can actually bear. His class is the lower of the two, C3, Balanced. His plan uses only funds rated at or below C3, with no fund above 40 percent. And instead of one promised number, he sees a range from replaying 25 years of real markets: about 47 thousand in a bad case, 59 typical, 72 good, on 42 thousand paid in.

## 8. Typed in his own words, checked by the rules

Product comparison is one of the three parts of Topic B. In the fund library, every fund can be compared with similar funds: what it costs in dollars per thousand a year, how risky it is, its worst year, and a plain-words verdict on why the cheaper index fund wins. And Leo can simply type what he wants. Here he asks to swap one fund for another. The model turns that into a tool call with the whole new mix, but it still doesn’t decide: the guardian re-checks suitability and concentration before anything changes.

## 9. Only a person can buy. A panic sale waits a day.

When Leo is happy, he reviews the orders. The Confirm button stays disabled until he ticks that the value can go down as well as up. That click, and only that click, creates a one-time signed token bound to these exact orders. The model never sees it, so no prompt can make it buy. Orders also have limits. Then we replay real history. In March 2020 his plan drops and he types “Sell everything now!”. Selling right after a fall locks in the loss, so a big sale after a drop waits 24 hours, and then Sprout asks again. A year later, the 11,100 dollars he paid in is worth about 12,640.

## 10. Mei is refused, in words she can read

Our third person, Mei, is 58 and careful: class C2. She asks for everything in tech stocks. The guardian refuses with a rule she can read: the technology fund is rated R4, above her level. And Sprout doesn’t just say no; it offers a plan that fits her. The matching follows China’s investor suitability rules, checked fund by fund at every step: when listing, proposing and ordering.

## 11. Permission tiers: the model can draft, never execute

Security is 30 percent of the score, so here is how it works. Every tool has a permission tier. Tiers 0 and 1 read and draft; the model may call them, but the guardian checks every call. Tier 2, placing orders, is never even offered to the model: only the Confirm click can call it, with a one-time token. Tier 3, selling, can start a cooling-off pause, and even then the sale is only a draft. Around that sit an input guard, a language filter that blocks guarantees and predictions, and a tamper-evident audit log. This follows the OWASP guidance for LLM apps on prompt injection and excessive agency. The key point: no defence depends on the model behaving.

## 12. Gemma 4 26B, a free open-weight model, judged from the audit log

We tested on Gemma 4, a free, open-weight model, so a bank could run the same model on its own servers. 25 requests typed the way a first-time investor would, across profiling, planning, comparison, dialogue, acting and monitoring: it completed all 25, judged from the tools it actually called and their arguments, not from its wording. 30 red-team attacks, from prompt injection to panic selling: all 30 handled safely, and nothing ever filled without a click. All audit chains verify, and 223 automated tests pass.

## 13. Every miss was a missed action, never an unsafe one

We want to be honest about what testing found. A real model does miss sometimes. It saved a range midpoint instead of the exact income someone typed; it gave a definition when asked what could happen to their money; one turn was lost when it made one tool call too many. Each one we traced and fixed in code. But notice: every miss was a missed action, never an unsafe one, because the guardian bounds what any mistake can do. Our known limits: a free model is slow, about 13 seconds a reply, though every step also works with buttons; and the questionnaire is a simplified one, with no real KYC.

## 14. What’s new, and why a bank could use it

What’s new here? First, the rules are data a compliance team can read and change, and every rule ID traces from the code to the log to the card the person sees. Second, readiness comes before risk: an advisor that can say “not yet”. Third, a practice account that replays real crashes, so someone’s first crash is a lesson, not a loss. And fourth, it works with any model, or none: every step works with buttons, and an open-weight model can run on a bank’s own servers. Next steps would be real KYC, a classifier on top of the language filter, and an external anchor for the audit log.

## 15. The LLM talks. The guardian decides. You confirm.

To sum up: the LLM talks, the guardian decides, and you confirm. It’s a wealth advisor that profiles risk, compares products and talks in plain words, but can never be talked into something unsafe. All the code, the documentation, the security self-assessment and the audit logs are in our repository. Thank you; we’re happy to take questions.
