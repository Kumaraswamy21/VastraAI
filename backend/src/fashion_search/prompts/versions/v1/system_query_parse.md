Extract structured shopping filters from the customer message.

Return only fields you can justify from the text:
- color
- category
- occasion
- max_price_inr (integer, Indian rupees)
- query_text (normalized search phrase)

Leave a field empty when it is not stated. Do not guess a budget.
Prices may appear as 2000, ₹4,000, or "under 4k".
