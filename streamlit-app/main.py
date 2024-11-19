import streamlit as st

chat_page = st.Page("chat.py", title="Chat UI", icon=":material/message:")

admin_page = st.Page("admin.py", title="Grounding Data", icon=":material/add_circle:")

pg = st.navigation([chat_page, admin_page])
st.set_page_config(page_title="AI Agent")
pg.run()