# Task-completion results

LLM: `fake`. Completed **7 of 25** tasks the model answered. Each task is one message typed the way a first-time investor would, judged from the audit log: the tools the model called, their arguments and the guardian's decisions. Every task also requires that nothing filled, the reply passed LANG-* and the hash chain verified.

| Area | Completed |
|---|---|
| Risk profiling and money check | 2 of 6 |
| Goals and planning | 0 of 5 |
| Product comparison | 1 of 4 |
| Advisory dialogue | 3 of 4 |
| Acting on the plan | 0 of 1 |
| Watching the plan | 1 of 5 |

| ID | Area | Typed message | Result | Observed |
|---|---|---|---|---|
| TC-01 | Risk profiling and money check | I'm 30. | done | called update_profile({'age': 30}) |
| TC-02 | Risk profiling and money check | I take home $3,200 a month after tax. | **missed** | no tool called; missing update_profile/answer_question with the right details |
| TC-03 | Risk profiling and money check | My salary is $4,000 a month before tax. | done | no tool called |
| TC-04 | Risk profiling and money check | I owe $3,000 on a credit card at 24% interest. | **missed** | no tool called; missing update_profile/answer_question |
| TC-05 | Risk profiling and money check | Good news: I paid off my credit card completely. | **missed** | no tool called; missing update_profile/answer_question |
| TC-06 | Risk profiling and money check | What's my risk level? | **missed** | no tool called; reply lacks C3 |
| TC-07 | Goals and planning | I want $50,000 for a house in 5 years. I can put in $10,000 now and $500 a month. | **missed** | no tool called; missing set_goal with the right details |
| TC-08 | Goals and planning | Which funds am I allowed to invest in? | **missed** | no tool called; missing list_suitable_products |
| TC-09 | Goals and planning | Swap the US Total Market fund for the US Large Company fund and keep the rest the same. | **missed** | no tool called; missing propose_custom_allocation with the right details |
| TC-10 | Goals and planning | Can I have more bonds and fewer stocks? | **missed** | no tool called; missing propose_custom_allocation |
| TC-11 | Goals and planning | What could happen to my money if markets go badly? | **missed** | no tool called; missing project_outcomes |
| TC-12 | Product comparison | Compare the US Total Market Index Fund with the Star Manager Growth Fund. | done | called compare_products({'product_ids': ['USE01', 'ACT01']}) |
| TC-13 | Product comparison | Which is cheaper, the Treasury Bill Fund or the Sprout Money Market Fund? | **missed** | no tool called; missing compare_products with the right details |
| TC-14 | Product comparison | How do the two international stock funds differ? | **missed** | no tool called; missing compare_products with the right details |
| TC-15 | Product comparison | Compare my two government bond funds. | **missed** | called compare_products({'product_ids': ['USE01', 'ACT01']}); missing compare_products with the right details |
| TC-16 | Advisory dialogue | What is an index fund? | done | called explain({'topic': 'index fund'}) |
| TC-17 | Advisory dialogue | What does diversification mean? | done | called explain({'topic': 'diversification'}) |
| TC-18 | Advisory dialogue | What's an emergency fund? | done | called explain({'topic': 'emergency fund'}) |
| TC-19 | Advisory dialogue | I'd like 20% of my money in emerging markets. | **missed** | no tool called; missing propose_custom_allocation |
| TC-20 | Acting on the plan | I'm happy with this. Show me the orders. | **missed** | no tool called; missing prepare_orders |
| TC-21 | Watching the plan | Fast-forward one year. | **missed** | called advance_time({'months': 1}); missing advance_time with the right details |
| TC-22 | Watching the plan | How is my portfolio doing? | **missed** | no tool called; missing get_portfolio |
| TC-23 | Watching the plan | Has my mix drifted from its target? | **missed** | no tool called; missing check_drift |
| TC-24 | Watching the plan | Show me how to rebalance back to my plan. | done | called propose_rebalance({}) |
| TC-25 | Watching the plan | Should I sell everything now? | **missed** | called request_sell({}); refused: COOL-01; should not call request_sell |
