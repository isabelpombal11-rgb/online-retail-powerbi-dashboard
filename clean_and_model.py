"""
Online Retail II -> star schema for Power BI.

Input : raw/online_retail_II.xlsx (UCI Online Retail II, Dec 2009 - Dec 2011)
Output: output/csv/*.csv and output/OnlineRetail_PowerBI.xlsx (one sheet per table, formatted as Excel tables)
Tables: FactSales (one row per invoice line), DimCustomer (with RFM segment and cohort month), DimProduct,
        DimDate, DimCountry, ProductPairs (products bought together, for cross-selling analysis)

Cleaning rules (each step is logged in output/cleaning_log.csv):
  1. Remove exact duplicate rows.
  2. Remove non-product lines (postage, fees, manual adjustments, test codes, gift vouchers).
  3. Remove lines with zero or negative unit price.
  4. Keep cancellation invoices (prefix 'C') as returns (negative quantity, LineType = 'Return').
  5. Remove other negative-quantity lines (stock write-offs, not customer transactions).
  6. Missing Customer ID -> CustomerKey 0 ('Guest / Unknown'); kept for revenue, excluded from customer analysis.
"""
import pandas as pd
import numpy as np
from pathlib import Path

RAW = Path("raw/online_retail_II.xlsx")
OUT = Path("output"); (OUT / "csv").mkdir(parents=True, exist_ok=True)

log = []
def step(name, df):
    log.append({"step": name, "rows": len(df)})
    print(f"{name:<55}{len(df):>10,}")
    return df

# ---------- load ----------
sheets = pd.read_excel(RAW, sheet_name=None, dtype={"Invoice": str, "StockCode": str})
df = pd.concat(sheets.values(), ignore_index=True)
df = df.rename(columns={"Customer ID": "CustomerID", "Price": "UnitPrice"})
df = step("0. Raw rows (both sheets)", df)

# ---------- clean ----------
df = step("1. Remove exact duplicates", df.drop_duplicates())

df["StockCode"] = df["StockCode"].str.strip().str.upper()
is_product = df["StockCode"].str.match(r"^\d{5}") | df["StockCode"].str.startswith("DCGS")
df = step("2. Remove non-product codes (postage, fees, tests...)", df[is_product])

df = step("3. Remove zero/negative unit price", df[df["UnitPrice"] > 0])

df["IsReturn"] = df["Invoice"].str.startswith("C")
df = step("4-5. Keep sales (qty>0) and returns (C-invoices)",
          df[(~df["IsReturn"] & (df["Quantity"] > 0)) | (df["IsReturn"] & (df["Quantity"] < 0))])

df["Revenue"] = (df["Quantity"] * df["UnitPrice"]).round(2)
df["CustomerKey"] = df["CustomerID"].fillna(0).astype(int)
df["DateKey"] = df["InvoiceDate"].dt.strftime("%Y%m%d").astype(int)
df["Hour"] = df["InvoiceDate"].dt.hour
df["LineType"] = np.where(df["IsReturn"], "Return", "Sale")

# ---------- DimCountry ----------
countries = sorted(df["Country"].unique())
dim_country = pd.DataFrame({"CountryKey": range(1, len(countries) + 1), "Country": countries})
dim_country["Region"] = np.where(dim_country["Country"] == "United Kingdom", "UK (domestic)", "International")
df = df.merge(dim_country[["CountryKey", "Country"]], on="Country")

# ---------- DimProduct ----------
desc = (df.dropna(subset=["Description"])
          .assign(Description=lambda d: d["Description"].str.strip())
          .groupby("StockCode")["Description"].agg(lambda s: s.value_counts().index[0]))
prod = df[~df["IsReturn"]].groupby("StockCode").agg(
    FirstSoldDate=("InvoiceDate", "min"), MedianUnitPrice=("UnitPrice", "median"))
dim_product = (pd.DataFrame({"StockCode": sorted(df["StockCode"].unique())})
               .merge(desc.rename("ProductName"), on="StockCode", how="left")
               .merge(prod, on="StockCode", how="left"))
dim_product["ProductName"] = dim_product["ProductName"].fillna("Unknown product")
dim_product["FirstSoldDate"] = dim_product["FirstSoldDate"].dt.date
dim_product["PriceBand"] = pd.cut(dim_product["MedianUnitPrice"], [0, 1, 2.5, 5, 10, np.inf],
                                  labels=["< £1", "£1-2.50", "£2.50-5", "£5-10", "> £10"]).astype(str)

# ---------- DimCustomer (RFM + cohort) ----------
sales = df[~df["IsReturn"] & (df["CustomerKey"] > 0)]
snapshot = df["InvoiceDate"].max().normalize() + pd.Timedelta(days=1)   # 2011-12-10
cust = sales.groupby("CustomerKey").agg(
    FirstPurchaseDate=("InvoiceDate", "min"), LastPurchaseDate=("InvoiceDate", "max"),
    Orders=("Invoice", "nunique"), GrossRevenue=("Revenue", "sum"))
home = (df[df["CustomerKey"] > 0].groupby("CustomerKey")["Country"]
          .agg(lambda s: s.value_counts().index[0]).rename("HomeCountry"))
cust = cust.join(home)
cust["RecencyDays"] = (snapshot - cust["LastPurchaseDate"].dt.normalize()).dt.days
cust["CohortMonth"] = cust["FirstPurchaseDate"].dt.to_period("M").dt.to_timestamp().dt.date

# RFM scores 1-5 (quintiles; recency reversed so recent = 5)
cust["R"] = pd.qcut(cust["RecencyDays"].rank(method="first"), 5, labels=[5, 4, 3, 2, 1]).astype(int)
cust["F"] = pd.qcut(cust["Orders"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
cust["M"] = pd.qcut(cust["GrossRevenue"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
cust["RFMScore"] = cust["R"].astype(str) + cust["F"].astype(str) + cust["M"].astype(str)

def segment(r, f):
    if r >= 4 and f >= 4: return "Champions"
    if r >= 3 and f >= 3: return "Loyal"
    if r >= 4 and f <= 2: return "New / Promising"
    if r == 3 and f <= 2: return "Needs Attention"
    if r <= 2 and f >= 3: return "At Risk"
    if r == 2 and f <= 2: return "Hibernating"
    return "Lost"
cust["Segment"] = [segment(r, f) for r, f in zip(cust["R"], cust["F"])]
order = {"Champions": 1, "Loyal": 2, "New / Promising": 3, "Needs Attention": 4,
         "At Risk": 5, "Hibernating": 6, "Lost": 7}
cust["SegmentOrder"] = cust["Segment"].map(order)
cust["FirstPurchaseDate"] = cust["FirstPurchaseDate"].dt.date
cust["LastPurchaseDate"] = cust["LastPurchaseDate"].dt.date
cust["GrossRevenue"] = cust["GrossRevenue"].round(2)
dim_customer = cust.reset_index()
guest = pd.DataFrame([{"CustomerKey": 0, "HomeCountry": "Unknown", "Segment": "Guest / Unknown",
                       "SegmentOrder": 8, "RFMScore": "n/a"}])
customers_only_returns = set(df["CustomerKey"].unique()) - set(dim_customer["CustomerKey"]) - {0}
extra = pd.DataFrame([{"CustomerKey": k, "Segment": "Returns only", "SegmentOrder": 9, "RFMScore": "n/a"}
                      for k in sorted(customers_only_returns)])
dim_customer = pd.concat([dim_customer, guest, extra], ignore_index=True)
dim_customer["CustomerType"] = np.where(dim_customer["CustomerKey"] == 0, "Guest", "Registered")
dim_customer = dim_customer[["CustomerKey", "CustomerType", "HomeCountry", "CohortMonth", "FirstPurchaseDate",
                             "LastPurchaseDate", "RecencyDays", "Orders", "GrossRevenue",
                             "R", "F", "M", "RFMScore", "Segment", "SegmentOrder"]]

# ---------- DimDate ----------
dates = pd.date_range(df["InvoiceDate"].min().normalize(), df["InvoiceDate"].max().normalize(), freq="D")
dim_date = pd.DataFrame({"Date": dates.date})
d = pd.to_datetime(dim_date["Date"])
dim_date.insert(0, "DateKey", d.dt.strftime("%Y%m%d").astype(int))
dim_date["Year"] = d.dt.year
dim_date["Quarter"] = "Q" + d.dt.quarter.astype(str)
dim_date["MonthNumber"] = d.dt.month
dim_date["MonthName"] = d.dt.strftime("%b")
dim_date["YearMonth"] = d.dt.strftime("%Y-%m")
dim_date["MonthStart"] = d.dt.to_period("M").dt.to_timestamp().dt.date
dim_date["WeekdayNumber"] = d.dt.dayofweek + 1          # 1 = Monday
dim_date["Weekday"] = d.dt.strftime("%a")
dim_date["IsWeekend"] = d.dt.dayofweek >= 5

# ---------- FactSales ----------
# CohortIndex = months between the customer's first purchase month and this line's month (0 = first month)
month_no = df["InvoiceDate"].dt.year * 12 + df["InvoiceDate"].dt.month
first_month = month_no[~df["IsReturn"] & (df["CustomerKey"] > 0)].groupby(df["CustomerKey"]).min()
df["CohortIndex"] = (month_no - df["CustomerKey"].map(first_month)).astype("Int64")   # blank for guests
df.loc[df["CohortIndex"] < 0, "CohortIndex"] = pd.NA   # returns of items bought before Dec 2009
fact = df[["Invoice", "LineType", "DateKey", "Hour", "CustomerKey", "StockCode", "CountryKey",
           "Quantity", "UnitPrice", "Revenue", "CohortIndex"]].sort_values(["DateKey", "Invoice"]).reset_index(drop=True)

# ---------- ProductPairs (market basket, top 300 products by orders) ----------
from scipy import sparse
s = df[~df["IsReturn"]][["Invoice", "StockCode"]].drop_duplicates()
n_orders = s["Invoice"].nunique()
top = s["StockCode"].value_counts().head(300).index
s = s[s["StockCode"].isin(top)]
inv_idx = {v: i for i, v in enumerate(s["Invoice"].unique())}
prd = list(top); prd_idx = {v: i for i, v in enumerate(prd)}
X = sparse.csr_matrix((np.ones(len(s)), ([inv_idx[i] for i in s["Invoice"]], [prd_idx[p] for p in s["StockCode"]])),
                      shape=(len(inv_idx), len(prd)))
co = (X.T @ X).toarray()
single = np.diag(co).copy()
iu = np.triu_indices(len(prd), k=1)
pairs = pd.DataFrame({"StockCodeA": np.array(prd)[iu[0]], "StockCodeB": np.array(prd)[iu[1]],
                      "OrdersTogether": co[iu].astype(int)})
pairs = pairs[pairs["OrdersTogether"] >= 50].copy()
a = pairs["StockCodeA"].map(prd_idx).values; b = pairs["StockCodeB"].map(prd_idx).values
pairs["SupportPct"] = (pairs["OrdersTogether"] / n_orders * 100).round(3)
pairs["ConfidenceAtoB"] = (pairs["OrdersTogether"] / single[a]).round(3)
pairs["ConfidenceBtoA"] = (pairs["OrdersTogether"] / single[b]).round(3)
pairs["Lift"] = (pairs["OrdersTogether"] * n_orders / (single[a] * single[b])).round(2)
names = dict(zip(dim_product["StockCode"], dim_product["ProductName"]))
pairs.insert(1, "ProductA", pairs["StockCodeA"].map(names))
pairs.insert(3, "ProductB", pairs["StockCodeB"].map(names))
product_pairs = pairs.sort_values("OrdersTogether", ascending=False).head(500).reset_index(drop=True)
product_pairs.insert(0, "PairRank", range(1, len(product_pairs) + 1))
fact.insert(0, "SalesLineID", range(1, len(fact) + 1))

# ---------- export ----------
tables = {"FactSales": fact, "DimCustomer": dim_customer, "DimProduct": dim_product,
          "DimDate": dim_date, "DimCountry": dim_country, "ProductPairs": product_pairs}
for n, t in tables.items():
    t.to_csv(OUT / "csv" / f"{n}.csv", index=False)
    print(f"{n:<12}{len(t):>10,} rows")
pd.DataFrame(log).to_csv(OUT / "cleaning_log.csv", index=False)

with pd.ExcelWriter(OUT / "OnlineRetail_PowerBI.xlsx", engine="xlsxwriter") as xw:
    for n, t in tables.items():
        t.to_excel(xw, sheet_name=n, index=False, startrow=1, header=False)
        ws = xw.sheets[n]
        ws.add_table(0, 0, len(t), len(t.columns) - 1,
                     {"name": n, "columns": [{"header": c} for c in t.columns], "style": "Table Style Light 9"})
print("done")
