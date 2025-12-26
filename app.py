import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import textwrap
from io import BytesIO

# --- PAGE CONFIG ---
st.set_page_config(page_title="Custom Lash Therapy", layout="wide")

# Lisa Frank Palette
COLORS = {
    "pink": "#FF69B4", "purple": "#9370DB", "blue": "#40E0D0",
    "yellow": "#FFD700", "green": "#71d411", "red": "#DC143C",
    "light_bg": "#F0F8FF", "dark_bg": "#8A2BE2", "text": "#4B0082",
    "report_bg": "#E0FFFF", "tax_bg": "#FFFACD", "teal": "#00CED1"
}

# Custom CSS
st.markdown(f"""
    <style>
    .stApp {{ background-color: {COLORS['light_bg']}; }}
    h1, h2, h3 {{ color: {COLORS['dark_bg']}; font-family: 'Comic Sans MS', cursive; }}
    .stButton>button {{ 
        background-color: {COLORS['pink']}; 
        color: white; 
        border-radius: 20px;
        font-weight: bold;
        width: 100%;
    }}
    </style>
    """, unsafe_allow_html=True)

def format_line(desc, amount, pct=""):
    return f"║ {desc:<40} ║ {amount:>15} ║ {pct:>10} ║\n"

# --- SIDEBAR ---
with st.sidebar:
    st.title("💖 App Settings")
    fed_rate = st.number_input("Fed Income Tax Est (%)", value=12.0)
    local_rate = st.number_input("Hanover EIT Local (%)", value=1.0)
    include_tips = st.checkbox("Include Tips", value=True)
    
    st.divider()
    st.subheader("📂 Data Import")
    sales_file = st.file_uploader("Upload Sales File", type=['csv', 'xlsx'])
    exp_file = st.file_uploader("Upload Expenses File", type=['csv', 'xlsx'])
    
    # MANUAL GENERATE BUTTON
    run_btn = st.button("🎨 GENERATE REPORT")

st.title("🌈 Custom Lash Therapy: Financials")

if sales_file and exp_file and run_btn:
    try:
        # 1. LOAD SALES
        s_df = pd.read_csv(sales_file, header=None) if sales_file.name.endswith('.csv') else pd.read_excel(sales_file, header=None)
        sales_summary = {str(row[0]).strip(): float(row[1]) for _, row in s_df.iterrows() if str(row[0]).strip() and not pd.isna(row[1])}

        # 2. LOAD EXPENSES
        e_df = pd.read_csv(exp_file, header=None) if exp_file.name.endswith('.csv') else pd.read_excel(exp_file, header=None)
        expenses_list = []
        curr_cat = None
        for i, row in e_df.iterrows():
            c0 = str(row[0]).strip()
            if c0 == "Total" or "Total Expenses" in c0: continue
            elif c0 and c0 != "nan" and c0 != "Vendor" and "Report" not in c0:
                if i + 1 < len(e_df) and str(e_df.iloc[i+1, 0]) == "Vendor": curr_cat = c0
                elif curr_cat:
                    try:
                        amt_val = float(str(row[3]).replace(',', '').replace('$', ''))
                        expenses_list.append({'Category': curr_cat, 'Vendor': row[0], 'Amount': amt_val})
                    except: pass
        df_exp = pd.DataFrame(expenses_list)

        # 3. CALCULATE
        net_sales = sales_summary.get('Net Sales', 0)
        gratuity = sales_summary.get('Gratuity', 0)
        tax_collected = sales_summary.get('Tax', 0)
        prepayments = sales_summary.get('Prepayments For Future Sales', 0)
        
        total_rev = net_sales + tax_collected + prepayments + (gratuity if include_tips else 0)
        
        processing_fees = abs(sales_summary.get('Payment Processing Fees Paid By Business', 0))
        total_cogs = df_exp[df_exp['Category'].isin(['Back Bar', 'Inventory'])]['Amount'].sum()
        total_opex = df_exp[~df_exp['Category'].isin(['Back Bar', 'Inventory'])]['Amount'].sum() + processing_fees + tax_collected
        net_profit = total_rev - total_cogs - total_opex

        # 4. DATA FOR P&L DISPLAY (Expanded to include Expenses)
        last_pnl_data = [
            ["REVENUE", "", ""],
            ["  Net Sales", net_sales, net_sales/total_rev if total_rev else 0],
            ["  Tax Collected", tax_collected, tax_collected/total_rev if total_rev else 0],
            ["  Prepayments", prepayments, prepayments/total_rev if total_rev else 0]
        ]
        if include_tips: 
            last_pnl_data.append(["  Tips/Gratuity", gratuity, gratuity/total_rev if total_rev else 0])
        
        last_pnl_data.append(["TOTAL REVENUE", total_rev, 1.0])
        last_pnl_data.append(["", "", ""]) # Spacer

        # --- COGS SECTION ---
        last_pnl_data.append(["COGS", "", ""])
        cogs_cats = ['Back Bar', 'Inventory']
        for cat in cogs_cats:
            amt = df_exp[df_exp['Category'] == cat]['Amount'].sum()
            if amt > 0:
                last_pnl_data.append([f"  {cat}", amt, amt/total_rev if total_rev else 0])
        last_pnl_data.append(["TOTAL COGS", total_cogs, total_cogs/total_rev if total_rev else 0])
        last_pnl_data.append(["GROSS MARGIN", total_rev - total_cogs, (total_rev - total_cogs)/total_rev if total_rev else 0])
        last_pnl_data.append(["", "", ""]) # Spacer

        # --- OPERATING EXPENSES SECTION ---
        last_pnl_data.append(["OPERATING EXPENSES", "", ""])
        last_pnl_data.append(["  Sales Tax Paid Out", tax_collected, tax_collected/total_rev if total_rev else 0])
        last_pnl_data.append(["  Processing Fees", processing_fees, processing_fees/total_rev if total_rev else 0])
        
        # Group remaining expenses by category
        opex_only = df_exp[~df_exp['Category'].isin(cogs_cats)]
        cat_totals = opex_only.groupby('Category')['Amount'].sum().sort_values(ascending=False)
        for cat, amt in cat_totals.items():
            last_pnl_data.append([f"  {cat}", amt, amt/total_rev if total_rev else 0])
            
        last_pnl_data.append(["TOTAL OPEX", total_opex, total_opex/total_rev if total_rev else 0])
        last_pnl_data.append(["NET PROFIT", net_profit, net_profit/total_rev if total_rev else 0])

        # --- TABS ---
        tab1, tab2, tab3 = st.tabs(["📄 P&L Report", "📊 Analytics", "💰 Tax Estimator"])

        with tab1:
            st.subheader("Profit & Loss Statement")
            # Scrollable ASCII Box
            rep = f"╔{'═'*42}╦{'═'*17}╦{'═'*12}╗\n"
            for row in last_pnl_data:
                rep += format_line(row[0], f"{row[1]:,.2f}", f"{(row[2]*100):.1f}%")
            rep += f"╚{'═'*42}╩{'═'*17}╩{'═'*12}╝\n"
            
            st.code(rep, language=None) # This creates the scrollable box

            # Download Excel
            output = BytesIO()
            pd.DataFrame(last_pnl_data, columns=["Desc", "Amt", "Pct"]).to_excel(output, index=False)
            st.download_button("💾 DOWNLOAD EXCEL REPORT", data=output.getvalue(), file_name="PNL_Report.xlsx")

        with tab2:
            st.subheader("Business Analytics")
            fig, ax = plt.subplots(figsize=(10, 5))
            df_exp.groupby('Category')['Amount'].sum().plot(kind='pie', autopct='%1.1f%%', colors=[COLORS["pink"], COLORS["blue"], COLORS["yellow"]])
            st.pyplot(fig)

        with tab3:
            st.subheader("Tax Liability")
            se_tax = (net_profit * 0.9235) * 0.153
            fed_inc = max(0, net_profit - (se_tax * 0.5)) * (fed_rate/100)
            total_tax = se_tax + fed_inc + (net_profit * 0.0307) + (net_profit * (local_rate/100))
            
            st.metric("Total Tax Estimate", f"${total_tax:,.2f}")
            st.metric("Take-Home", f"${net_profit - total_tax:,.2f}")

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("👈 Upload files and click 'Generate Report' in the sidebar.")
