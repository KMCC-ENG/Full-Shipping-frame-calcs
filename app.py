"""Single entry point for the three independent Streamlit calculators."""

from base64 import b64encode
from importlib import import_module
from pathlib import Path

import streamlit as st


ASSETS = Path(__file__).resolve().parent / "assets"
CALCULATORS = {
    "coil_cg": ("Coil Center of Gravity", "tube_cg_calculator"),
    "tube_load": ("Tube Load Analyzer", "beam_stress_calculator"),
    "shipping_frame": ("Shipping Frame Load Analyzer", "shipping_frame_calculator"),
}


def navigate(destination):
    # Only the current view changes. Each calculator owns its model and widgets.
    st.session_state.suite_view = destination


@st.cache_data(show_spinner=False)
def homepage_style():
    css = (ASSETS / "home.css").read_text(encoding="utf-8")
    for name in CALCULATORS:
        picture = b64encode((ASSETS / f"home_{name}.png").read_bytes()).decode("ascii")
        css += f'\n.st-key-open_{name} button::before {{ background-image: url("data:image/png;base64,{picture}"); }}'
    return f"<style>{css}</style>"


def homepage():
    st.html(homepage_style())
    with st.container(key="suite_homepage"):
        st.title("Engineering Calculators")
        for column, (name, (title, _module)) in zip(st.columns(3, gap="small"), CALCULATORS.items()):
            column.button(title, key=f"open_{name}", on_click=navigate, args=(name,), width="stretch", wrap=True)


def main():
    view = st.session_state.get("suite_view", "home")
    calculator = CALCULATORS.get(view)
    title = calculator[0] if calculator else "Engineering Calculators"
    st.set_page_config(page_title=title, layout="wide", initial_sidebar_state="auto")

    if calculator is None:
        homepage()
        return

    st.html(ASSETS / "navigation.css")
    st.button("← Home", key="suite_home", on_click=navigate, args=("home",))
    # Import only the chosen calculator, so opening Home never initializes a model.
    import_module(calculator[1]).render_app()


if __name__ == "__main__":
    main()
