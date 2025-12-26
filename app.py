import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import textwrap
from io import BytesIO

# --- PAGE CONFIG & THEME ---
st.set_page_config(page_title="Custom Lash Therapy", layout="wide")

# Lisa Frank Palette
COLORS = {
    "pink": "#FF69B4", "purple": "#9370DB", "blue": "#40E0D0",
    "yellow": "#FFD700", "green": "#71d411", "red": "#DC143C",
    "light_bg": "#F0F8FF", "dark_bg": "#8A2BE2", "text": "#4B0082",
    "report_bg": "#E0FFFF", "tax_bg": "#FFFACD", "teal": "#00CED1"
}

# Custom CSS for styling
st.markdown(f"""
    <style>
    .stApp {{ background-color: {COLORS['light_bg']}; }}
    h1, h2, h3 {{ color: {COLORS['dark_bg']}; font-family: 'Comic Sans MS', cursive; }}
    .stButton>button {{ 
        background-color: {COLORS['pink']}; 
        color: white; 
        border-radius: 20px;
        font-weight: bold;
    }}
    .report-box {{
        background-color: {COLORS['report_bg']};
        padding: 20px;
        border-radius: 10px;
        font-family: 'Courier New', monospace;
        color: {COLORS['text']};
        white-space: pre;
        overflow-x: auto;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- APP LOGIC FUNCTIONS ---
def format_line(desc, amount, pct=""):
    return f"║ {desc:<40} ║ {amount:>15} ║ {pct:>10} ║\n"

# --- SIDEBAR INPUTS ---
st.sidebar.title("💖 App Settings")
fed_income_rate = st.sidebar.number_input("Fed Income Tax Est (%)", value=12.0)
local_eit_rate = st.sidebar.number_input("Hanover EIT Local (%)", value=1.0)
include_tips = st.sidebar.checkbox("Include Tips", value=True)

st.sidebar.subheader("📂 Data Import")
sales_file = st.sidebar.file_uploader("Upload Sales File", type=['csv', 'xlsx'])
exp_file = st.sidebar.file_uploader("Upload Expenses File", type=['csv', 'xlsx'])

# --- MAIN INTERFACE ---
st.title("🌈 Custom Lash Therapy: Financials")

if sales_file and exp_file:
    try:
        # 1. LOAD SALES DATA
        s_df = pd.read_csv(sales_file, header=None) if sales_file.name.endswith('.csv') else pd.read_excel(sales_file, header=None)
        sales_summary = {str(row[0]).strip(): float(row[1]) for _, row in s_df.iterrows() if str(row[0]).strip() and not pd.isna(row[1])}

        # 2. LOAD EXPENSES DATA
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
                        date_val = pd.to_datetime(row[2], errors='coerce')
                        amount_val = float(str(row[3]).replace(',', '').replace('$', ''))
                        if not pd.isna(date_val):
                            expenses_list.append({'Category': curr_cat, 'Vendor': row[0], 'Date': date_val, 'Amount': amount_val})
                    except: pass
        
        df_exp = pd.DataFrame(expenses_list)

        # 3. CALCULATE TOTALS
        net_sales = sales_summary.get('Net Sales', 0)
        gratuity = sales_summary.get('Gratuity', 0)
        tax_collected = sales_summary.get('Tax', 0)
        prepayments = sales_summary.get('Prepayments For Future Sales', 0)
        
        total_rev = net_sales + tax_collected + prepayments
        if include_tips: total_rev += gratuity

        cogs_cats = ['Back Bar', 'Inventory']
        cogs_df = df_exp[df_exp['Category'].isin(cogs_cats)]
        opex_df = df_exp[~df_exp['Category'].isin(cogs_cats)]
        
        processing_fees = abs(sales_summary.get('Payment Processing Fees Paid By Business', 0))
        total_cogs = cogs_df['Amount'].sum()
        gross_margin = total_rev - total_cogs
        total_opex = opex_df['Amount'].sum() + processing_fees + tax_collected
        net_profit = gross_margin - total_opex

        # --- TABBED VIEW ---
        tab1, tab2, tab3 = st.tabs(["📄 P&L Report", "📊 Analytics", "💰 Tax Estimator"])

        with tab1:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.subheader("Profit & Loss Statement")
                
                # Build report text (similar to your format_line logic)
                rep = f"╔{'═'*42}╦{'═'*17}╦{'═'*12}╗\n"
                rep += format_line("DESCRIPTION", "AMOUNT ($)", "% OF REV")
                rep += f"╠{'═'*42}╬{'═'*17}╬{'═'*12}╣\n"
                
                # Revenue section
                rep += format_line("Net Sales", f"{net_sales:,.2f}", f"{(net_sales/total_rev*100):.1f}%" if total_rev else "0%")
                if include_tips: rep += format_line("Tips/Gratuity", f"{gratuity:,.2f}", f"{(gratuity/total_rev*100):.1f}%")
                rep += f"╠{'─'*42}╬{'─'*17}╬{'─'*12}╣\n"
                rep += format_line("TOTAL REVENUE", f"{total_rev:,.2f}", "100%")
                rep += f"╚{'═'*42}╩{'═'*17}╩{'═'*12}╝\n"
                
                st.markdown(f'<div class="report-box">{rep}</div>', unsafe_allow_html=True)

            with col2:
                st.subheader("Export")
                # Excel Download
                df_export = pd.DataFrame([["Total Revenue", total_rev], ["Total Expenses", total_opex + total_cogs], ["Net Profit", net_profit]], columns=["Item", "Amount"])
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_export.to_excel(writer, index=False)
                st.download_button("Download Excel Report", data=output.getvalue(), file_name="Hanover_Lash_Report.xlsx")

        with tab2:
            st.subheader("Visual Analytics")
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), facecolor=COLORS["light_bg"])
            
            # Vendor Spend
            top_v = df_exp.groupby('Vendor')['Amount'].sum().sort_values(ascending=False).head(5)
            top_v.plot(kind='bar', ax=ax1, color=[COLORS["pink"], COLORS["purple"], COLORS["blue"], COLORS["yellow"], COLORS["teal"]])
            ax1.set_title("Top 5 Vendor Spend")
            
            # Category Pie
            exp_breakdown = df_exp.groupby('Category')['Amount'].sum()
            ax2.pie(exp_breakdown, labels=[textwrap.fill(l, 15) for l in exp_breakdown.index], autopct='%1.1f%%', colors=[COLORS["pink"], COLORS["blue"], COLORS["yellow"], COLORS["green"]])
            ax2.set_title("Expense Breakdown")
            
            st.pyplot(fig)

        with tab3:
            st.subheader("Hanover, PA Tax Estimator")
            se_tax = (net_profit * 0.9235) * 0.153
            fed_inc = max(0, net_profit - (se_tax * 0.5)) * (fed_income_rate/100)
            pa_state = net_profit * 0.0307
            pa_local = net_profit * (local_eit_rate/100)
            lst = 52.0 if net_profit > 12000 else 0
            total_tax = se_tax + fed_inc + pa_state + pa_local + lst

            c1, c2, c3 = st.columns(3)
            c1.metric("Business Profit", f"${net_profit:,.2f}")
            c2.metric("Total Tax Due", f"${total_tax:,.2f}", delta_color="inverse")
            c3.metric("Take-Home Pay", f"${net_profit - total_tax:,.2f}")

            tax_details = f"""
            FEDERAL SE TAX (15.3%):  ${se_tax:,.2f}
            FEDERAL INCOME TAX:      ${fed_inc:,.2f}
            PA STATE TAX (3.07%):    ${pa_state:,.2f}
            HANOVER LOCAL EIT:       ${pa_local:,.2f}
            PA LST TAX:              ${lst:,.2f}
            """
            st.info(tax_details)
            st.download_button("Save Tax Report (.txt)", data=tax_details, file_name="Tax_Estimate.txt")

    except Exception as e:
        st.error(f"Error processing files: {e}. Ensure your Excel format matches the expected columns.")
else:
    st.warning("👈 Please upload your Sales and Expense files in the sidebar to generate the report.")
