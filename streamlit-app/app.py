from dotenv import load_dotenv
import os 
from openai import AzureOpenAI
import pandas as pd
import streamlit as st
import pyodbc
from sqlalchemy import create_engine
import urllib
import json

load_dotenv()

endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
api_key = os.getenv('AZURE_OPENAI_API_KEY')
server = os.getenv('AZURE_SQL_SERVER') 
database = os.getenv('AZURE_SQL_DB_NAME')
username = os.getenv('AZURE_SQL_USER') 
password = os.getenv('AZURE_SQL_PASSWORD')

connection_string = f'Driver={{ODBC Driver 18 for SQL Server}};Server=tcp:{server},1433;Database={database};Uid={username};Pwd={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'

params = urllib.parse.quote_plus(connection_string)
conn_str = 'mssql+pyodbc:///?odbc_connect={}'.format(params)
engine_azure = create_engine(conn_str,echo=False)


def query_azure_sql(query: str) -> str:
    """Run a SQL query on Azure SQL and return results as a pandas DataFrame"""
    print(f"Executing query on Azure SQL: {query}")
    df = pd.read_sql(query, engine_azure)
    return json.dumps(df.to_dict(orient='records'))

def get_table_schema(table_name: str) -> str:
    """Get the schema of a table in Azure SQL"""
    query = f"SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{table_name}'"
    print(f"Executing query on Azure SQL: {query}")
    df = pd.read_sql(query, engine_azure)
    return json.dumps(df.to_dict(orient='records'))

def get_tools():
    return [
        {
            "type": "function",
            "function": {
                "name": "query_azure_sql",
                "description": "Execute a SQL query to retrieve information from a database",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The SQL query to execute",
                        },
                    },
                    "required": ["query"],
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_table_schema",
                "description": "Get the schema of a table in Azure SQL",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "The name of the table to get the schema for",
                        },
                    },
                    "required": ["table_name"],
                },
            }
        },
    ]

def get_available_functions():
    return {"query_azure_sql":query_azure_sql}

def init_messages():
    return [
    {"role":"system", "content":"""You are a helpful AI data analyst assistant, 
     You can execute SQL queries to retrieve information from a sql table, the table name is sales_data
     Here is the table schema
              COLUMN_NAME DATA_TYPE
0              index    bigint
1        ORDERNUMBER    bigint
2    QUANTITYORDERED    bigint
3          PRICEEACH     float
4    ORDERLINENUMBER    bigint
5              SALES     float
6          ORDERDATE   varchar
7             STATUS   varchar
8             QTR_ID    bigint
9           MONTH_ID    bigint
10           YEAR_ID    bigint
11       PRODUCTLINE   varchar
12              MSRP    bigint
13       PRODUCTCODE   varchar
14      CUSTOMERNAME   varchar
15             PHONE   varchar
16      ADDRESSLINE1   varchar
17      ADDRESSLINE2   varchar
18              CITY   varchar
19             STATE   varchar
20        POSTALCODE   varchar
21           COUNTRY   varchar
22         TERRITORY   varchar
23   CONTACTLASTNAME   varchar
24  CONTACTFIRSTNAME   varchar
25          DEALSIZE   varchar
     
     """}
]

client = AzureOpenAI(
    azure_endpoint=endpoint,
    api_key=api_key,
    api_version='2024-02-01'
)

st.title("Chat with Azure SQL")

# Set a default model
if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-4o-global"

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

messages = init_messages()+[
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ]

# Accept user input
if prompt := st.chat_input("What is up?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    messages.append({"role": "user", "content": prompt})
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)


# Display assistant response in chat message container
    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model=st.session_state["openai_model"],
            messages=messages,
            stream=True,
            tools = get_tools(),
            tool_choice="auto"
        )

        tool_calls=[]

        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices and chunk.choices[0].delta is not None else None
            if delta and delta.content:
                response = st.write_stream(stream)
                break
            elif delta and delta.tool_calls:
                tc_chunk_list = delta.tool_calls
                for tc_chunk in tc_chunk_list:
                    if len(tool_calls) <= tc_chunk.index:
                        tool_calls.append({"id":"", "type":"function", "function":{"name":"", "arguments":""}})
                    
                    tc = tool_calls[tc_chunk.index]
                    if tc_chunk.id:
                        tc["id"] += tc_chunk.id
                    if tc_chunk.function.name:
                        tc["function"]["name"] += tc_chunk.function.name
                    if tc_chunk.function.arguments:
                        tc["function"]["arguments"] += tc_chunk.function.arguments
    
        if tool_calls:
            messages.append({"role":"assistant", "tool_calls":tool_calls})
            available_functions = get_available_functions()
        
            for tool_call in tool_calls:
                # Note: the JSON response may not always be valid; be sure to handle errors
                    function_name = tool_call['function']['name']
                
                    # Step 3: call the function with arguments if any
                    function_to_call = available_functions[function_name]
                    function_args = json.loads(tool_call['function']['arguments'])
                    with st.status(f"Running function: {function_name}...", expanded=True) as status:
                        st.code(function_args.get("query"), language="sql")
                        function_response = function_to_call(**function_args)
                        st.write(f"Function output {function_response}")
                        status.update(label=f"Function {function_name} completed!", state="complete", expanded=False)


                    # Step 4: send the info for each function call and function response to the model
                    messages.append(
                        {
                            "tool_call_id": tool_call['id'],
                            "role": "tool",
                            "name": function_name,
                            "content": function_response,
                        }
                    )
                
            stream2 = client.chat.completions.create(
                                            model="gpt-4o-global",
                                            messages=messages,
                                            temperature=0,  # Adjust the variance by changing the temperature value (default is 0.8)
                                            stream=True,
                    )
            
            stream_response2 = st.write_stream(stream2)
            st.session_state.messages.append({"role": "assistant", "content": stream_response2})