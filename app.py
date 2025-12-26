from __future__ import annotations

import io
import datetime
import textwrap
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any

import pandas as pd
import matplotlib.pyplot as plt

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, send_file
)

app = Flask(__name__)
app.secret_key = "replace-me-with-a-random-secret"  # needed for flash messages


# ----------------------------
# Theme colors (matches your Tkinter palette)
# ----------------------------
COLORS = {
    "pink": "#FF69B4",
    "purple": "#9370DB",
    "blue": "#40E0D0",
    "yellow": "#FFD700",
    "green": "#71d411",
    "red": "#DC143C",
    "light_bg": "#F0F8FF",
    "dark_bg": "#8A2BE2",
    "text": "#4B0082",
    "button_fg": "#FFFFFF",
    "report_bg": "#E0FFFF",
    "tax_bg": "#FFFACD",
    "teal": "#00CED1",
}


# ----------------------------
# In-memory "app state"
# (simple + local dev friendly; for multiple users/prod use sessions/db)
# ----------------------------
@dataclass
class AppState:
    sales_df: Optional[pd.DataFrame] = None
    exp_df_raw: Optional[pd.DataFrame] = None
    include_tips: bool = True

    fed_income_rate: float = 12.0
    local_eit_rate: float = 1.0

    last_pnl_data: List[List[Any]] = None
    current_net_profit: float = 0.0
    last_tax_txt: str = ""

    report_text: str = ""
    charts_png: Optional[bytes] = None  # combined charts image as PNG bytes

STATE = AppState(last_pnl_data=[])


# ----------------------------
# Helpers (ported from your Tkinter logic)
# ----------------------------
def _read_sales_file(file_storage) -> pd.DataFrame:
    filename = (file_storage.filename or "").lower()
    data = file_storage.read()
    bio = io.BytesIO(data)

    if filename.endswith(".csv"):
        return pd.read_csv(bio, header=None)
    return pd.read_excel(bio, header=None)

def _read_expenses_file(file_storage) -> pd.DataFrame:
    filename = (file_storage.filename or "").lower()
    data = file_storage.read()
    bio = io.BytesIO(data)

    if filename.endswith(".csv"):
        return pd.read_csv(bio, header=None)
    return pd.read_excel(bio, header=None)

def _format_line(desc: str, amount: str, pct: str = "") -> str:
    return f"║ {desc:<40} ║ {amount:>15} ║ {pct:>10} ║\n"

def _parse_sales_summary(s_df: pd.DataFrame) -> Dict[str, float]:
    # matches your: {row[0]: float(row[1])}
    out: Dict[str, float] = {}
    for _, row in s_df.iterrows():
        k = str(row.iloc[0]).strip()
        v = row.iloc[1]
        if k and k != "nan" and not pd.isna(v):
            try:
                out[k] = float(v)
            except Exception:
                pass
    return out

def _parse_expenses(exp_df: pd.DataFrame) -> pd.DataFrame:
    expenses_list = []
    curr_cat = None

    for i, row in exp_df.iterrows():
        c0 = str(row.iloc[0]).strip()

        if c0 == "Total" or "Total Expenses" in c0:
            continue

        if c0 and c0 != "nan" and c0 != "Vendor" and "Report" not in c0:
            # detect category header
            if i + 1 < len(exp_df) and str(exp_df.iloc[i + 1, 0]) == "Vendor":
                curr_cat = c0
            elif curr_cat:
                try:
                    # expects: Vendor=row[0], Date=row[2], Amount=row[3]
                    date_val = pd.to_datetime(row.iloc[2], errors="coerce")
                    amount_val = float(str(row.iloc[3]).replace(",", "").replace("$", ""))
                    if not pd.isna(date_val):
                        expenses_list.append(
                            {
                                "Category": curr_cat,
                                "Vendor": row.iloc[0],
                                "Date": date_val,
                                "Amount": amount_val,
                            }
                        )
                except Exception:
                    pass

    return pd.DataFrame(expenses_list)

def _calc_hanover_tax_text(net: float, fed_income_rate: float, local_eit_rate: float) -> Tuple[str, float]:
    se_tax = (net * 0.9235) * 0.153
    fed_inc = max(0, net - (se_tax * 0.5)) * (fed_income_rate / 100)
    pa_state = net * 0.0307
    pa_local = net * (local_eit_rate / 100)
    lst = 52.0 if net > 12000 else 0
    total_tax = se_tax + fed_inc + pa_state + pa_local + lst

    txt = (
        "ESTIMATED TAX LIABILITY (HANOVER, PA)\n"
        + "=" * 50
        + "\n"
        + f"Report Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        + f"Business Profit:  ${net:,.2f}\n"
        + f"{'-' * 50}\n"
        + f"Fed SE Tax (15.3%):               ${se_tax:,.2f}\n"
        + f"Fed Income Tax ({fed_income_rate}%):           ${fed_inc:,.2f}\n"
        + f"PA State Tax (3.07%):             ${pa_state:,.2f}\n"
        + f"Hanover Local EIT ({local_eit_rate}%):          ${pa_local:,.2f}\n"
        + f"PA Local Services Tax (LST):      ${lst:,.2f}\n"
        + "=" * 50
        + "\n"
        + f"TOTAL ESTIMATED TAX DUE:          ${total_tax:,.2f}\n"
        + f"ESTIMATED TAKE-HOME:              ${net - total_tax:,.2f}\n"
    )
    return txt, total_tax

def _build_report_and_tables(
    sales_summary: Dict[str, float],
    expenses_df: pd.DataFrame,
    include_tips: bool,
) -> Tuple[str, List[List[Any]], float]:
    # REVENUE
    net_sales = sales_summary.get("Net Sales", 0.0)
    gratuity = sales_summary.get("Gratuity", 0.0)
    tax_collected = sales_summary.get("Tax", 0.0)
    prepayments = sales_summary.get("Prepayments For Future Sales", 0.0)

    total_rev = net_sales + tax_collected + prepayments
    if include_tips:
        total_rev += gratuity

    # EXPENSE DATA
    cogs_cats = ["Back Bar", "Inventory"]
    cogs_df = expenses_df[expenses_df["Category"].isin(cogs_cats)] if not expenses_df.empty else expenses_df
    opex_df = expenses_df[~expenses_df["Category"].isin(cogs_cats)] if not expenses_df.empty else expenses_df

    processing_fees = abs(sales_summary.get("Payment Processing Fees Paid By Business", 0.0))
    sales_tax_expense = tax_collected

    total_cogs = float(cogs_df["Amount"].sum()) if not cogs_df.empty else 0.0
    gross_margin = float(total_rev - total_cogs)

    total_opex = float((opex_df["Amount"].sum() if not opex_df.empty else 0.0) + processing_fees + sales_tax_expense)
    net_profit = float(gross_margin - total_opex)

    # BUILD DATA FOR EXCEL + report
    last_pnl_data: List[List[Any]] = [
        ["REVENUE", "", ""],
        ["  Net Sales", net_sales, (net_sales / total_rev) if total_rev else 0],
        ["  Tax Collected", tax_collected, (tax_collected / total_rev) if total_rev else 0],
        ["  Prepayments", prepayments, (prepayments / total_rev) if total_rev else 0],
    ]
    if include_tips:
        last_pnl_data.append(["  Tips/Gratuity", gratuity, (gratuity / total_rev) if total_rev else 0])

    last_pnl_data.append(["TOTAL REVENUE", total_rev, 1.0])
    last_pnl_data.append(["", "", ""])
    last_pnl_data.append(["COGS", "", ""])

    for cat in cogs_cats:
        amt = float(cogs_df[cogs_df["Category"] == cat]["Amount"].sum()) if not cogs_df.empty else 0.0
        if amt > 0:
            last_pnl_data.append([f"  {cat}", amt, (amt / total_rev) if total_rev else 0])

    last_pnl_data.extend(
        [
            ["TOTAL COGS", total_cogs, (total_cogs / total_rev) if total_rev else 0],
            ["GROSS MARGIN", gross_margin, (gross_margin / total_rev) if total_rev else 0],
            ["", "", ""],
            ["OPERATING EXPENSES", "", ""],
            ["  Sales Tax Paid Out", sales_tax_expense, (sales_tax_expense / total_rev) if total_rev else 0],
            ["  Processing Fees", processing_fees, (processing_fees / total_rev) if total_rev else 0],
        ]
    )

    if not opex_df.empty:
        cat_totals = opex_df.groupby("Category")["Amount"].sum().sort_values(ascending=False)
        for cat, amt in cat_totals.items():
            amt = float(amt)
            last_pnl_data.append([f"  {cat}", amt, (amt / total_rev) if total_rev else 0])

    last_pnl_data.extend(
        [
            ["TOTAL OPEX", total_opex, (total_opex / total_rev) if total_rev else 0],
            ["NET PROFIT", net_profit, (net_profit / total_rev) if total_rev else 0],
        ]
    )

    rep = f"{' ' * 20}PROFIT & LOSS STATEMENT - All Year\n"
    rep += f"╔{'═'*42}╦{'═'*17}╦{'═'*12}╗\n"
    rep += _format_line("DESCRIPTION", "AMOUNT ($)", "% OF REV")
    rep += f"╠{'═'*42}╬{'═'*17}╬{'═'*12}╣\n"

    for row in last_pnl_data:
        if row[0] and not row[1] and not row[2]:
            rep += f"║ {row[0]:<40} ║ {'':>15} ║ {'':>10} ║\n"
        elif not row[0]:
            rep += f"╠{'─'*42}╬{'─'*17}╬{'─'*12}╣\n"
        else:
            rep += _format_line(row[0], f"{row[1]:,.2f}", f"{(row[2]*100):.1f}%")

    rep += f"╚{'═'*42}╩{'═'*17}╩{'═'*12}╝\n"

    return rep, last_pnl_data, net_profit

def _draw_charts_png(expenses_df: pd.DataFrame) -> bytes:
    # very close to your Tkinter draw_charts
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
    fig.patch.set_facecolor(COLORS["light_bg"])

    # Vendor Spend
    if expenses_df is not None and not expenses_df.empty:
        top_v = expenses_df.groupby("Vendor")["Amount"].sum().sort_values(ascending=False).head(5)
        wrapped_labels = [textwrap.fill(str(label), width=15) for label in top_v.index]

        top_v.plot(
            kind="bar",
            ax=ax1,
            color=[COLORS["pink"], COLORS["purple"], COLORS["blue"], COLORS["yellow"], COLORS["teal"]],
        )

        ax1.set_xticklabels(wrapped_labels, rotation=30, ha="right")
        ax1.set_ylabel("USD ($)")
        ax1.set_xlabel("Vendor")
        ax1.set_title("Top 5 Vendor Spend")
        ax1.set_facecolor(COLORS["report_bg"])

        # Expense breakdown pie
        expense_breakdown = expenses_df.groupby("Category")["Amount"].sum()
        pie_colors = [COLORS["pink"], COLORS["purple"], COLORS["blue"], COLORS["yellow"], COLORS["green"], COLORS["red"]]
        colors_for_pie = [pie_colors[i % len(pie_colors)] for i in range(len(expense_breakdown))]
        pie_labels = [textwrap.fill(str(label), width=20) for label in expense_breakdown.index]

        ax2.pie(
            expense_breakdown,
            labels=pie_labels,
            autopct="%1.1f%%",
            colors=colors_for_pie,
            textprops={"color": COLORS["text"]},
        )
        ax2.set_title("Expense Breakdown by Category")
    else:
        ax1.text(0.5, 0.5, "No expense data available", ha="center", va="center", transform=ax1.transAxes)
        ax1.set_title("Top 5 Vendor Spend")
        ax2.text(0.5, 0.5, "No expense data available", ha="center", va="center", transform=ax2.transAxes)
        ax2.set_title("Expense Breakdown by Category")

    for ax in (ax1, ax2):
        ax.title.set_color(COLORS["text"])
        ax.xaxis.label.set_color(COLORS["text"])
        ax.yaxis.label.set_color(COLORS["text"])
        ax.tick_params(colors=COLORS["text"])

    fig.tight_layout()

    out = io.BytesIO()
    fig.savefig(out, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out.getvalue()


# ----------------------------
# Routes
# ----------------------------
@app.route("/")
def home():
    return redirect(url_for("pnl"))

@app.route("/pnl", methods=["GET", "POST"])
def pnl():
    if request.method == "POST":
        try:
            # settings
            STATE.include_tips = bool(request.form.get("include_tips"))
            flash("Settings updated.", "info")
        except Exception:
            pass
        return redirect(url_for("pnl"))

    return render_template(
        "pnl.html",
        colors=COLORS,
        report_text=STATE.report_text,
        include_tips=STATE.include_tips,
        has_files=(STATE.sales_df is not None and STATE.exp_df_raw is not None),
    )

@app.route("/upload", methods=["POST"])
def upload():
    sales_file = request.files.get("sales_file")
    exp_file = request.files.get("exp_file")

    if not sales_file or not exp_file or not sales_file.filename or not exp_file.filename:
        flash("Please choose BOTH Sales and Expenses files.", "danger")
        return redirect(url_for("pnl"))

    try:
        sales_df = _read_sales_file(sales_file)
        exp_df_raw = _read_expenses_file(exp_file)
        STATE.sales_df = sales_df
        STATE.exp_df_raw = exp_df_raw
        flash("Files loaded successfully!", "success")
    except Exception as e:
        flash(f"File load failed: {e}", "danger")

    return redirect(url_for("pnl"))

@app.route("/generate", methods=["POST"])
def generate():
    if STATE.sales_df is None or STATE.exp_df_raw is None:
        flash("Load files first!", "danger")
        return redirect(url_for("pnl"))

    # include tips toggle
    STATE.include_tips = bool(request.form.get("include_tips"))

    try:
        sales_summary = _parse_sales_summary(STATE.sales_df)
        expenses_df = _parse_expenses(STATE.exp_df_raw)

        report_text, last_pnl_data, net_profit = _build_report_and_tables(
            sales_summary=sales_summary,
            expenses_df=expenses_df,
            include_tips=STATE.include_tips,
        )

        STATE.report_text = report_text
        STATE.last_pnl_data = last_pnl_data
        STATE.current_net_profit = net_profit

        # update tax report too
        tax_txt, _ = _calc_hanover_tax_text(
            net=STATE.current_net_profit,
            fed_income_rate=STATE.fed_income_rate,
            local_eit_rate=STATE.local_eit_rate,
        )
        STATE.last_tax_txt = tax_txt

        # charts image
        STATE.charts_png = _draw_charts_png(expenses_df)

        flash("Report generated!", "success")
    except Exception as e:
        flash(f"Processing failed: {e}", "danger")

    return redirect(url_for("pnl"))

@app.route("/download_excel")
def download_excel():
    if not STATE.last_pnl_data:
        flash("Generate a report first!", "warning")
        return redirect(url_for("pnl"))

    df_export = pd.DataFrame(STATE.last_pnl_data, columns=["Description", "Amount ($)", "% of Total"])

    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df_export.to_excel(writer, index=False, sheet_name="P&L Report")
        wb = writer.book
        ws = writer.sheets["P&L Report"]

        # Basic formatting similar to your original
        for cell in ws["B"]:
            cell.number_format = "#,##0.00"
        for cell in ws["C"]:
            cell.number_format = "0.0%"

        # widen columns a bit
        ws.column_dimensions["A"].width = 45
        ws.column_dimensions["B"].width = 16
        ws.column_dimensions["C"].width = 12

    bio.seek(0)
    filename = f"Pnl_Report_{datetime.date.today().isoformat()}.xlsx"
    return send_file(
        bio,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

@app.route("/analytics")
def analytics():
    return render_template(
        "analytics.html",
        colors=COLORS,
        has_chart=bool(STATE.charts_png),
    )

@app.route("/charts.png")
def charts_png():
    if not STATE.charts_png:
        flash("Generate a report first to see charts.", "warning")
        return redirect(url_for("analytics"))
    return send_file(io.BytesIO(STATE.charts_png), mimetype="image/png")

@app.route("/tax", methods=["GET", "POST"])
def tax():
    if request.method == "POST":
        try:
            STATE.fed_income_rate = float(request.form.get("fed_income_rate", STATE.fed_income_rate))
            STATE.local_eit_rate = float(request.form.get("local_eit_rate", STATE.local_eit_rate))

            tax_txt, _ = _calc_hanover_tax_text(
                net=STATE.current_net_profit,
                fed_income_rate=STATE.fed_income_rate,
                local_eit_rate=STATE.local_eit_rate,
            )
            STATE.last_tax_txt = tax_txt
            flash("Tax recalculated!", "success")
        except Exception as e:
            flash(f"Could not recalculate: {e}", "danger")

        return redirect(url_for("tax"))

    return render_template(
        "tax.html",
        colors=COLORS,
        fed_income_rate=STATE.fed_income_rate,
        local_eit_rate=STATE.local_eit_rate,
        tax_text=STATE.last_tax_txt,
        current_net_profit=STATE.current_net_profit,
    )

@app.route("/download_tax_report")
def download_tax_report():
    if not STATE.last_tax_txt:
        flash("Please calculate taxes first!", "warning")
        return redirect(url_for("tax"))

    bio = io.BytesIO(STATE.last_tax_txt.encode("utf-8"))
    filename = f"Tax_Report_{datetime.date.today().isoformat()}.txt"
    return send_file(bio, as_attachment=True, download_name=filename, mimetype="text/plain")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)

