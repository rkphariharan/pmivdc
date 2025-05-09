#!/usr/bin/env python
"""
PMI Vendor Portal  – demo build  v0.7
------------------------------------
* Excel persistence fixed (writes correct headers every time)
* View / Edit / Delete pages for Vendor + T1-T4
* Working Back buttons everywhere
* Stats dashboard blurred & tidy
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

import io
import os
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image, ImageFilter    # (Pillow only needed if you want heavier blur later)

# ──────────────────────────────────────────────────────────────────────────────
#  📌 CONFIG & CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────
EXCEL_PATH = r"C:\Users\rkpha\Desktop\pmivdc\pmivdc.xlsx"   # centralised single source

HEADERS = [
    "DIM Procurement Contact in PMI",
    "Procurement Product",
    "Supplier Group Name",
    "Supplier Name",
    "Total 2024 Volume for Procurement Product (mt)",
    "Plant Location\nCountry",
    "Plant Location \nSub-National/ Province/ Region",
    "Plant location Municipality",
    "Mill Location\nCountry",
    "Mill Location \nSub-National/ Province/ Region",
    "Mill Location Municipality",
    "Mill owned by same Supplier Group?",
    "Company that owns the mill (if different from supplier group)",
    "CoC certificate granted Y/N",
    "which certicifation program (FSC / PEFC / SFI)",
    "CoC certificate copy available to PMI Y/N",
    "Pulp-making Location\nCountry",
    "Pulp-making Location \nSub-National/ Province/ Region",
    "Pulp-making Location Municipality",
    "Pulp-making owned by same Supplier Group?",
    "Company that owns the mill (if different from supplier group)",
    "CoC certificate granted Y/N",
    "which certicifation program (FSC / PEFC / SFI)",
    "CoC certificate copy available to PMI Y/N",
    "Feedstock of Procurement Product",
    "Plantation Location - Country",
    "Plantation Location - Sub-national/State/Province",
    "Plantation Location - Municipality",
    "Plantation Location - Forest Management Unit\n(FMU)* - provide center GPS coordinates or woodlot shapefile)",
    "Feedstock source type (refers to the type of supplier you source the commodity from. Select the \noption that best reflects the source of your commodities)",
    "Name of Feedstock Supplier (if any, logging company, woodlot owning company,…)",
    "Percentage of 2024 volume (mentioned on column F) Breakdown by location (total must be equal 100%)",
    "Virgin Fibres [% of total volumes of column D]",
    "Recycled fibres [% of total volumes of column D]",
    "CoC certificate granted Y/N",
    "which certicifation program (FSC / PEFC / SFI)",
    "CoC certificate copy available to PMI Y/N",
    "Purchase of certified fibers Y/N",
    "which certification program (FSC / PEFC / SFI)",
    "Volume of purchased fibers certified for PMI product [%]",
    "Volume of purchased fiber meeting Controlled wood requirements for PMI product [%]",
]

CERT_PROGRAMS          = ["FSC", "PEFC", "SFI"]
FEEDSTOCK_SOURCE_TYPES = ["Logging Company", "Woodlot", "Community Forest"]

# ──────────────────────────────────────────────────────────────────────────────
#  🖼️ UI & GLOBAL CSS
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="PMI Vendor Portal", layout="wide")
st.markdown(
    """
    <style>
        section.main { padding-top: 1rem; }
        .blur img   { filter: blur(2px); }          /* simple blur for stats */
    </style>
    """,
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────────────────────
#  🔐 OTP (DEMO)
# ──────────────────────────────────────────────────────────────────────────────
_generate_otp = lambda: "123abc"
_send_otp     = lambda email, otp: st.info(f"🔐 **DEMO OTP for {email}: `{otp}`**")

# ──────────────────────────────────────────────────────────────────────────────
#  🛠️ HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def _require(cond: bool, msg: str):
    if not cond:
        st.error(msg)
        st.stop()

def _append_entry(tier_key: str, entry: Dict):
    data = st.session_state.setdefault("vendor_data", {})
    data.setdefault(tier_key, []).append(entry)

def _update_entries(tier_key: str, edited_df: pd.DataFrame):
    st.session_state["vendor_data"][tier_key] = edited_df.to_dict("records")

def save_to_excel() -> None:
    meta = st.session_state.get("vendor_meta", {})
    data = st.session_state.get("vendor_data", {})
    if not data:
        return

    rows: List[Dict] = []
    for tier, entries in data.items():
        for entry in entries:
            row = {h: "" for h in HEADERS}

            # shared vendor meta
            row["DIM Procurement Contact in PMI"] = meta.get("proc_contact", "")
            row["Procurement Product"]            = meta.get("proc_product", "")
            row["Supplier Group Name"]            = meta.get("supplier_group", "")
            row["Supplier Name"]                  = meta.get("supplier_name", "")
            row["Total 2024 Volume for Procurement Product (mt)"] = meta.get("total_volume_2024", "")

            # tier-specific mapping
            if tier == "t1":
                row.update(
                    {
                        "Plant Location\nCountry": entry["country"],
                        "Plant Location \nSub-National/ Province/ Region": entry["state"],
                        "Plant location Municipality": entry["muni"],
                        "CoC certificate granted Y/N": "Y",
                    }
                )
            elif tier == "t2":
                row.update(
                    {
                        "Mill Location\nCountry": entry["country"],
                        "Mill Location \nSub-National/ Province/ Region": entry["state"],
                        "Mill Location Municipality": entry["muni"],
                        "Mill owned by same Supplier Group?": entry["owned"],
                        "Company that owns the mill (if different from supplier group)": entry.get("owner_company", ""),
                        "CoC certificate granted Y/N": entry.get("granted", "N"),
                        "which certicifation program (FSC / PEFC / SFI)": entry.get("coc_prog", ""),
                        "CoC certificate copy available to PMI Y/N": entry.get("coc_copy", ""),
                    }
                )
            elif tier == "t3":
                row.update(
                    {
                        "Pulp-making Location\nCountry": entry["country"],
                        "Pulp-making Location \nSub-National/ Province/ Region": entry["state"],
                        "Pulp-making Location Municipality": entry["muni"],
                        "Pulp-making owned by same Supplier Group?": entry["owned"],
                        "Company that owns the mill (if different from supplier group)": entry.get("owner_company", ""),
                        "CoC certificate granted Y/N": entry.get("granted", "N"),
                        "which certicifation program (FSC / PEFC / SFI)": entry.get("coc_prog", ""),
                        "CoC certificate copy available to PMI Y/N": entry.get("coc_copy", ""),
                    }
                )
            else:  # t4
                row.update(
                    {
                        "Feedstock of Procurement Product": entry.get("product", ""),
                        "Plantation Location - Country": entry["country"],
                        "Plantation Location - Sub-national/State/Province": entry["state"],
                        "Plantation Location - Municipality": entry["muni"],
                        "Plantation Location - Forest Management Unit\n(FMU)* - provide center GPS coordinates or woodlot shapefile)": entry.get("gps", ""),
                        "Feedstock source type (refers to the type of supplier…)": entry.get("source", ""),
                        "Name of Feedstock Supplier (if any, logging company, woodlot owning company,…)": entry.get("supplier", ""),
                        "Percentage of 2024 volume (mentioned on column F) Breakdown by location (total must be equal 100%)": entry.get("volume", ""),
                        "Virgin Fibres [% of total volumes of column D]": entry.get("virgin", ""),
                        "Recycled fibres [% of total volumes of column D]": entry.get("recycled", ""),
                        "CoC certificate granted Y/N": entry.get("granted", "N"),
                        "which certicifation program (FSC / PEFC / SFI)": entry.get("coc_prog", ""),
                        "CoC certificate copy available to PMI Y/N": entry.get("coc_copy", ""),
                        "Purchase of certified fibers Y/N": entry.get("p_purchase", ""),
                        "which certification program (FSC / PEFC / SFI)": entry.get("p_prog", ""),
                        "Volume of purchased fibers certified for PMI product [%]": entry.get("vol_cert", ""),
                        "Volume of purchased fiber meeting Controlled wood requirements for PMI product [%]": entry.get("vol_ctrl", ""),
                    }
                )
            rows.append(row)

    pd.DataFrame(rows, columns=HEADERS).to_excel(EXCEL_PATH, index=False)
    st.success("🗂️ Data saved to Excel")

# ──────────────────────────────────────────────────────────────────────────────
#  📋 VIEW / EDIT / DELETE PAGE
# ──────────────────────────────────────────────────────────────────────────────
def page_view_tier(tier_key: str, label: str):
    st.subheader(f"{label} – existing entries")
    data = st.session_state.get("vendor_data", {}).get(tier_key, [])
    if not data:
        st.info("No entries yet.")
        if st.button("⬅ Back"):
            st.session_state["page"] = tier_key
            st.rerun()
        return

    df = pd.DataFrame(data)
    edited_df = st.data_editor(df, key=f"edit_{tier_key}", use_container_width=True, num_rows="dynamic")

    col1, col2, col3 = st.columns(3)
    if col1.button("💾 Save changes", key=f"save_{tier_key}"):
        _update_entries(tier_key, edited_df)
        save_to_excel()
        st.success("Changes stored")

    if col2.button("🗑️ Delete all", key=f"del_{tier_key}"):
        if st.radio("Really delete all entries?", ["No", "Yes"], key=f"conf_{tier_key}", horizontal=True) == "Yes":
            st.session_state["vendor_data"][tier_key] = []
            save_to_excel()
            st.warning("All entries deleted")

    if col3.button("⬅ Back"):
        st.session_state["page"] = tier_key
        st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
#  🔌 VIEW ROUTES
# ──────────────────────────────────────────────────────────────────────────────
def register_view_routes():
    ROUTER.update(
        {
            "view_vendor": lambda: st.json(st.session_state.get("vendor_meta", {})),
            "view_t1": lambda: page_view_tier("t1", "T1 – Factory"),
            "view_t2": lambda: page_view_tier("t2", "T2 – Board / Paper Mill"),
            "view_t3": lambda: page_view_tier("t3", "T3 – Pulp-making"),
            "view_t4": lambda: page_view_tier("t4", "T4 – Feedstock"),
        }
    )

# ──────────────────────────────────────────────────────────────────────────────
#  🚪 AUTH PAGES
# ──────────────────────────────────────────────────────────────────────────────
def page_login():
    st.subheader("Vendor Login")
    c1, c2 = st.columns(2)
    cmp = c1.text_input("Company Name")
    eml = c2.text_input("Registered Email ID")
    if st.button("Send OTP"):
        _send_otp(eml, _generate_otp())
        st.session_state.update(pending_company=cmp,
                                pending_email=eml,
                                pending_otp="123abc",
                                page="verify")
        st.rerun()

def page_verify():
    st.subheader("Enter OTP (demo: 123abc)")
    otp = st.text_input("OTP", max_chars=6)
    if st.button("Verify"):
        if otp != st.session_state.get("pending_otp"):
            st.error("Invalid OTP")
        else:
            st.session_state["vendor_meta"] = {}
            st.session_state["page"] = "main"
            st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
#  📊 MAIN DASHBOARD
# ──────────────────────────────────────────────────────────────────────────────
def page_main():
    st.subheader("Vendor Dashboard")

    meta = st.session_state.setdefault("vendor_meta", {})
    with st.expander("🔍 Vendor Details", expanded=True):
        c1, c2 = st.columns(2)
        proc_contact = c1.text_input("DIM Procurement Contact in PMI", meta.get("proc_contact", ""))
        proc_product = c1.text_input("Procurement Product",            meta.get("proc_product", ""))
        supplier_group = c2.text_input("Supplier Group Name",          meta.get("supplier_group", ""))
        supplier_name  = c2.text_input("Supplier Name",                meta.get("supplier_name", ""))
        total_vol = st.text_input("Total 2024 Volume for Procurement Product (mt)",
                                  str(meta.get("total_volume_2024", "")))

        st.write(f"**Email:** {st.session_state.get('pending_email', '-')}")
        if st.button("💾 Save Vendor Details"):
            _require(proc_contact and proc_product and supplier_group and supplier_name and total_vol,
                     "All vendor detail fields are required.")
            try:
                meta["total_volume_2024"] = float(total_vol)
            except ValueError:
                meta["total_volume_2024"] = total_vol
            meta.update(
                proc_contact=proc_contact,
                proc_product=proc_product,
                supplier_group=supplier_group,
                supplier_name=supplier_name,
            )
            save_to_excel()
            st.success("Vendor details saved")

        if st.button("🔍 View Vendor Details"):
            st.json(meta)

    buttons = [
        ("T1 Factory",            "t1"),
        ("T2 Board/Paper Mill",   "t2"),
        ("T3 Pulp-making",        "t3"),
        ("T4 Feedstock",          "t4"),
        ("📊 Stats",              "stats"),
        ("📈 Demand",             "demand"),
        ("♻️ Waste",              "waste"),
        ("📑 Orders",             "orders"),
    ]
    cols = st.columns(len(buttons))
    for col, (label, page) in zip(cols, buttons):
        if col.button(label):
            st.session_state["page"] = page
            st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
#  T1 – Factory
# ──────────────────────────────────────────────────────────────────────────────
def page_t1():
    st.header("T1: Factory")
    country = st.text_input("Plant Location – Country")
    state   = st.text_input("Plant Location – Sub-National / Province / Region")
    muni    = st.text_input("Plant Location – Municipality")
    cert_files = st.file_uploader("Upload CoC certifications (any)", accept_multiple_files=True)

    if st.button("Save & Add Another"):
        _require(country and state and muni, "Country, State & Municipality required")
        _require(cert_files, "Certification files required")
        _append_entry("t1",
            {"country": country, "state": state, "muni": muni,
             "cert_files": [f.name for f in cert_files]})
        save_to_excel()
        st.success("T1 entry stored")

    c1, c2, c3 = st.columns(3)
    if c1.button("🔍 View T1 entries"):
        st.session_state["page"] = "view_t1"; st.rerun()
    if c2.button("💾 Submit T1"):
        st.success("T1 submitted")
    if c3.button("⬅ Back"):
        st.session_state["page"] = "main";   st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
#  T2 – Board / Paper Mill
# ──────────────────────────────────────────────────────────────────────────────
def page_t2():
    st.header("T2: Board / Paper Mill")

    country = st.text_input("Mill Location – Country")
    state   = st.text_input("Mill Location – Sub-National / Province / Region")
    muni    = st.text_input("Mill Location – Municipality")

    owned = st.radio("Mill owned by same Supplier Group?", ["Yes", "No"], horizontal=True)
    owner = "" if owned == "Yes" else st.text_input("Company that owns the mill (if different)")

    st.subheader("CoC Certification")
    granted  = st.radio("CoC certificate granted?", ["Y", "N"], horizontal=True)
    coc_prog = st.selectbox("Certification program", CERT_PROGRAMS)
    coc_copy = st.radio("Certificate copy available to PMI?", ["Y", "N"], horizontal=True)
    file     = st.file_uploader("Upload certificate *", type=["pdf"])

    if st.button("Save & Add Another"):
        _require(country and state and muni, "Country, State & Municipality required")
        _require(not (owned == "No" and not owner), "Owner company required")
        _require(file, "Certificate file required")

        _append_entry("t2",
            {"country": country, "state": state, "muni": muni,
             "owned": owned, "owner_company": owner,
             "granted": granted, "coc_prog": coc_prog, "coc_copy": coc_copy,
             "coc_file": file.name})
        save_to_excel()
        st.success("T2 entry stored")

    c1, c2, c3 = st.columns(3)
    if c1.button("🔍 View T2 entries"):
        st.session_state["page"] = "view_t2"; st.rerun()
    if c2.button("💾 Submit T2"):
        st.success("T2 submitted")
    if c3.button("⬅ Back"):
        st.session_state["page"] = "main";   st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
#  T3 – Pulp-Making
# ──────────────────────────────────────────────────────────────────────────────
def page_t3():
    st.header("T3: Pulp-Making")

    country = st.text_input("Pulp-making Location – Country")
    state   = st.text_input("Pulp-making Location – Sub-National / Province / Region")
    muni    = st.text_input("Pulp-making Location – Municipality")

    owned = st.radio("Pulp-making owned by same Supplier Group?", ["Yes", "No"], horizontal=True)
    owner = "" if owned == "Yes" else st.text_input("Company that owns the mill (if different)")

    st.subheader("CoC Certification")
    granted  = st.radio("CoC certificate granted?", ["Y", "N"], horizontal=True)
    coc_prog = st.selectbox("Certification program", CERT_PROGRAMS)
    coc_copy = st.radio("Certificate copy available to PMI?", ["Y", "N"], horizontal=True)
    file     = st.file_uploader("Upload certificate *", type=["pdf"], key="t3_file")

    if st.button("Save & Add Another"):
        _require(country and state and muni, "Country, State & Municipality required")
        _require(file, "Certificate file required")

        _append_entry("t3",
            {"country": country, "state": state, "muni": muni,
             "owned": owned, "owner_company": owner,
             "granted": granted, "coc_prog": coc_prog, "coc_copy": coc_copy,
             "coc_file": file.name})
        save_to_excel()
        st.success("T3 entry stored")

    c1, c2, c3 = st.columns(3)
    if c1.button("🔍 View T3 entries"):
        st.session_state["page"] = "view_t3"; st.rerun()
    if c2.button("💾 Submit T3"):
        st.success("T3 submitted")
    if c3.button("⬅ Back"):
        st.session_state["page"] = "main";   st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
#  T4 – Feedstock
# ──────────────────────────────────────────────────────────────────────────────
def page_t4():
    st.header("T4: Feedstock")

    product  = st.text_input("Feedstock of Procurement Product")
    country  = st.text_input("Plantation Location – Country")
    state    = st.text_input("Plantation Location – Sub-National / State / Province")
    muni     = st.text_input("Plantation Location – Municipality")
    gps      = st.text_input("FMU centre GPS (or shapefile ref)")
    source   = st.selectbox("Feedstock source type", FEEDSTOCK_SOURCE_TYPES)
    supplier = st.text_input("Name of Feedstock Supplier")

    volume   = st.number_input("% of 2024 volume", min_value=0.0, max_value=100.0)
    virgin   = st.number_input("Virgin fibres [%]",   min_value=0.0, max_value=100.0)
    recycled = st.number_input("Recycled fibres [%]", min_value=0.0, max_value=100.0)

    st.subheader("CoC Certification")
    granted  = st.radio("CoC certificate granted?", ["Y", "N"], horizontal=True)
    coc_prog = st.selectbox("Certification program", CERT_PROGRAMS, key="t4_prog")
    coc_copy = st.radio("Certificate copy available to PMI?", ["Y", "N"], horizontal=True)
    file     = st.file_uploader("Upload certificate *", type=["pdf"], key="t4_file")

    st.subheader("Product-level Certification")
    p_purchase = st.radio("Purchase certified fibres?", ["Yes", "No"], horizontal=True)
    if p_purchase == "Yes":
        p_prog   = st.selectbox("Certification program", CERT_PROGRAMS, key="t4_p_prog")
        vol_cert = st.number_input("Volume certified [%]",     min_value=0.0, max_value=100.0)
        vol_ctrl = st.number_input("Controlled-wood vol [%]",  min_value=0.0, max_value=100.0)
    else:
        p_prog = ""; vol_cert = vol_ctrl = 0.0

    if st.button("Save & Add Another"):
        _require(product and country, "Feedstock product & Country required")
        _require(abs((virgin + recycled) - 100) < 1e-6, "Virgin + Recycled must equal 100 %")
        _require(file, "Certificate file required")

        _append_entry("t4",
            {"product": product, "country": country, "state": state, "muni": muni,
             "gps": gps, "source": source, "supplier": supplier,
             "volume": volume, "virgin": virgin, "recycled": recycled,
             "granted": granted, "coc_prog": coc_prog, "coc_copy": coc_copy,
             "coc_file": file.name, "p_purchase": p_purchase, "p_prog": p_prog,
             "vol_cert": vol_cert, "vol_ctrl": vol_ctrl})
        save_to_excel()
        st.success("T4 entry stored")

    c1, c2, c3 = st.columns(3)
    if c1.button("🔍 View T4 entries"):
        st.session_state["page"] = "view_t4"; st.rerun()
    if c2.button("💾 Submit T4"):
        st.success("T4 submitted")
    if c3.button("⬅ Back"):
        st.session_state["page"] = "main";   st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
#  DEMAND, WASTE, ORDERS (unchanged demo pages)
# ──────────────────────────────────────────────────────────────────────────────
def page_demand():
    st.header("Demand Planning")
    st.write("Upload historical demand CSV with columns Month, Volume")
    file = st.file_uploader("CSV *", type=["csv"])
    if file:
        df = pd.read_csv(file)
        st.dataframe(df)
        last = df.iloc[-1, 1]
        months = pd.date_range(datetime.today(), periods=6, freq="M")
        forecast = pd.Series([last * (1 + 0.02 * i) for i in range(6)], index=months)
        fig, ax = plt.subplots(figsize=(4,4))
        ax.plot(forecast.index, forecast.values, marker='o'); ax.set_title("6-month forecast")
        st.pyplot(fig)
    if st.button("⬅ Back"): st.session_state["page"]="main"; st.rerun()

def page_waste():
    st.header("♻️ Waste Management (demo)")
    scrap_rates = {"Factory": 20, "Mill": 30}; threshold = 25
    fig, ax = plt.subplots(figsize=(4,4))
    ax.bar(scrap_rates.keys(), scrap_rates.values(),
           color=["green" if v<=threshold else "red" for v in scrap_rates.values()])
    st.pyplot(fig)
    if st.button("⬅ Back"): st.session_state["page"]="main"; st.rerun()

def page_orders():
    st.header("Order Management")
    file = st.file_uploader("Open PO CSV (needs LeadTime)", type=["csv"])
    if file:
        df = pd.read_csv(file); st.dataframe(df)
        if 'LeadTime' in df.columns:
            df['LateRisk%'] = np.clip(df['LeadTime'] / df['LeadTime'].max(), 0,1)*100
            st.write(df[['PO','LateRisk%']])
    if st.button("⬅ Back"): st.session_state["page"]="main"; st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
#  📊 STATS (Dashboard wrapped in blur)
# ──────────────────────────────────────────────────────────────────────────────
def page_stats():
    st.markdown('<div class="blur">', unsafe_allow_html=True)
    st.header("📊 Statistics Dashboard (Demo)")

    country_counts = pd.Series([8,5,3], index=["Country A","Country B","Country C"])
    st.subheader("1️⃣ Country-wise Operations")
    fig, ax = plt.subplots(figsize=(1,1)); ax.barh(country_counts.index, country_counts.values)
    ax.set_title("Country-wise Operations", fontsize=3); ax.tick_params(labelsize=3); ax.invert_yaxis()
    st.pyplot(fig)

    st.subheader("2️⃣ Feedstock Composition")
    fig2, ax2 = plt.subplots(figsize=(1,1))
    ax2.pie([65,35], labels=["Virgin","Recycled"], autopct='%1.0f%%', startangle=90,
            textprops={'fontsize':3}); ax2.set_title("Feedstock", fontsize=3)
    st.pyplot(fig2)

    st.subheader("3️⃣ Certification Coverage")
    cert_df = pd.DataFrame({'Tier':['T1','T2','T3','T4'],
                            'Certified':[100,75,50,25],
                            'Not Certified':[0,25,50,75]}).set_index('Tier')
    fig3, ax3 = plt.subplots(figsize=(1,1))
    ax3.bar(cert_df.index, cert_df['Certified'], label='Certified')
    ax3.bar(cert_df.index, cert_df['Not Certified'], bottom=cert_df['Certified'])
    ax3.set_title("Coverage", fontsize=5); ax3.tick_params(labelsize=2); ax3.legend(fontsize=2)
    st.pyplot(fig3)

    st.subheader("4️⃣ Tier Completion Status")
    for t,p in {'T1':100,'T2':75,'T3':50,'T4':25}.items():
        st.write(f"{t}: {p}%"); st.progress(p)

    st.subheader("5️⃣ On-Time Delivery Trend")
    dates = pd.date_range(datetime.today()-timedelta(days=150), periods=6, freq='M')
    ontime = pd.Series([90,92,88,95,93,96], index=dates)
    fig5, ax5 = plt.subplots(figsize=(2,2)); ax5.plot(ontime.index, ontime.values, marker='o')
    st.pyplot(fig5)

    st.markdown("</div>", unsafe_allow_html=True)
    if st.button("⬅ Back"): st.session_state["page"]="main"; st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
#  🚦 ROUTER & BOOTSTRAP
# ──────────────────────────────────────────────────────────────────────────────
ROUTER = {
    "login":  page_login,
    "verify": page_verify,
    "main":   page_main,
    "t1":     page_t1,
    "t2":     page_t2,
    "t3":     page_t3,
    "t4":     page_t4,
    "stats":  page_stats,
    "demand": page_demand,
    "waste":  page_waste,
    "orders": page_orders,
}
register_view_routes()                        # inject view routes AFTER dict exists

if "page" not in st.session_state:
    st.session_state["page"] = "login"

ROUTER.get(st.session_state["page"], page_login)()
