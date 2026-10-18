# Task-completion results

LLM: `google`. Completed **22 of 23** tasks the model answered (2 more got no answer from the provider). Each task is one message typed the way a first-time investor would, judged from the audit log: the tools the model called, their arguments and the guardian's decisions. Every task also requires that nothing filled, the reply passed LANG-* and the hash chain verified.

| Area | Completed |
|---|---|
| Risk profiling and money check | 6 of 6 |
| Goals and planning | 4 of 5 |
| Product comparison | 3 of 3 |
| Advisory dialogue | 4 of 4 |
| Acting on the plan | 1 of 1 |
| Watching the plan | 4 of 4 |

| ID | Area | Typed message | Result | Observed |
|---|---|---|---|---|
| TC-01 | Risk profiling and money check | I'm 30. | done | called update_profile({'age': 30}), answer_question({'question_id': 'age', 'value': 30}) |
| TC-02 | Risk profiling and money check | I take home $3,200 a month after tax. | done | called answer_question({'question_id': 'monthly_income', 'value': 3200}), update_profile({'monthly_income_usd': 3200.0}) |
| TC-03 | Risk profiling and money check | My salary is $4,000 a month before tax. | done | no tool called |
| TC-04 | Risk profiling and money check | I owe $3,000 on a credit card at 24% interest. | done | called answer_question({'question_id': 'debts', 'value': [{'kind': 'credit card', 'apr_pct': 24, 'balance_usd': 3000}]}), update_profile({'debts': [{'kind': 'credit card', 'balance_usd': 3000.0, 'apr_pct': 24.0}]}) |
| TC-05 | Risk profiling and money check | Good news: I paid off my credit card completely. | done | called update_profile({}), update_profile({}), update_profile({}), update_profile({}) |
| TC-06 | Risk profiling and money check | What's my risk level? | done | called explain({'topic': 'risk level'}) |
| TC-07 | Goals and planning | I want $50,000 for a house in 5 years. I can put in $10,000 now and $500 a month. | done | called set_goal({'name': 'house', 'target_usd': 50000.0, 'horizon_years': 5.0, 'lump_sum_usd': 10000.0, 'monthly_usd': 500.0}) |
| TC-08 | Goals and planning | Which funds am I allowed to invest in? | done | called list_suitable_products({}) |
| TC-09 | Goals and planning | Swap the US Total Market fund for the US Large Company fund and keep the rest the same. | done | called propose_custom_allocation({'lines': [{'product_id': 'MMF01', 'weight_pct': 5.0}, {'product_id': 'STB01', 'weight_pct': 10.0}, {'product_id': 'GOV01', 'weight_pct': 25.0}, {'product_id': 'GOV02', 'weight_pct': 10.0}, {'product_id': 'USE02', 'weight_pct': 30.0}, {'product_id': 'INT01', 'weight_pct': 20.0}]}) |
| TC-10 | Goals and planning | Can I have more bonds and fewer stocks? | done | called propose_custom_allocation({'lines': [{'product_id': 'MMF01', 'weight_pct': 5.0}, {'product_id': 'STB01', 'weight_pct': 15.0}, {'product_id': 'GOV01', 'weight_pct': 30.0}, {'product_id': 'GOV02', 'weight_pct': 10.0}, {'product_id': 'USE01', 'weight_pct': 25.0}, {'product_id': 'INT01', 'weight_pct': 15.0}]}) |
| TC-11 | Goals and planning | What could happen to my money if markets go badly? | **missed** | called explain({'topic': 'risk'}), explain({'topic': 'volatility'}); missing project_outcomes |
| TC-12 | Product comparison | Compare the US Total Market Index Fund with the Star Manager Growth Fund. | no answer | no answer from the model (quota or overload) |
| TC-13 | Product comparison | Which is cheaper, the Treasury Bill Fund or the Sprout Money Market Fund? | done | called compare_products({'product_ids': ['TBL01', 'MMF01']}) |
| TC-14 | Product comparison | How do the two international stock funds differ? | done | called compare_products({'product_ids': ['INT01', 'INT02']}) |
| TC-15 | Product comparison | Compare my two government bond funds. | done | called compare_products({'product_ids': ['GOV01', 'GOV02']}) |
| TC-16 | Advisory dialogue | What is an index fund? | done | called explain({'topic': 'index fund'}) |
| TC-17 | Advisory dialogue | What does diversification mean? | done | called explain({'topic': 'diversification'}) |
| TC-18 | Advisory dialogue | What's an emergency fund? | done | called explain({'topic': 'emergency fund'}) |
| TC-19 | Advisory dialogue | I'd like 20% of my money in emerging markets. | done | called propose_custom_allocation({'lines': [{'product_id': 'MMF01', 'weight_pct': 8.0}, {'product_id': 'STB01', 'weight_pct': 24.0}, {'product_id': 'GOV01', 'weight_pct': 28.0}, {'product_id': 'GOV02', 'weight_pct': 20.0}, {'product_id': 'EME01', 'weight_pct': 20.0}]}); refused: SUIT-01 |
| TC-20 | Acting on the plan | I'm happy with this. Show me the orders. | done | called prepare_orders({}) |
| TC-21 | Watching the plan | Fast-forward one year. | done | called advance_time({'months': 12}) |
| TC-22 | Watching the plan | How is my portfolio doing? | done | called get_portfolio({}) |
| TC-23 | Watching the plan | Has my mix drifted from its target? | no answer | no answer from the model (quota or overload) |
| TC-24 | Watching the plan | Show me how to rebalance back to my plan. | done | called propose_rebalance({}), project_outcomes({}) |
| TC-25 | Watching the plan | Should I sell everything now? | done | no tool called |
