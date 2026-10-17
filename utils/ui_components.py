"""
Reusable UI helper components for Streamlit POS.
Provides custom CSS injection, styled metric cards, page headers, and session initialization.
"""
from pathlib import Path
from typing import Optional
import streamlit as st


def apply_custom_css():
    """Inject custom desktop POS CSS styling."""
    css_path = Path(__file__).resolve().parent.parent / ".streamlit" / "style.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
            st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def init_session_state():
    """Initialize essential session state variables."""
    if "cart" not in st.session_state:
        st.session_state.cart = []
    if "user" not in st.session_state:
        st.session_state.user = {
            "id": 1,
            "username": "admin",
            "role": "owner"
        }
    if "discount_amount" not in st.session_state:
        st.session_state.discount_amount = 0.0
    if "discount_type" not in st.session_state:
        st.session_state.discount_type = "Fixed (₹)"


def render_page_header(title: str, subtitle: Optional[str] = None, icon: Optional[str] = None, **kwargs):
    """Render consistent page top banner."""
    icon_str = f"{icon} " if icon else ""
    st.markdown(f"### {icon_str}{title}")
    if subtitle:
        st.caption(subtitle)
    st.markdown("---")


def render_metric_card(title: str, value: str, subtext: Optional[str] = None, **kwargs):
    """Render a modern glassmorphic metric card."""
    sub_html = f'<div class="pos-metric-sub">{subtext}</div>' if subtext else ""
    html = f"""
    <div class="pos-metric-card">
        <div class="pos-metric-title">{title}</div>
        <div class="pos-metric-value">{value}</div>
        {sub_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
