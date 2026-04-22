import streamlit as st
from db import get_bot_config, upsert_bot_config, delete_bot_config
from auth import login_gate, render_sidebar_auth

st.set_page_config(page_title="Bot Configuration", layout="wide")
login_gate()
render_sidebar_auth()
st.title("⚙️ Bot Configuration")
st.caption("Edit prices, links and settings. Changes apply immediately.")

CATEGORY_LABELS = {
    "price": "💰 Prices",
    "link": "🔗 Links",
    "setting": "⚙️ Settings",
    "persona": "🧍 Persona",
}

CATEGORY_OPTIONS = ["price", "link", "setting", "persona"]

# ----------------------------
# Load all config
# ----------------------------
try:
    all_config = get_bot_config()
except Exception as e:
    st.error(f"Error loading config: {e}")
    st.stop()

config_by_category = {}
for row in all_config:
    cat = row["category"]
    if cat not in config_by_category:
        config_by_category[cat] = []
    config_by_category[cat].append(row)

# ----------------------------
# Display and edit by category
# ----------------------------
for category in CATEGORY_OPTIONS:
    label = CATEGORY_LABELS.get(category, category)
    st.subheader(label)

    rows = config_by_category.get(category, [])

    if not rows:
        st.caption("No entries yet.")
    else:
        for row in rows:
            col1, col2, col3, col4 = st.columns([2, 3, 3, 1])

            with col1:
                st.text(row["key"])

            with col2:
                new_value = st.text_input(
                    "Value",
                    value=row["value"] or "",
                    key=f"val_{row['key']}",
                    label_visibility="collapsed",
                    placeholder="Value"
                )

            with col3:
                new_desc = st.text_input(
                    "Description",
                    value=row["description"] or "",
                    key=f"desc_{row['key']}",
                    label_visibility="collapsed",
                    placeholder="Description"
                )

            with col4:
                col_save, col_del = st.columns(2)
                with col_save:
                    if st.button("💾", key=f"save_{row['key']}", help="Save"):
                        try:
                            upsert_bot_config(
                                category=category,
                                key=row["key"],
                                value=new_value,
                                description=new_desc
                            )
                            st.success("Saved")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                with col_del:
                    if st.button("🗑️", key=f"del_{row['key']}", help="Delete"):
                        try:
                            delete_bot_config(row["key"])
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

    st.divider()

# ----------------------------
# Add new entry
# ----------------------------
st.subheader("➕ Add new entry")

col1, col2, col3, col4, col5 = st.columns([2, 2, 3, 3, 1])

with col1:
    new_category = st.selectbox("Category", options=CATEGORY_OPTIONS, key="new_category")
with col2:
    new_key = st.text_input("Key", placeholder="e.g. pack_5_photos", key="new_key")
with col3:
    new_value = st.text_input("Value", placeholder="e.g. $10", key="new_value")
with col4:
    new_desc = st.text_input("Description", placeholder="e.g. 5 photos pack", key="new_desc")
with col5:
    st.write("")
    st.write("")
    if st.button("Add", use_container_width=True):
        if not new_key.strip():
            st.warning("Key is required.")
        else:
            try:
                upsert_bot_config(
                    category=new_category,
                    key=new_key.strip(),
                    value=new_value.strip(),
                    description=new_desc.strip()
                )
                st.success(f"Added: {new_key}")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")