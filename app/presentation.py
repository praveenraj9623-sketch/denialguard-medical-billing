"""Visual styles and display-only markup for the DenialGuard workspace."""
from html import escape
import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
:root{--dg-ink:#192c45;--dg-muted:#64758b;--dg-line:#dce5ef;--dg-blue:#3158bf;}
.stApp{background:#f5f7fb;color:var(--dg-ink);font-family:'DM Sans',sans-serif;}
.stMainBlockContainer,.block-container{max-width:1400px;padding-top:4rem!important;padding-bottom:3rem;}
h1,h2,h3,h4{font-family:'Manrope',sans-serif!important;letter-spacing:-.03em!important;color:var(--dg-ink)!important;}
h2{font-size:1.4rem!important}h3{font-size:1.16rem!important}h4{font-size:1.05rem!important}
[data-testid="stCaptionContainer"]{color:var(--dg-muted);line-height:1.6;}
[data-testid="stVerticalBlock"]{gap:.8rem;}
hr{margin:1rem 0!important;border-color:var(--dg-line)!important;}
.stButton button,.stDownloadButton button,[data-testid="stPopover"] button{border-radius:9px;min-height:42px;font-weight:600;}
.stButton button[kind="primary"],.stFormSubmitButton button[kind="primary"]{background:#3158bf;border-color:#3158bf;}
.stButton button[kind="primary"]:hover{background:#27489e;border-color:#27489e;}
.stButton button:focus-visible,.stDownloadButton button:focus-visible{outline:3px solid #8faaf0;outline-offset:3px;}
button[data-baseweb="tab"]{padding:0 1.1rem;font-weight:600;font-size:.91rem;}
[data-baseweb="tab-list"]{gap:.2rem;border-bottom:1px solid var(--dg-line);padding-bottom:.3rem;}
[data-baseweb="tab-highlight"]{background:#3158bf;}
[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea{background:#fff;}
[data-testid="stMetric"]{padding:16px 18px;border:1px solid var(--dg-line);border-radius:12px;background:#fff;}
[data-testid="stMetricLabel"]{color:var(--dg-muted);font-size:.8rem;}
[data-testid="stMetricValue"]{font-family:'Manrope',sans-serif;font-size:1.65rem;font-weight:700;}
[data-testid="stAlert"]{border-radius:11px;}
[data-testid="stExpander"]{border-color:var(--dg-line);background:#fff;border-radius:11px;}
[data-testid="stDataFrame"]{border-radius:12px;}
div[class*="st-key-finding_card_"]{border:1px solid var(--dg-line)!important;border-radius:15px!important;background:white;padding:20px!important;margin:6px 0 14px;box-shadow:0 3px 13px #20365005;}
div[class*="st-key-finding_card_"] [data-testid="stCaptionContainer"]{font-size:.78rem;}
div[class*="st-key-finding_card_"] [data-testid="stTextArea"] textarea{background:#f8fafc;}
.st-key-header_controls_row{border:1px solid var(--dg-line);border-radius:14px;background:#fff;padding:17px 20px;margin:1rem 0 .4rem;}
.st-key-header_controls_row [data-testid="stHorizontalBlock"]{align-items:flex-start!important;}
.dg-hero{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:1rem;}
.dg-identity{display:flex;align-items:center;gap:14px;}
.dg-logo{width:47px;height:47px;border-radius:14px;display:flex;align-items:center;justify-content:center;background:#e8eefc;color:#3158bf;flex-shrink:0;}
.dg-hero h1{font-size:1.9rem!important;line-height:1.2!important;margin:0;padding:0;}
.dg-hero p{font-size:.88rem;color:var(--dg-muted);margin:7px 0 0;line-height:1.6;}
.dg-badge{display:inline-flex;align-items:center;gap:5px;padding:6px 10px;border-radius:6px;font-size:.67rem;font-weight:700;letter-spacing:.04em;white-space:nowrap;}
.dg-badge.demo{color:#3a527b;background:#eaf0fc;border:1px solid #d9e3f7;}
.dg-badge.source{color:#596d88;background:#edf2f7;}
.dg-badge.agent{color:#6150a4;background:#f0ecfb;}
.dg-badge.HIGH{color:#a22f40;background:#fbecef;}
.dg-badge.MEDIUM{color:#8e5b08;background:#fff4d9;}
.dg-badge.LOW{color:#245aa0;background:#eaf2fd;}
.dg-finding{border-left:3px solid #3158bf;padding-left:13px;margin:0 0 13px;}
.dg-finding.HIGH{border-color:#c15868}.dg-finding.MEDIUM{border-color:#d9a342}.dg-finding.LOW{border-color:#5b89cb}
.dg-finding-tags{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-bottom:11px;}
.dg-finding h3{font-size:1.02rem!important;line-height:1.65!important;font-weight:750;margin:0;padding:0;letter-spacing:-.015em!important;overflow-wrap:anywhere;}
.dg-section{margin:14px 0 15px;}
.dg-eyebrow{color:#496695;font-size:.68rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin:0 0 7px;}
.dg-section h2{font-size:1.2rem!important;margin:0 0 5px;padding:0;}
.dg-section p{font-size:.82rem;color:var(--dg-muted);margin:0;line-height:1.65;}
.dg-claim-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:1rem 0;}
.dg-claim{padding:19px 21px;background:white;border:1px solid var(--dg-line);border-radius:13px;min-width:0;}
.dg-claim h3{font-size:.9rem!important;margin:0 0 13px;padding:0;}
.dg-claim dl{margin:0;display:grid;grid-template-columns:1fr 1fr;gap:15px;}
.dg-claim dl>div{min-width:0}.dg-claim dt{font-size:.71rem;color:var(--dg-muted);margin-bottom:5px;}
.dg-claim dd{font-size:.86rem;font-weight:500;margin:0;overflow-wrap:anywhere;line-height:1.6;}
.dg-note{padding:11px 14px;background:#edf2fa;border-left:3px solid #94aadb;border-radius:0 9px 9px 0;color:#53667f;font-size:.77rem;line-height:1.7;margin:.5rem 0;}
.dg-excerpt{background:#f6f8fc;border-left:3px solid #bac9dd;padding:13px 15px;border-radius:0 8px 8px 0;color:#485c73;font-size:.84rem;line-height:1.8;white-space:pre-wrap;overflow-wrap:anywhere;}
.dg-footer{font-size:.73rem;color:var(--dg-muted);line-height:1.65;margin-top:1.5rem;padding-top:15px;border-top:1px solid var(--dg-line);}
@media(max-width:760px){.stMainBlockContainer,.block-container{padding:4rem 1rem 2rem!important}.dg-hero{align-items:flex-start;flex-direction:column;gap:14px}.dg-hero h1{font-size:1.6rem!important}.dg-claim-grid{grid-template-columns:1fr}.st-key-header_controls_row{padding:14px}.dg-claim{padding:16px}div[class*="st-key-finding_card_"]{padding:14px!important}}
</style>
"""


def safe(value):
    return escape(str(value), quote=True)


def style():
    st.markdown(CSS, unsafe_allow_html=True)


def hero():
    st.markdown('''<div class="dg-hero"><div class="dg-identity"><div class="dg-logo" aria-hidden="true"><svg width="27" height="27" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 3 4 6v6c0 4.5 8 9 8 9s8-4.5 8-9V6l-8-3Z"/><path d="m8.5 12 2.5 2.5 4.5-5"/></svg></div><div><h1>DenialGuard</h1><p>Claim review workspace · Evidence first. Human decisions.</p></div></div><span class="dg-badge demo">Portfolio prototype · Synthetic data only</span></div>''', unsafe_allow_html=True)


def section(title, subtitle, eyebrow=""):
    return f'<div class="dg-section"><div class="dg-eyebrow">{safe(eyebrow)}</div><h2>{safe(title)}</h2><p>{safe(subtitle)}</p></div>'


def finding_header(severity, source, issue, cached=False):
    # Fixed class allowlist; source and model text are escaped before HTML use.
    level = severity if severity in {"HIGH", "MEDIUM", "LOW"} else "LOW"
    source_cls = "source" if source == "Rule Engine" else "agent"
    preview = '<span class="dg-badge demo">Recorded example · not this run</span>' if cached else ""
    return f'<div class="dg-finding {level}"><div class="dg-finding-tags"><span class="dg-badge {level}">{safe(severity)} SEVERITY</span><span class="dg-badge {source_cls}">{safe(source)}</span>{preview}</div><h3>{safe(issue)}</h3></div>'


def claim_summary(claim):
    groups = [
        ("Claim & provider", [("Claim ID", claim['claim_id']), ("Payer", claim['payer']), ("Provider NPI", claim.get('npi') or 'Not provided'), ("Place of service", claim['place_of_service'])]),
        ("Submitted codes", [("CPT / HCPCS", ', '.join(claim['cpt_codes'])), ("ICD-10 diagnoses", ', '.join(claim['icd10_codes'])), ("Modifiers", ', '.join(claim.get('modifiers', [])) or 'None provided')]),
    ]
    return '<div class="dg-claim-grid">' + ''.join(
        f'<section class="dg-claim"><h3>{safe(title)}</h3><dl>' + ''.join(
            f'<div><dt>{safe(label)}</dt><dd>{safe(value)}</dd></div>' for label, value in fields) + '</dl></section>'
        for title, fields in groups) + '</div>'


def excerpt(text):
    return f'<div class="dg-excerpt">{safe(text)}</div>'


def scenario_label(value):
    """Format an existing option without changing its stored value or claim ID."""
    claim_id = value.partition(" — ")[0]
    demo = value.rpartition("  ·  ")[-1]
    return f"{claim_id} — {demo}" if demo and demo != value else claim_id
