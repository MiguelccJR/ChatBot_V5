"""
Shared authentication module for all Streamlit pages.
"""
import hmac
import streamlit as st


def get_auth_users() -> dict:
    try:
        auth_cfg = st.secrets["auth"]
        users_cfg = auth_cfg["users"]
        users = {}
        for username in users_cfg:
            entry = users_cfg[username]
            users[username] = {
                "password": str(entry["password"]),
                "role": str(entry.get("role", "user")),
            }
        return users
    except Exception:
        return {}


def init_auth():
    if "auth_username" not in st.session_state:
        st.session_state.auth_username = None
    if "auth_role" not in st.session_state:
        st.session_state.auth_role = "user"


def is_logged_in() -> bool:
    return bool(st.session_state.get("auth_username"))


def is_admin() -> bool:
    return st.session_state.get("auth_role") == "admin"


def login(username: str, password: str) -> bool:
    users = get_auth_users()
    user = users.get(username)
    if not user:
        return False
    if not hmac.compare_digest(password, user["password"]):
        return False
    st.session_state.auth_username = username
    st.session_state.auth_role = user.get("role", "user")
    return True


def logout():
    st.session_state.auth_username = None
    st.session_state.auth_role = "user"
    st.rerun()


def render_sidebar_auth():
    with st.sidebar:
        st.subheader("Account")
        if is_logged_in():
            st.success(f"✅ **{st.session_state.auth_username}**")
            if st.button("Logout", use_container_width=True, key="logout_btn"):
                logout()


def login_gate():
    """
    Call at the very top of every page (after set_page_config).
    Hides sidebar and shows only a login form until authenticated.
    """
    init_auth()
    if not is_logged_in():
        # Hide sidebar completely
        st.markdown("""
            <style>
                [data-testid="stSidebar"] { display: none; }
                [data-testid="collapsedControl"] { display: none; }
            </style>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("## 🔐 Control Panel")
            st.markdown("---")
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", use_container_width=True)
                if submitted:
                    if login(username.strip(), password):
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
        st.stop()