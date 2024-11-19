import streamlit as st  
import json  
import pandas as pd  
  
st.title('Grounding data')  
  
# Load existing data  
try:  
    with open('queries.json', 'r') as f:  
        queries = json.load(f)  
except FileNotFoundError:  
    queries = []  
  
# Function to save data  
def save_queries(queries):  
    with open('queries.json', 'w') as f:  
        json.dump(queries, f)  
  
# Function to add new query  
@st.dialog("Admin Options")  
def admin_options():  
    option = st.radio("Choose an option:", ("Example queries", "Methodology"))  
  
    if option == "Example queries":  
        with st.form(key='query_form'):  
            question = st.text_input('Enter the question')  
            sql_query = st.text_area('Enter the SQL query')  
            submit_button = st.form_submit_button(label='Add Query')  
  
            if submit_button:  
                queries.append({'question': question, 'sql_query': sql_query})  
                save_queries(queries)  
                st.success('Query added successfully!')  
                st.rerun()  
    elif option == "Methodology":  
        uploaded_file = st.file_uploader("Upload a document", type=["pdf", "docx", "txt"])  
        if uploaded_file is not None:  
            with open(uploaded_file.name, "wb") as f:  
                f.write(uploaded_file.getbuffer())  
            st.success(f"Uploaded {uploaded_file.name} successfully!")  

if st.button("Add Data"):  
    admin_options()  
  
# Display existing queries in an expandable section with delete option  
with st.expander("Existing SQL Queries"):  
    st.write("### Existing Queries")  
    if queries:  
        # Convert queries list to a DataFrame  
        df = pd.DataFrame(queries)  
          
        # Display the table without making it editable  
        st.table(df)  
    else:  
        st.write("No queries found.")  