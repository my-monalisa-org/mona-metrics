# Synthetic cafe data contract

Every record is fictional. The fixed dates describe a sample reporting period,
not when a workflow ran. Both fixtures use the same columns and cafe configuration.

`cafes.json` maps stable cafe IDs to display names and integer gram-based waste
budgets. `min_conversion` is an order/visit ratio in [0, 1];
`traffic_spike_multiplier` is greater than 1. CSV fields are:

| Field | Meaning |
| --- | --- |
| `date` | Canonical ISO calendar date, `YYYY-MM-DD` |
| `cafe_id` | Configured cafe ID |
| `visits` | Nonnegative integer visitor entries |
| `orders` | Nonnegative integer transactions, at most visits |
| `revenue_credits` | Nonnegative whole fictional credits |
| `adoptions` | Nonnegative integer adoptions, at most visits |
| `food_waste_g` | Nonnegative integer discarded food grams |

Duplicate cafe/date keys, unknown cafes, blank or extra fields, invalid dates,
negative or fractional counts, and impossible order/adoption counts are errors.
Each numeric field is capped at 1,000,000,000.
Empty files are errors. Zero visits requires zero orders, revenue, and adoptions.
A cafe-day may have zero orders only if its revenue is also zero.

Warnings do not discard rows:

- Missing cafe-day within the global first-to-last date, including absent cafes.
  The calendar is inclusive and assumes both cafes open daily.
- Conversion **strictly below 60%** on a day with visits.
- Waste **strictly above** each cafe's budget.
- Visits **strictly above 2x** the median of that cafe's earlier available days,
  requiring at least three earlier observations. This is a simple heuristic,
  not statistical significance or a causal claim; missing days are not imputed.

Input is capped at 10,000 records and 366 calendar days to bound processing and
report size. Daily coverage checks do not depend on today's date.

`daily.csv` is the clean baseline. `scenarios/meteor-shower.csv` deliberately
omits Luna Paw on September 6 and replaces Octocat Outpost on September 7
with 200 visits, 50 orders, 600 credits, and 900g waste. A fictional meteor-shower
promotion is a **hypothesis**, not proof of why traffic increased. Compare counts,
denominators, missingness, and waste before celebrating growth.

To explore, copy a fixture outside tracked data or make a normal feature-branch
PR. Keep the clean baseline clean; update exact expectations when intentionally
changing fixture behavior. Never replace synthetic labels with claims of live
customer activity or generated agent telemetry.
