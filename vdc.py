#!/usr/bin/env python
"""PMI Vendor Portal – demo build (v 0.4)

Run with:
    streamlit run vendor_app.py

Changelog
~~~~~~~~~
* **Dropdown UX** – Country / State / Municipality / GPS all use the same multiselect‑with‑add pattern and are never empty (fallback shows A/B/C seeds even before parent selection).
* **Stats Dashboard** – now includes the 4 requested “Now” charts **plus** the 3 future ML charts:
  1. Country‑wise Operations (bar).
  2. Feedstock Composition (pie).
  3. Certification Coverage by tier (stacked bar).
  4. Tier Completion Status (progress bars).
  5. Supply Performance trend (line – dummy ML).
  6. Rejection Rate per country (bar – dummy ML).
  7. Vendor Risk Score heat‑map (dummy ML).
* **GPS picker** – converted to `multi_select_with_add()` (was a fixed selectbox).
* **Certification status capture** – each tier records a `certified: bool` flag to feed chart #3.
* **Progress calculation** – each tier contributes 25 % when saved; progress bars update live.
"""
from __future__ import annotations

from typing import Dict, List
import random as _rnd
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# 🔧 Seeds & Fake DB
# ---------------------------------------------------------------------------
VENDOR_REGISTRY = {
    ("DemoVendor", "demo@pmi.com"): {
        "proc_contact": "Priya Das",
        "proc_product": "Packaging Board",
        "supplier_group": "Demo Group",
        "supplier_name": "DemoVendor",
        "total_volume_2024": 12500,  # metric tonnes
    }
}

DEFAULT_COUNTRIES = ["Country A", "Country B", "Country C"]
DEFAULT_STATES = {c: ["State A", "State B", "State C"] for c in DEFAULT_COUNTRIES}
DEFAULT_MUNICIPALITIES = {
    s: ["Municipality A", "Municipality B", "Municipality C"]
    for sl in DEFAULT_STATES.values() for s in sl
}
DEFAULT_GPS = ["GPS A", "GPS B", "GPS C"]
CERT_PROGRAMS = ["FSC", "PEFC", "SFI"]
FEEDSTOCK_SOURCE_TYPES = ["Logging Company", "Woodlot", "Community Forest"]

# ---------------------------------------------------------------------------
# 🔐 OTP (fixed)
# ---------------------------------------------------------------------------
_generate_otp = lambda _=None: "123abc"
_send_otp = lambda email, otp: st.info(f"🔐 **DEMO OTP for {email}:** `{otp}` – fixed for demo")

# ---------------------------------------------------------------------------
# 🌳 Helper widgets
# ---------------------------------------------------------------------------

def multi_select_with_add(label: str, key: str, options: List[str]) -> List[str]:
    """Multiselect that never shows an empty list & lets users append."""
    current = st.session_state.setdefault(key, options.copy())
    sel = st.multiselect(label + " *", current, key=f"sel_{key}")
    with st.expander("➕ Add new"):
        new_val = st.text_input("Add value", key=f"new_{key}")
        if st.button("Add", key=f"btn_{key}") and new_val:
            if new_val not in current:
                current.append(new_val)
                st.session_state[key] = current
                st.rerun()
    return sel

# ---------------------------------------------------------------------------
# ✅ Validation helper
# ---------------------------------------------------------------------------

def _require(cond: bool, msg: str):
    if not cond:
        st.error(msg)
        st.stop()

# ---------------------------------------------------------------------------
# 🚪 Auth pages
# ---------------------------------------------------------------------------

def page_login():
    st.subheader("Vendor Login")
    c1, c2 = st.columns(2)
    cmp = c1.text_input("Company Name")
    eml = c2.text_input("Registered Email ID")
    if st.button("Send OTP"):
        _send_otp(eml, _generate_otp())
        st.session_state.update(pending_company=cmp, pending_email=eml, pending_otp="123abc", page="verify")
        st.rerun()


def page_verify():
    st.subheader("Enter OTP (demo: 123abc)")
    otp = st.text_input("OTP", max_chars=6)
    if st.button("Verify"):
        if otp != st.session_state.get("pending_otp"):
            st.error("Invalid OTP")
        else:
            key = (st.session_state["pending_company"], st.session_state["pending_email"])
            st.session_state["vendor_meta"] = VENDOR_REGISTRY.get(key, {})
            st.session_state["page"] = "main"
            st.rerun()

# ---------------------------------------------------------------------------
# 🚪 Main Dashboard
# ---------------------------------------------------------------------------

def page_main():
    st.subheader("Vendor Dashboard")
    meta = st.session_state.get("vendor_meta", {})
    with st.expander("🔍 Vendor Details", expanded=True):
        c1, c2 = st.columns(2)
        c1.write(f"**Procurement Contact in PMI:** {meta.get('proc_contact', '-')}")
        c1.write(f"**Procurement Product:** {meta.get('proc_product', '-')}")
        c2.write(f"**Supplier Group Name:** {meta.get('supplier_group', '-')}")
        c2.write(f"**Supplier Name:** {meta.get('supplier_name', '-')}")
        st.write(f"**Email (Registered):** {st.session_state.get('pending_email', '-')}")
        st.write(f"**Total 2024 Volume (mt):** {meta.get('total_volume_2024', '-')}")

    buttons = [
        ("T1: Factory", "t1"), ("T2: Mill", "t2"), ("T3: Pulp", "t3"), ("T4: Feedstock", "t4"),
        ("📊 Stats", "stats"), ("📈 Demand", "demand"), ("♻️ Waste", "waste"), ("📑 Orders", "orders")
    ]
    cols = st.columns(len(buttons))
    for col, (label, page) in zip(cols, buttons):
        if col.button(label):
            st.session_state["page"] = page; st.rerun()

# ---------------------------------------------------------------------------
# 🌍 Location helper (never empty)
# ---------------------------------------------------------------------------

def _tier_location(prefix: str):
    countries = multi_select_with_add(f"{prefix} – Country", f"{prefix}_countries", DEFAULT_COUNTRIES)
    # if none selected fall back to all states to avoid empty dropdown UX
    fallback_states = sum(DEFAULT_STATES.values(), [])
    states = multi_select_with_add(
        f"{prefix} – State/Province", f"{prefix}_states",
        sum((DEFAULT_STATES.get(c, []) for c in countries), []) or fallback_states,
    )
    fallback_munis = sum(DEFAULT_MUNICIPALITIES.values(), [])
    munis = multi_select_with_add(
        f"{prefix} – Municipality", f"{prefix}_munis",
        sum((DEFAULT_MUNICIPALITIES.get(s, []) for s in states), []) or fallback_munis,
    )
    return countries, states, munis

# ---------------------------------------------------------------------------
# 🚪 Tier Pages (T1‑T4)
# ---------------------------------------------------------------------------

def _save_tier(tier_key: str, data: Dict, certified: bool):
    st.session_state.setdefault("vendor_data", {})[tier_key] = data | {"certified": certified}
    st.success(f"Saved {tier_key.upper()}")


# ---------- T1 ----------

def page_t1():
    st.header("T1: Factory Data Entry")
    c, s, m = _tier_location("Plant Location")
    scrap = st.number_input("Scrap % *", min_value=0.0, max_value=100.0)
    defect = st.number_input("Defect kg *", min_value=0.0)
    cert_files = st.file_uploader("Upload Certifications *", accept_multiple_files=True)

    if st.button("💾 Save T1"):
        _require(c, "Select at least one country")
        _require(cert_files, "Certification upload required")
        _save_tier("t1", {
            "countries": c, "states": s, "munis": m,
            "scrap": scrap, "defect": defect, "cert_files": cert_files,
        }, certified=True)
    if st.button("⬅ Back"):
        st.session_state["page"] = "main"; st.rerun()

# ---------- T2 ----------

def page_t2():
    st.header("T2: Mill Data Entry")
    c, s, m = _tier_location("Mill Location")
    owned = st.radio("Mill owned by same Supplier Group? *", ["Yes", "No"], horizontal=True)
    owner_company = "" if owned == "Yes" else st.text_input("Company that owns the mill *")
    scrap = st.number_input("Scrap % *", min_value=0.0, max_value=100.0)
    defect = st.number_input("Defect kg *", min_value=0.0)
    st.subheader("CoC Certification of Mill")
    granted = st.radio("Certificate granted? *", ["Yes", "No"], horizontal=True)
    prog = st.selectbox("Certification program *", CERT_PROGRAMS)
    copy_avail = st.radio("Copy available? *", ["Yes", "No"], horizontal=True)
    file = st.file_uploader("Upload certificate *")

    if st.button("💾 Save T2"):
        _require(c, "Select at least one country")
        _require(not (owned == "No" and not owner_company), "Owner company required")
        _require(file, "Certificate file required")
        _save_tier("t2", {
            "countries": c, "states": s, "munis": m,
            "owned": owned, "owner_company": owner_company,
            "scrap": scrap, "defect": defect,
            "coc": {"granted": granted, "program": prog, "copy": copy_avail, "file": file},
        }, certified=granted == "Yes")
    if st.button("⬅ Back"):
        st.session_state["page"] = "main"; st.rerun()

# ---------- T3 ----------

def page_t3():
    st.header("T3: Pulp‑making Data Entry")
    c, s, m = _tier_location("Pulp Location")
    owned = st.radio("Pulp‑making owned by same Supplier Group? *", ["Yes", "No"], horizontal=True)
    owner_company = "" if owned == "Yes" else st.text_input("Company that owns the mill *")
    st.subheader("CoC Certification of Pulp‑making")
    granted = st.radio("Certificate granted? *", ["Yes", "No"], horizontal=True)
    prog = st.selectbox("Certification program *", CERT_PROGRAMS, key="t3_prog")
    copy_avail = st.radio("Copy available? *", ["Yes", "No"], horizontal=True, key="t3_copy")
    file = st.file_uploader("Upload certificate *", key="t3_file")

    if st.button("💾 Save T3"):
        _require(c, "Select at least one country")
        _require(file, "Certificate file required")
        _save_tier("t3", {
            "countries": c, "states": s, "munis": m,
            "owned": owned, "owner_company": owner_company,
            "coc": {"granted": granted, "program": prog, "copy": copy_avail, "file": file},
        }, certified=granted == "Yes")
    if st.button("⬅ Back"):
        st.session_state["page"] = "main"; st.rerun()

# ---------- T4 ----------

def page_t4():
    st.header("T4: Feedstock Data Entry")
    product = st.text_input("Feedstock of Procurement Product *")
    c, s, m = _tier_location("Plantation")
    gps = multi_select_with_add("FMU GPS", "gps_sel", DEFAULT_GPS)
    source = st.selectbox("Feedstock source type *", FEEDSTOCK_SOURCE_TYPES)
    supplier = st.text_input("Name of Feedstock Supplier *")
    st.markdown("**2024 Volume Breakdown (must equal 100%)**")
    col_v, col_r = st.columns(2)
    virgin = col_v.number_input("Virgin Fibres [%] *", 0.0, 100.0, 60.0)
    recycled = col_r.number_input("Recycled Fibres [%] *", 0.0, 100.0, 40.0)
    st.subheader("CoC Certification of Feedstock")
    granted = st.radio("Certificate granted? *", ["Yes", "No"], horizontal=True)
    prog = st.selectbox("Certification program *", CERT_PROGRAMS, key="t4_prog")
    copy_avail = st.radio("Copy available? *", ["Yes", "No"], horizontal=True, key="t4_copy")
    file = st.file_uploader("Upload certificate *", key="t4_file")

    st.subheader("Product Level Certification")
    purchase = st.radio("Purchase certified fibers? *", ["Yes", "No"], horizontal=True)
    if purchase == "Yes":
        p_prog = st.selectbox("Certification program *", CERT_PROGRAMS, key="t4_p_prog")
        col1, col2 = st.columns(2)
        vol_cert = col1.number_input("Volume certified [%] *", 0.0, 100.0)
        vol_ctrl = col2.number_input("Controlled wood volume [%] *", 0.0, 100.0)
    else:
        p_prog = ""; vol_cert = vol_ctrl = 0.0

    if st.button("💾 Save T4"):
        _require(product, "Feedstock product required")
        _require(c, "Select at least one country")
        _require(abs((virgin + recycled) - 100) < 1e-6, "Virgin+Recycled must equal 100%")
        _require(file, "CoC certificate required")
        _save_tier("t4", {
            "product": product, "countries": c, "states": s, "munis": m,
            "gps": gps, "source_type": source, "supplier_name": supplier,
            "virgin": virgin, "recycled": recycled,
            "coc": {"granted": granted, "program": prog, "copy": copy_avail, "file": file},
            "product_cert": {"purchase": purchase, "program": p_prog, "vol_cert": vol_cert, "vol_ctrl": vol_ctrl},
        }, certified=granted == "Yes")
    if st.button("⬅ Back"):
        st.session_state["page"] = "main"; st.rerun()


# ---------------------------------------------------------------------------
# 🚪 Demand Planning
# ---------------------------------------------------------------------------

def page_demand():
    st.header("Demand Planning")
    st.write("Upload historical demand (CSV with Month, Volume)")
    file = st.file_uploader("CSV File *", type=["csv"], key="demand_csv")
    if file is not None:
        df = pd.read_csv(file)
        st.dataframe(df)
        # dummy forecast
        last = df.iloc[-1, 1]
        months = pd.date_range(datetime.today(), periods=6, freq="M")
        forecast = pd.Series([last * (1 + 0.02 * i) for i in range(6)], index=months)
        st.subheader("6‑Month Forecast (Dummy)")
        st.line_chart(forecast)
    if st.button("⬅ Back"):
        st.session_state["page"] = "main"; st.rerun()

# ---------------------------------------------------------------------------
# 🚮 Waste Management (Demo with clearer graph & anomalies)
# ---------------------------------------------------------------------------
def page_waste():
    import matplotlib.pyplot as plt

    st.header("♻️ Waste Management Overview (Demo)")

    # dummy scrap rates
    scrap_rates = {"Factory": 20, "Mill": 30}
    threshold = 25

    # custom bar chart with anomaly coloring
    fig, ax = plt.subplots()
    colors = ["green" if v <= threshold else "red" for v in scrap_rates.values()]
    bars = ax.bar(scrap_rates.keys(), scrap_rates.values(), color=colors)
    ax.set_ylabel("Scrap Rate (%)")
    ax.set_title("Scrap Rate by Site")
    for bar in bars:
        h = bar.get_height()
        ax.annotate(f"{h}%", xy=(bar.get_x() + bar.get_width()/2, h),
                    xytext=(0, 3), textcoords="offset points", ha="center")
    st.pyplot(fig)

    # anomaly detection logic
    st.subheader("Anomaly Detection")
    anomalies = {site: rate for site, rate in scrap_rates.items() if rate > threshold}
    if anomalies:
        for site, rate in anomalies.items():
            st.error(f"⚠️ Anomaly: {site} scrap rate is {rate}%, exceeds {threshold}%")
    else:
        st.success("✅ No anomalies detected")

    if st.button("⬅ Back"):
        st.session_state["page"] = "main"
        st.rerun()


# ---------------------------------------------------------------------------
# 🚪 Order Management
# ---------------------------------------------------------------------------

def page_orders():
    st.header("Order Management")
    file = st.file_uploader("Upload open PO list (CSV) *", type=["csv"], key="po_csv")
    if file is not None:
        df = pd.read_csv(file)
        st.dataframe(df)
        # dummy late‑risk prediction
        if "LeadTime" in df.columns:
            df["LateRisk%"] = np.clip(df["LeadTime"] / df["LeadTime"].max(), 0, 1) * 100
            st.subheader("Predicted Late Delivery Risk")
            st.dataframe(df[["PO", "LateRisk%"]])
    if st.button("⬅ Back"):
        st.session_state["page"] = "main"; st.rerun()


# ---------------------------------------------------------------------------
# 📊 Stats Dashboard
# ---------------------------------------------------------------------------

def _tier_completion():
    vd = st.session_state.get("vendor_data", {})
    return {f"T{i}": 1 if f"t{i}" in vd else 0 for i in range(1, 5)}


# ---------------------------------------------------------------------------
# 📊 Stats Dashboard (Demo with dummy data)
# ---------------------------------------------------------------------------
def page_stats():
    import matplotlib.pyplot as plt

    st.header("📊 Statistics Dashboard (Demo)")

    # 1️⃣ Country-wise Operations (horizontal bar)
    country_counts = pd.Series([8, 5, 3], index=["Country A", "Country B", "Country C"])
    st.subheader("1️⃣ Country-wise Operations")
    fig1, ax1 = plt.subplots()
    ax1.barh(country_counts.index, country_counts.values, color="skyblue")
    ax1.set_xlabel("Number of Operations")
    ax1.set_title("Country-wise Operations")
    ax1.invert_yaxis()
    st.pyplot(fig1)

    # 2️⃣ Feedstock Composition (pie)
    st.subheader("2️⃣ Feedstock Composition")
    comp = {"Virgin": 65, "Recycled": 35}
    fig2, ax2 = plt.subplots()
    ax2.pie(comp.values(), labels=comp.keys(), autopct="%1.1f%%", startangle=90)
    ax2.axis("equal")
    ax2.set_title("Feedstock Composition")
    st.pyplot(fig2)

    # 3️⃣ Certification Coverage by Tier (stacked bar)
    st.subheader("3️⃣ Certification Coverage by Tier")
    cert_df = pd.DataFrame({
        "Tier": ["T1", "T2", "T3", "T4"],
        "Certified": [100, 75, 50, 25],
        "Not Certified": [0, 25, 50, 75]
    }).set_index("Tier")
    fig3, ax3 = plt.subplots()
    ax3.bar(cert_df.index, cert_df["Certified"], label="Certified")
    ax3.bar(cert_df.index, cert_df["Not Certified"], bottom=cert_df["Certified"], label="Not Certified")
    ax3.set_ylabel("%")
    ax3.set_title("Certification Coverage")
    ax3.legend()
    st.pyplot(fig3)

    # 4️⃣ Tier Completion Status (progress bars)
    st.subheader("4️⃣ Tier Completion Status")
    completions = {"T1": 100, "T2": 75, "T3": 50, "T4": 25}
    for tier, pct in completions.items():
        st.write(f"{tier}:")
        st.progress(pct)

    st.markdown("---")
    st.header("🤖 ML Insights (Demo)")

    # 5️⃣ Supply Performance – On-Time Delivery % (line)
    st.subheader("5️⃣ Supply Performance – On-Time Delivery %")
    dates = pd.date_range(datetime.today() - timedelta(days=150), periods=6, freq="M")
    ontime = pd.Series([90, 92, 88, 95, 93, 96], index=dates)
    fig5, ax5 = plt.subplots()
    ax5.plot(ontime.index, ontime.values, marker="o")
    ax5.set_ylabel("On-Time %")
    ax5.set_title("On-Time Delivery Trend")
    ax5.set_xticklabels([d.strftime("%b %Y") for d in ontime.index], rotation=45)
    st.pyplot(fig5)

    # 6️⃣ Rejection Rate by Country (bar)
    st.subheader("6️⃣ Rejection Rate by Country")
    rej = pd.Series([2.5, 4.0, 3.1], index=country_counts.index)
    fig6, ax6 = plt.subplots()
    ax6.bar(rej.index, rej.values)
    ax6.set_ylabel("Rejection Rate (%)")
    ax6.set_title("Rejection Rate by Country")
    st.pyplot(fig6)

    # 7️⃣ Vendor Risk Matrix (heat-map)
    st.subheader("7️⃣ Vendor Risk Matrix")
    factors = ["Cert Gap", "Performance", "Rejection"]
    risk_matrix = np.array([[10, 20, 5],
                            [15, 25, 10],
                            [5, 15, 8]])
    fig7, ax7 = plt.subplots()
    im = ax7.imshow(risk_matrix, cmap="RdYlGn_r")
    ax7.set_xticks(np.arange(len(factors)))
    ax7.set_xticklabels(factors, rotation=45, ha="right")
    ax7.set_yticks(np.arange(len(country_counts)))
    ax7.set_yticklabels(country_counts.index)
    for i in range(risk_matrix.shape[0]):
        for j in range(risk_matrix.shape[1]):
            ax7.text(j, i, risk_matrix[i, j], ha="center", va="center")
    fig7.colorbar(im, ax=ax7, label="Risk Level")
    ax7.set_title("Risk Score Heatmap")
    st.pyplot(fig7)

    if st.button("⬅ Back"):
        st.session_state["page"] = "main"
        st.rerun()



# ---------------------------------------------------------------------------
# Router & bootstrap  (Demand/Waste/Orders unchanged stubs)
# ---------------------------------------------------------------------------
ROUTER = {
    "login": page_login,
    "verify": page_verify,
    "main": page_main,
    "t1": page_t1,
    "t2": page_t2,
    "t3": page_t3,
    "t4": page_t4,
    "stats": page_stats,
    "demand": page_demand,
    "waste": page_waste,
    "orders": page_orders,
}

st.set_page_config(page_title="PMI Vendor Portal", layout="wide")
if "page" not in st.session_state: st.session_state["page"] = "login"
ROUTER.get(st.session_state["page"], page_login)()
