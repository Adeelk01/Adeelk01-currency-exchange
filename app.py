# app.py
# Simple Currency Converter for Hugging Face Spaces (Gradio)
# No API key required — uses public CDN JSON files (daily-updated).

import requests
import time
import gradio as gr

PRIMARY_BASE = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies"
FALLBACK_BASE = "https://latest.currency-api.pages.dev/v1/currencies"
CACHE_TTL_SECS = 5 * 60

_cache = {"ts": 0, "date": None, "rates": {}}

def _try_fetch(url, timeout=10):
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()

def _fetch_base_rates(base_code: str):
    base = base_code.lower()
    for root in (PRIMARY_BASE, FALLBACK_BASE):
        try:
            data = _try_fetch(f"{root}/{base}.json")
            # expected shape: {"date":"YYYY-MM-DD", "<base>": { "pkr": 278.1, "gbp": 0.76, ... } }
            if "date" in data and base in data:
                return data["date"], data[base]
        except Exception:
            continue
    raise RuntimeError("Could not download rates from both sources. Check internet access.")

def _get_usd_rates(force_refresh=False):
    now = time.time()
    if (not force_refresh) and _cache["rates"] and (now - _cache["ts"] < CACHE_TTL_SECS):
        return _cache["date"], _cache["rates"]
    date, rates = _fetch_base_rates("usd")
    _cache.update(ts=now, date=date, rates=rates)
    return date, rates

def available_codes():
    _, usd = _get_usd_rates(force_refresh=True)
    codes = set(k.upper() for k in usd.keys()) | {"USD"}
    popular = ["USD","EUR","GBP","PKR","INR","AED","SAR","USDT","CNY","JPY"]
    rest = sorted([c for c in codes if c not in popular])
    ordered = [c for c in popular if c in codes] + rest
    return ordered

def convert(amount, from_code, to_code):
    try:
        amt = float(amount)
    except Exception:
        return "", "Invalid amount (must be a number)."
    if amt < 0:
        return "", "Amount must be non-negative."

    a = (from_code or "").strip().lower()
    b = (to_code or "").strip().lower()
    if not a or not b:
        return "", "Please choose both currencies."

    date, usd = _get_usd_rates()
    r_from = 1.0 if a == "usd" else usd.get(a)
    r_to   = 1.0 if b == "usd" else usd.get(b)

    # If any code missing from the USD hub, try direct base fetch; otherwise compute cross-rate
    if (r_from is None) or (r_to is None):
        try:
            d_date, d_map = _fetch_base_rates(a)
            direct = d_map.get(b)
            if direct is not None:
                res = amt * direct
                return f"{res:,.6f} {to_code.upper()}", f"Rate: 1 {from_code.upper()} = {direct:.6f} {to_code.upper()}  (date {d_date})"
        except Exception:
            pass
        return "", f"Pair not available: {from_code.upper()} → {to_code.upper()}"

    rate = r_to / r_from
    res = amt * rate
    return f"{res:,.6f} {to_code.upper()}", f"1 {from_code.upper()} = {rate:.6f} {to_code.upper()}  (last update {date})"

# Build UI (simple and exactly like the Colab version)
codes = available_codes()

with gr.Blocks(title="Simple Currency Converter (No API Key)") as demo:
    gr.Markdown("# 💱 Simple Currency Converter — No API Key\nConvert between 200+ currencies including USDT, PKR, INR, AED, SAR, GBP, USD, EUR.")
    with gr.Row():
        amount = gr.Number(value=1.0, label="Amount")
    with gr.Row():
        from_dd = gr.Dropdown(choices=codes, value="USD", label="From")
        to_dd = gr.Dropdown(choices=codes, value="PKR", label="To")
    with gr.Row():
        convert_btn = gr.Button("Convert", variant="primary")
        swap_btn    = gr.Button("Swap")
        refresh_btn = gr.Button("Refresh Rates")
    result_box = gr.Textbox(label="Converted Amount", interactive=False)
    info_box   = gr.Textbox(label="Rate / Info", interactive=False)

    def on_convert(amount, from_code, to_code):
        res, info = convert(amount, from_code, to_code)
        return res, info

    def on_swap(f, t):
        return t, f

    def on_refresh():
        _get_usd_rates(force_refresh=True)
        new_codes = available_codes()
        return gr.update(choices=new_codes), gr.update(choices=new_codes), "✅ Rates refreshed (fetched latest)."

    convert_btn.click(on_convert, [amount, from_dd, to_dd], [result_box, info_box])
    swap_btn.click(on_swap, [from_dd, to_dd], [from_dd, to_dd])
    refresh_btn.click(on_refresh, None, [from_dd, to_dd, info_box])

# On Hugging Face Spaces it's fine to call launch() (the platform runs the script automatically)
if __name__ == "__main__":
    demo.launch()
