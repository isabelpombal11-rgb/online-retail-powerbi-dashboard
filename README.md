# Online Retail: Customer & Sales Analytics Dashboard (Power BI)

An end-to-end analysis of two years of real transactions from a UK online retailer: data cleaning in Python, a star-schema data model, DAX measures, and a four-page Power BI report covering sales performance, RFM customer segmentation, cohort retention and cross-selling.

**[View the live report](LINK)** · Tools: Python (pandas, SciPy), Power BI, DAX

![Executive overview](images/page1_overview.png)

## Business questions

1. How is the business performing, and is it growing year over year?
2. Who are the most valuable customers, and which ones are at risk of leaving?
3. Do customers come back after their first purchase, and how quickly do they drop off?
4. Which products drive revenue, which are returned most, and which are bought together?

## Data

[UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii): 1,067,371 invoice lines from a UK-based online gift retailer, 1 Dec 2009 to 9 Dec 2011, customers in 43 countries. Licensed by UCI under CC BY 4.0.

## Data cleaning (`clean_and_model.py`)

| Step | Rows after |
|---|---|
| Raw rows (both sheets) | 1,067,371 |
| Remove exact duplicates | 1,033,036 |
| Remove non-product codes (postage, bank charges, manual adjustments, test codes) | 1,027,213 |
| Remove zero or negative unit prices | 1,021,252 |

- Cancellation invoices (prefix `C`) are kept as **returns** with negative revenue, so net revenue and return rates are both measurable.
- Lines without a Customer ID (13% of sales) are kept for revenue totals and mapped to a **Guest** customer, but excluded from customer metrics.
- Product names are standardised to the most frequent description per stock code.
- **Data quality finding:** two single orders of 80,995 units (Paper Craft, Little Birdie, 9 Dec 2011) and 74,215 units (Medium Ceramic Top Storage Jar, 18 Jan 2011) were cancelled in full shortly after being placed. They look like order-entry errors rather than customer returns, and account for about 34% of all returns value. They stay in the totals but are excluded from the product return-rate table.

## Data model

Star schema with one fact table and four dimensions, plus a standalone market-basket table.

![Data model](images/model.png)

- **FactSales**: one row per invoice line (sales and returns)
- **DimCustomer**: first purchase, cohort month, RFM scores (1-5) and segment
- **DimProduct**, **DimDate** (marked as date table), **DimCountry**
- **ProductPairs**: top 500 product pairs bought in the same order, with support, confidence and lift

## Report pages

1. **Executive Overview**: revenue, orders, AOV, return rate, year-over-year trend, orders by weekday and hour
2. **Customers & RFM**: segment sizes and value, new vs returning customers, repeat rate
3. **Cohort Retention**: monthly retention heatmap by first-purchase month
4. **Products & Cross-Selling**: top products, return rates, price bands, products bought together

## Key findings

### Sales overview
- Revenue peaks every November ahead of Christmas.
- Thursday is the busiest day; 78% of orders are placed between 10:00 and 16:00.
- The UK is 85% of revenue; Ireland and the Netherlands lead internationally.

### Customers
- Champions: 25% of customers generate 69% of revenue.
- At Risk: 830 customers worth £1.6M, on average about a year since their last order.
- Growth comes mainly from returning customers.

### Cohorts
- About 1 in 5 new customers (20%) orders again in the month after their first purchase. In each of the following 12 months, between 15% and 25% of them place an order. There's no sharp drop-off, which points to a loyal core of customers.
- Customers acquired in the holiday season are the least likely to return. In December 2010, month-1 retention was only 9%, and November cohorts were also below average. This suggests that people who shop for gifts in the holiday season don't usually come back.
- In 2011 there was a clear decrease in new customer acquisition. Monthly cohorts went from 250–440 customers in early 2010 to about 100–200 in 2011.

### Products
- Two-thirds of revenue comes from items priced £1–5
- Revenue is spread widely: the top 15 of 4,701 products = only 9%
- Data quality: two bulk-order errors = 34% of returns value
- Strong pairs, e.g. the Jumbo Bag colours are bought together (lift ~6)

## Recommendations

- A win-back campaign aimed at the At Risk group,
- A follow-up offer to holiday-season first-time buyers,
- Bundles based on the products bought together.


## Limitations

- No cost data, so margin can't be calculated; revenue is used throughout.
- Guest orders (13% of sales) can't be linked to customers.
- The data starts in December 2009, so customers who existed before then all appear in the first cohort.
- The data ends on 9 December 2011, so year-over-year measures compare the same dates in both years (like-for-like) instead of using SAMEPERIODLASTYEAR, which would compare a partial 2011 with a full 2010.

## Repository

```
clean_and_model.py      data cleaning and star-schema build
dax/measures.dax        all DAX measures
output/cleaning_log.csv row counts after each cleaning step
images/                 report screenshots
```
