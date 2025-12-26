import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import textwrap

# --- PAGE CONFIG ---
st.set_page_config(page_title="Custom Lash Therapy", layout="wide")

# Lisa Frank Palette
COLORS = {
    "pink": "#FF69B4", "purple": "#9370DB", "blue": "#40E0D0",
    "yellow": "#FFD700", "green": "#71d411", "red": "#DC143C",
    "light_bg": "#F0F8FF", "dark_bg": "#8A2BE2", "text": "#4B0082",
    "report_bg": "#E0FFFF", "tax_bg": "#FFFACD", "teal": "#00CED1"
}

# Global Styling
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
    run_btn = st.button("🎨 GENERATE REPORT")

if sales_file and exp_file and run_btn:
    try:
        # 1. LOAD DATA
        s_df = pd.read_csv(sales_file, header=None) if sales_file.name.endswith('.csv') else pd.read_excel(sales_file, header=None)
        sales_summary = {str(row[0]).strip(): float(row[1]) for _, row in s_df.iterrows() if str(row[0]).strip() and not pd.isna(row[1])}

        e_df = pd.read_csv(exp_file, header=None) if exp_file.name.endswith('.csv') else pd.read_excel(exp_file, header=None)
        expenses_list = []
        curr_cat = None
        for i, row in e_df.iterrows():
            c0 = str(row[0]).strip()
            if c0 in ["Total", "Total Expenses", "Vendor", "nan"]: continue
            if i + 1 < len(e_df) and str(e_df.iloc[i+1, 0]) == "Vendor": 
                curr_cat = c0
            elif curr_cat:
                try:
                    amt_val = float(str(row[3]).replace(',', '').replace('$', ''))
                    expenses_list.append({'Category': curr_cat, 'Vendor': row[0], 'Amount': amt_val})
                except: pass
        df_exp = pd.DataFrame(expenses_list)

        # 2. CALCULATIONS
        net_sales = sales_summary.get('Net Sales', 0)
        gratuity = sales_summary.get('Gratuity', 0)
        tax_collected = sales_summary.get('Tax', 0)
        prepayments = sales_summary.get('Prepayments For Future Sales', 0)
        total_rev = net_sales + tax_collected + prepayments + (gratuity if include_tips else 0)
        
        processing_fees = abs(sales_summary.get('Payment Processing Fees Paid By Business', 0))
        total_cogs = df_exp[df_exp['Category'].isin(['Back Bar', 'Inventory'])]['Amount'].sum()
        total_opex = df_exp[~df_exp['Category'].isin(['Back Bar', 'Inventory'])]['Amount'].sum() + processing_fees + tax_collected
        net_profit = total_rev - total_cogs - total_opex

        # 3. TABS
        tab1, tab2, tab3 = st.tabs(["📄 P&L Report", "📊 Analytics", "💰 Tax Estimator"])

        with tab1:
            st.subheader("Profit & Loss Statement")
            last_pnl_data = [["Net Sales", net_sales, net_sales/total_rev if total_rev else 0],
                             ["TOTAL REVENUE", total_rev, 1.0]]
            rep = f"╔{'═'*42}╦{'═'*17}╦{'═'*12}╗\n"
            for row in last_pnl_data:
                rep += format_line(row[0], f"{row[1]:,.2f}", f"{(row[2]*100):.1f}%")
            rep += f"╚{'═'*42}╩{'═'*17}╩{'═'*12}╝\n"
            st.code(rep, language=None)

        with tab2:
            st.subheader("Business Analytics")
            if not df_exp.empty:
                # Use subplots but allow streamlit to scale the figure
                plt.rcParams['font.sans-serif'] = ['Arial'] # Standard font for better compatibility
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), facecolor=COLORS["light_bg"])
                
                # BAR CHART
                top_v = df_exp.groupby('Vendor')['Amount'].sum().sort_values(ascending=False).head(5)
                wrapped_v = [textwrap.fill(str(l), width=10) for l in top_v.index]
                bar_colors = [COLORS["pink"], COLORS["purple"], COLORS["blue"], COLORS["yellow"], COLORS["teal"]]
                ax1.bar(wrapped_v, top_v.values, color=bar_colors, edgecolor='#ccc')
                ax1.set_facecolor(COLORS["report_bg"])
                ax1.set_title("Top 5 Vendor Spend", fontweight='bold', color=COLORS["text"])
                ax1.set_ylabel("USD ($)", color=COLORS["text"])
                ax1.tick_params(axis='x', rotation=0, labelsize=8)

                # PIE CHART
                exp_breakdown = df_exp.groupby('Category')['Amount'].sum()
                pie_colors = [COLORS["pink"], COLORS["purple"], COLORS["blue"], COLORS["yellow"], COLORS["green"], COLORS["red"]]
                ax2.pie(exp_breakdown, labels=exp_breakdown.index, autopct='%1.1f%%', colors=pie_colors, startangle=140, textprops={'fontsize': 8})
                ax2.set_title("Expense Breakdown", fontweight='bold', color=COLORS["text"])
                
                fig.tight_layout()
                # KEY FIX: use_container_width=True makes it fit the browser
                st.pyplot(fig, use_container_width=True)
            else:
                st.warning("No expense data found to visualize.")

        with tab3:
            col_l, col_mid, col_r = st.columns([1, 2, 1])
            with col_mid:
                st.markdown(f"""
                <div style="border: 2px solid {COLORS['purple']}; border-radius: 10px; padding: 20px; background-color: {COLORS['light_bg']}; margin-bottom: 20px;">
                    <h3 style="text-align: center; color: {COLORS['dark_bg']}; margin-top:0;">Tax Rate Settings</h3>
                    <p style="text-align: center; color: {COLORS['text']};">Fed Income Tax Est: {fed_rate}%<br>Hanover EIT Local: {local_rate}%</p>
                </div>""", unsafe_allow_html=True)
                
            se_tax = (net_profit * 0.9235) * 0.153
            total_tax = se_tax + (net_profit * 0.0307)
            tax_txt = f"ESTIMATED TAX LIABILITY (HANOVER, PA)\n{'='*40}\nProfit: ${net_profit:,.2f}\nTotal Tax Due: ${total_tax:,.2f}"

            st.markdown(f"""
            <div style="background-color: #FFFACD; border: 1px solid #ccc; padding: 20px; font-family: 'Courier New', monospace; color: #4B0082; white-space: pre; border-radius: 5px;">
{tax_txt}
            </div>""", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error processing files: {e}")
else:
    st.info("👈 Upload files and click 'Generate Report' to start.")
