"""
Shared authentication module for all Streamlit pages.
Import this in every page to get consistent login state.
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
    """Initialize auth state. Call at the top of every page."""
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
    """Renders the login/logout widget in the sidebar. Call in every page."""
    with st.sidebar:
        st.subheader("Access")
        if is_logged_in():
            st.success(f"Logged in as **{st.session_state.auth_username}** ({st.session_state.auth_role})")
            if st.button("Logout", use_container_width=True, key="logout_btn"):
                logout()
        else:
            st.info("Normal mode active")
            users = get_auth_users()
            if users:
                with st.expander("Admin login"):
                    with st.form("login_form_shared", clear_on_submit=False):
                        login_user = st.text_input("User")
                        login_pass = st.text_input("Password", type="password")
                        submitted = st.form_submit_button("Login as admin", use_container_width=True)
                        if submitted:
                            if login(login_user.strip(), login_pass):
                                st.rerun()
                            else:
                                st.error("Invalid username or password")


def require_admin():
    """
    Call at the top of admin-only pages.
    If not admin, shows login form and stops execution.
    """
    init_auth()
    if not is_admin():
        st.warning("🔒 This page is only visible to admins.")
        users = get_auth_users()
        if users:
            with st.form("admin_login_required", clear_on_submit=False):
                st.subheader("Admin login required")
                login_user = st.text_input("User")
                login_pass = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", use_container_width=True)
                if submitted:
                    if login(login_user.strip(), login_pass) and is_admin():
                        st.rerun()
                    else:
                        st.error("Invalid credentials or insufficient permissions")
        st.stop()