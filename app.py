import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import io, xlsxwriter

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Custom Lash Therapy: Financials", layout="wide")

# --- LISA FRANK THEME COLORS (Applied via Custom CSS) ---
COLORS = {
    "pink": "#FF69B4", "purple": "#9370DB", "blue": "#40E0D0",
    "yellow": "#FFD700", "green": "#71d411", "red": "#DC143C",
    "light_bg": "#F0F8FF", "text": "#4B0082", "teal": "#00CED1"
}

st.markdown(f"""
    <style>
    .main {{ background-color: {COLORS["light_bg"]}; color: {COLORS["text"]}; }}
    h1, h2, h3 {{ color: {COLORS["purple"]}; font-family: 'Comic Sans MS'; }}
    .stButton>button {{
        background-color: {COLORS["pink"]}; color: white; border-radius: 10px;
        font-weight: bold; border: 2px solid {COLORS["purple"]};
    }}
    .report-box {{
        background-color: white; border: 2px solid {COLORS["blue"]};
        padding: 20px; border-radius: 10px; font-family: 'Courier New';
    }}
    </style>
    """, unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def parse_expenses(df):
    """Refined parsing logic for the specific expense report format."""
    expenses_list = []
    curr_cat = None
    for i, row in df.iterrows():
        c0 = str(row[0]).strip()
        if not c0 or c0 == "nan" or c0 == "Vendor" or "Report" in c0 or "Total" in c0:
            # Check if next row defines a category
            if i + 1 < len(df) and str(df.iloc[i+1, 0]) == "Vendor":
                curr_cat = c0
            continue
        
        if curr_cat:
            try:
                # Assuming standard positioning from your Tkinter logic
                amount_val = float(str(row[3]).replace(',', '').replace('$', ''))
                date_val = pd.to_datetime(row[2], errors='coerce')
                if not pd.isna(date_val):
                    expenses_list.append({'Category': curr_cat, 'Vendor': c0, 'Date': date_val, 'Amount': amount_val})
            except:
                continue
    return pd.DataFrame(expenses_list)

# --- APP LOGIC ---
st.title("💖 Custom Lash Therapy: Tax Suite")

# Sidebar for Inputs
with st.sidebar:
    st.header("⚙️ Configuration")
    fed_rate = st.number_input("Fed Income Tax Est (%)", value=12.0, step=0.5)
    local_rate = st.number_input("Hanover EIT Local (%)", value=1.0, step=0.1)
    include_tips = st.checkbox("Include Tips in Revenue", value=True)
    
    st.divider()
    sales_file = st.file_uploader("Upload Sales File", type=['csv', 'xlsx'])
    exp_file = st.file_uploader("Upload Expenses File", type=['csv', 'xlsx'])

# Tabs for Organization
tab1, tab2, tab3 = st.tabs(["📊 P&L Report", "📈 Analytics", "💸 Tax Estimator"])

if sales_file and exp_file:
    # Load Data
    s_df = pd.read_csv(sales_file, header=None) if sales_file.name.endswith('.csv') else pd.read_excel(sales_file, header=None)
    sales_summary = {str(row[0]).strip(): float(row[1]) for _, row in s_df.iterrows() if str(row[0]).strip() and not pd.isna(row[1])}
    
    e_raw_df = pd.read_csv(exp_file, header=None) if exp_file.name.endswith('.csv') else pd.read_excel(exp_file, header=None)
    df_exp = parse_expenses(e_raw_df)

    # --- CALCULATIONS ---
    net_sales = sales_summary.get('Net Sales', 0)
    gratuity = sales_summary.get('Gratuity', 0)
    tax_collected = sales_summary.get('Tax', 0)
    prepayments = sales_summary.get('Prepayments For Future Sales', 0)
    
    total_rev = net_sales + tax_collected + prepayments
    if include_tips: total_rev += gratuity
    
    cogs_cats = ['Back Bar', 'Inventory']
    total_cogs = df_exp[df_exp['Category'].isin(cogs_cats)]['Amount'].sum()
    
    processing_fees = abs(sales_summary.get('Payment Processing Fees Paid By Business', 0))
    total_opex = df_exp[~df_exp['Category'].isin(cogs_cats)]['Amount'].sum() + processing_fees + tax_collected
    
    net_profit = total_rev - total_cogs - total_opex

    # --- TAB 1: P&L ---
    with tab1:
        st.subheader("Profit & Loss Statement")
        
        # Prepare Dataframe for display
        pnl_data = [
            {"Description": "REVENUE", "Amount": None},
            {"Description": "  Net Sales", "Amount": net_sales},
            {"Description": "  Tax Collected", "Amount": tax_collected},
            {"Description": "  Prepayments", "Amount": prepayments}
        ]
        if include_tips: pnl_data.append({"Description": "  Tips/Gratuity", "Amount": gratuity})
        pnl_data.append({"Description": "TOTAL REVENUE", "Amount": total_rev})
        pnl_data.append({"Description": "TOTAL COGS", "Amount": total_cogs})
        pnl_data.append({"Description": "TOTAL OPEX", "Amount": total_opex})
        pnl_data.append({"Description": "NET PROFIT", "Amount": net_profit})
        
        pnl_df = pd.DataFrame(pnl_data)
        pnl_df["% of Revenue"] = (pnl_df["Amount"] / total_rev * 100).round(1).astype(str) + '%'
        
        st.dataframe(pnl_df.fillna(""), use_container_width=True)
        
        # Excel Export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            pnl_df.to_excel(writer, index=False, sheet_name='PNL')
        st.download_button("Download P&L as Excel", data=output.getvalue(), file_name="pnl_report.xlsx")

    # --- TAB 2: ANALYTICS ---
    with tab2:
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("Top 5 Vendor Spend")
            top_v = df_exp.groupby('Vendor')['Amount'].sum().sort_values(ascending=False).head(5)
            st.bar_chart(top_v, color=COLORS["pink"])
            
        with col2:
            st.write("Expense Breakdown")
            exp_breakdown = df_exp.groupby('Category')['Amount'].sum()
            fig, ax = plt.subplots(facecolor='none')
            ax.pie(exp_breakdown, labels=exp_breakdown.index, autopct='%1.1f%%', colors=[COLORS["pink"], COLORS["purple"], COLORS["blue"], COLORS["teal"]])
            st.pyplot(fig)

    # --- TAB 3: TAX ESTIMATOR ---
    with tab3:
        st.subheader("Estimated Tax Liability (Hanover, PA)")
        
        se_tax = (net_profit * 0.9235) * 0.153
        fed_inc = max(0, net_profit - (se_tax * 0.5)) * (fed_rate/100)
        pa_state = net_profit * 0.0307
        pa_local = net_profit * (local_rate/100)
        lst = 52.0 if net_profit > 12000 else 0
        total_tax = se_tax + fed_inc + pa_state + pa_local + lst
        
        tax_report = f"""
        Business Profit: ${net_profit:,.2f}
        ------------------------------------------
        Fed SE Tax (15.3%):        ${se_tax:,.2f}
        Fed Income Tax ({fed_rate}%):  ${fed_inc:,.2f}
        PA State Tax (3.07%):      ${pa_state:,.2f}
        Hanover Local EIT ({local_rate}%):  ${pa_local:,.2f}
        PA Local Services Tax:     ${lst:,.2f}
        ==========================================
        TOTAL ESTIMATED TAX DUE:   ${total_tax:,.2f}
        ESTIMATED TAKE-HOME:       ${net_profit - total_tax:,.2f}
        """
        st.code(tax_report)
        st.download_button("Save Tax Report (.txt)", tax_report, file_name="tax_estimate.txt")

else:
    st.info("👋 Welcome! Please upload your Sales and Expenses files in the sidebar to begin.")
