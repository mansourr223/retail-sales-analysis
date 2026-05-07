import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from io import StringIO


st.set_page_config(layout="wide", page_title="Retail Store Sales Analysis")

st.title("Retail Store Sales Analysis")
st.markdown(
	"This interactive dashboard helps you explore the retail transactions dataset — filter data, answer analysis questions, and download results for further use."
)

@st.cache_data
def load_data(preferred_path="retail_store_cleaned.csv", fallback_path="retail_store_sales.csv"):
	# prefer cleaned exported dataframe if present
	import os
	path = preferred_path if os.path.exists(preferred_path) else fallback_path
	try:
		df = pd.read_csv(path)
	except Exception:
		st.error(f"Could not load {path}. Make sure the file exists in the workspace.")
		return pd.DataFrame()

	# Basic cleaning / type conversions
	if "transaction_date" in df.columns:
		try:
			df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
		except Exception:
			pass

	# numeric conversions
	for col in ["quantity", "unit_price", "discount", "total_spent", "rating"]:
		if col in df.columns:
			df[col] = pd.to_numeric(df[col], errors="coerce")

	# returned: ensure 0/1
	if "returned" in df.columns:
		df["returned"] = pd.to_numeric(df["returned"], errors="coerce").fillna(0)
		df["returned"] = df["returned"].apply(lambda x: 1 if x > 0.5 else 0)

	# If total_spent missing, try to compute it
	if ("total_spent" not in df.columns or df["total_spent"].isna().all()) and all(c in df.columns for c in ["quantity", "unit_price", "discount"]):
		df["total_spent"] = df["quantity"] * df["unit_price"] * (1 - df["discount"].fillna(0))

	return df


df = load_data()

if df.empty:
	st.stop()

# Sidebar filters and controls
st.sidebar.header("Filters & Settings")

min_date = df["transaction_date"].min() if "transaction_date" in df.columns else None
max_date = df["transaction_date"].max() if "transaction_date" in df.columns else None

date_range = None
if min_date is not None and max_date is not None:
	date_range = st.sidebar.date_input("Transaction date range", value=(min_date, max_date))

region_options = ["All"] + sorted(df["region"].dropna().unique().tolist()) if "region" in df.columns else ["All"]
region = st.sidebar.selectbox("Region", region_options)

category_options = ["All"] + sorted(df["category"].dropna().unique().tolist()) if "category" in df.columns else ["All"]
category = st.sidebar.selectbox("Category", category_options)

segment_options = ["All"] + sorted(df["customer_segment"].dropna().unique().tolist()) if "customer_segment" in df.columns else ["All"]
segment = st.sidebar.selectbox("Customer segment", segment_options)

payment_options = ["All"] + sorted(df["payment_method"].dropna().unique().tolist()) if "payment_method" in df.columns else ["All"]
payment = st.sidebar.selectbox("Payment method", payment_options)

show_raw = st.sidebar.checkbox("Show raw data", value=False)


def filter_df(df):
	d = df.copy()
	if date_range is not None and len(date_range) == 2:
		start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
		d = d[(d["transaction_date"] >= start) & (d["transaction_date"] <= end)]
	if region != "All":
		d = d[d["region"] == region]
	if category != "All":
		d = d[d["category"] == category]
	if segment != "All":
		d = d[d["customer_segment"] == segment]
	if payment != "All":
		d = d[d["payment_method"] == payment]
	return d


filtered = filter_df(df)

# Top-level metrics
st.subheader("Key Metrics")
col1, col2, col3, col4 = st.columns(4)

total_revenue = filtered["total_spent"].sum()
avg_transaction = filtered["total_spent"].mean()
total_txns = filtered.shape[0]
return_rate = (filtered["returned"].mean() * 100) if "returned" in filtered.columns else 0

col1.metric("Total Revenue", f"${total_revenue:,.2f}")
col2.metric("Avg Transaction", f"${avg_transaction:,.2f}" if not np.isnan(avg_transaction) else "N/A")
col3.metric("# Transactions", f"{total_txns:,}")
col4.metric("Return Rate", f"{return_rate:.1f}%")


st.markdown("---")

# Analysis questions / visualizations
st.markdown("**Analysis Questions & Visuals**")

# 1. Revenue over time (monthly)
with st.container():
	st.markdown("**1) Revenue over time (monthly average)**")
	if "transaction_date" in filtered.columns:
		tmp = filtered.copy()
		tmp["month_year"] = tmp["transaction_date"].dt.to_period("M").astype(str)
		ts = tmp.groupby("month_year")["total_spent"].sum().reset_index()
		fig = px.line(ts, x="month_year", y="total_spent", title="Monthly Revenue", markers=True)
		fig.update_layout(xaxis_title="Month", yaxis_title="Revenue")
		st.plotly_chart(fig, use_container_width=True)
	else:
		st.info("No transaction_date column available to show time series.")

	st.markdown("---")

	# 2. Top items by revenue
	st.markdown("**2) Top 10 items by total revenue**")
	if "item" in filtered.columns and "total_spent" in filtered.columns:
		top_items = filtered.groupby("item")["total_spent"].sum().reset_index().sort_values("total_spent", ascending=False).head(10)
		fig2 = px.bar(top_items, x="item", y="total_spent", title="Top 10 Items by Revenue")
		st.plotly_chart(fig2, use_container_width=True)
	else:
		st.info("Item or total_spent column missing.")

	st.markdown("---")

	# 3. Which customer segment spends most on average?
	st.markdown("**3) Avg spend by customer segment**")
	if "customer_segment" in filtered.columns and "total_spent" in filtered.columns:
		seg = filtered.groupby("customer_segment")["total_spent"].mean().reset_index().sort_values("total_spent", ascending=False)
		fig3 = px.bar(seg, x="customer_segment", y="total_spent", title="Average Spend per Transaction by Segment")
		st.plotly_chart(fig3, use_container_width=True)
	else:
		st.info("Customer segment or total_spent column missing.")

	st.markdown("---")

	# 4. Category distribution
	st.markdown("**4) Sales distribution by category**")
	if "category" in filtered.columns:
		cat = filtered["category"].value_counts().reset_index()
		cat.columns = ["category", "count"]
		fig4 = px.pie(cat, names="category", values="count", title="Category Distribution of Transactions")
		st.plotly_chart(fig4, use_container_width=True)
	else:
		st.info("Category column missing.")

	st.markdown("---")

	# 5. Returns analysis
	st.markdown("**5) Returns analysis**")
	if "returned" in filtered.columns:
		returns_by_cat = filtered.groupby("category")["returned"].mean().reset_index().sort_values("returned", ascending=False)
		if not returns_by_cat.empty:
			fig5 = px.bar(returns_by_cat, x="category", y="returned", title="Return Rate by Category", labels={"returned":"Return Rate"})
			st.plotly_chart(fig5, use_container_width=True)
		st.write("Returned transactions (sample):")
		st.dataframe(filtered[filtered["returned"] == 1].head(50))
	else:
		st.info("Returned column missing.")

	st.markdown("---")

	# 6. Rating distribution
	st.markdown("**6) Ratings distribution**")
	if "rating" in filtered.columns:
		fig6 = px.histogram(filtered, x="rating", nbins=20, title="Rating Distribution")
		st.plotly_chart(fig6, use_container_width=True)
	else:
		st.info("Rating column missing.")

	st.markdown("---")

	# 7. Correlation heatmap for numeric features
	st.markdown("**7) Numeric correlation heatmap**")
	num_cols = filtered.select_dtypes(include=np.number).columns.tolist()
	if len(num_cols) >= 2:
		corr = filtered[num_cols].corr()
		fig7 = px.imshow(corr, text_auto=True, title="Correlation Matrix")
		st.plotly_chart(fig7, use_container_width=True)
	else:
		st.info("Not enough numeric columns for correlation.")


st.markdown("---")

# Data export and raw viewer
st.sidebar.header("Export & Raw Data")
csv = filtered.to_csv(index=False)
st.sidebar.download_button("Download filtered data as CSV", data=csv, file_name="filtered_retail_data.csv", mime="text/csv")

if show_raw:
	st.subheader("Raw / Filtered Data")
	st.dataframe(filtered)

st.sidebar.markdown("\n---\nRun locally: `streamlit run app.py`")
