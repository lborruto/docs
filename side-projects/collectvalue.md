# CollectValue: real market prices for trading cards in France

A price guide for trading cards and sealed products built on completed sales, not asking prices. Each card's price is a weighted median of what it actually sold for, split by condition, grade and variant, and every figure shows its source, sample and time window. Pokémon, One Piece and Lorcana, in French.

Site: <https://collectvalue.fr>

## Why build this

Price guides for the French market usually quote asking prices, or mix raw and graded cards into a single number. A collector who wants to know what a Dracaufeu 4/102 in PSA 9 sold for last month has to search sold listings by hand, one by one.

CollectValue does that search for every card in the catalogue and keeps the result current. At the time of writing the site tracks about 26,000 items across 838 sets and more than 280,000 recorded sales.

## How a price is calculated

The full method is public on the [méthodologie](https://collectvalue.fr/methodologie) page. In short:

- **Completed sales only.** eBay.fr and GradedCardCenter provide sales that went through. Cardmarket FR's lowest current offer is shown too, labelled as a listing rather than a sale.
- **One price per grade and variant.** A PSA 10 and a CCC 10 are separate prices. Sales are never mixed across graders, but eBay and GCC sales for the same grader and grade are pooled.
- **A recency-weighted median.** Outliers are filtered with an IQR bound on log-price, and each sale is weighted with a half-life of about 30 days.
- **Honest confidence.** With 8 or more sales in 90 days, all of them are used; otherwise the last 5. A price appears from 2 sales and is marked low-confidence below 3.
- **A neutral trend.** The 30-day change compares the last 30 days with the 30 before, capped at ±300 %.

## What's in it

- Card, set and sealed-product pages with price curves, volumes and recent sales.
- Weekly movers and the top risers over 30 days.
- A personal collection tracked at current prices.
- Search by card name, set, number or EAN.

Built with FastAPI, Next.js, PostgreSQL and Redis, and self-hosted.
