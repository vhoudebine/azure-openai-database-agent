from dotenv import load_dotenv
import os 
from openai import AzureOpenAI
import pandas as pd
import streamlit as st
import pyodbc, struct
from sqlalchemy import create_engine
from audiorecorder import audiorecorder
import urllib
import json
import io
import matplotlib.pyplot as plt
import numpy as np
import time
from azure.identity import DefaultAzureCredential



load_dotenv()

endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
api_key = os.getenv('AZURE_OPENAI_API_KEY')
deployment = os.getenv('AZURE_OPENAI_GPT_MODEL_DEPLOYMENT')
speech_deployment = os.getenv('AZURE_OPENAI_WHISPER_MODEL')
server = os.getenv('AZURE_SQL_SERVER') 
database = os.getenv('AZURE_SQL_DB_NAME')
username = os.getenv('AZURE_SQL_USER') 
password = os.getenv('AZURE_SQL_PASSWORD')

#connection_string = f'Driver={{ODBC Driver 18 for SQL Server}};Server=tcp:{server},1433;Database={database};Uid={username};Pwd={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'
connection_string = f'Driver={{ODBC Driver 18 for SQL Server}};Server=tcp:{server},1433;Database={database};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'

def get_conn():
    credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
    token_bytes = credential.get_token("https://database.windows.net/.default").token.encode("UTF-16-LE")
    token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
    SQL_COPT_SS_ACCESS_TOKEN = 1256  # This connection option is defined by microsoft in msodbcsql.h
    conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
    return conn

engine_azure = get_conn()

def agent_query_validator(query: str) -> str:
    """Check that a SQL query is valid"""
    global client
    prompt ="""Double check the user's SQL Server query for common mistakes, including:
- Using LIMIT instead of TOP
- Using NOT IN with NULL values
- Using UNION when UNION ALL should have been used
- Using BETWEEN for exclusive ranges
- Data type mismatch in predicates
- Properly quoting identifiers
- Using the correct number of arguments for functions
- Casting to the correct data type
- Using the proper columns for joins

If there are any of the above mistakes, rewrite the query. If there are no mistakes, just reproduce the original query.

Output the final SQL query only."""
    
    messages = [{"role":"system", "content":prompt},
                          {"role":"user", "content":f" here's the query: {query}"}]
    try:
        response = client.chat.completions.create(
                model=st.session_state["openai_model"],
                messages=messages
            )
        return json.dumps(response.choices[0].message.content)
    except Exception as e:
        print(e)

def convert_datetime_columns_to_string(df: pd.DataFrame) -> pd.DataFrame:
    """Convert any datetime and timestamp columns in a DataFrame to strings."""
    for column in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[column]):
            df[column] = df[column].astype(str)
    return df

def list_database_tables() -> str:
    """List tables in the Azure SQL database"""
    query = "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'"
    print(f"Executing query on Azure SQL: {query}")
    df = pd.read_sql(query, engine_azure)
    return json.dumps(df.to_dict(orient='records'))

def query_azure_sql(query: str) -> str:
    """Run a SQL query on Azure SQL and return results as a pandas DataFrame"""
    print(f"Executing query on Azure SQL: {query}")
    df = pd.read_sql(query, engine_azure)
    df = convert_datetime_columns_to_string(df)
    return json.dumps(df.to_dict(orient='records'))

def get_table_schema(table_name: str) -> str:
    """Get the schema of a table in Azure SQL"""
    query = f"SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{table_name}'"
    print(f"Executing query on Azure SQL: {query}")
    df = pd.read_sql(query, engine_azure)
    return json.dumps(df.to_dict(orient='records'))

def get_table_rows(table_name: str) -> str:
    """Get the first 3 rows of a table in Azure SQL"""
    query = f"SELECT TOP 3 * FROM {table_name}"
    print(f"Executing query on Azure SQL: {query}")
    df = pd.read_sql(query, engine_azure)
    df = convert_datetime_columns_to_string(df)
    return df.to_markdown()

def get_column_values(table_name: str, column_name: str) -> str:
    """Get the unique values of a column in a table in Azure SQL"""
    query = f"SELECT DISTINCT TOP 50 {column_name} FROM {table_name} ORDER BY {column_name}"
    print(f"Executing query on Azure SQL: {query}")
    df = pd.read_sql(query, engine_azure)
    df = convert_datetime_columns_to_string(df)
    return json.dumps(df.to_dict(orient='records'))

def plot_data(data: str) -> str:
    # Convert the data string to a dictionary
    data = json.loads(data)
    # Convert the dictionary to a pandas DataFrame
    df = pd.DataFrame(data)
        
    # Convert the timestamp column to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
        
    # Set the timestamp column as the index
    df.set_index('timestamp', inplace=True)
        
    # Plot the data series using a line chart
    df.plot(kind='line')
        
    # Create the tmp folder if it doesn't exist
    if not os.path.exists('tmp'):
        os.makedirs('tmp')
        
    # Save the plot image in the tmp folder
    plt.savefig('tmp/plot.png')
        
    return "![Image: plot](tmp/plot.png)"

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
        {
            "type": "function",
            "function": {
                "name": "get_table_rows",
                "description": "Preview the first 5 rows of a table in Azure SQL",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "The name of the table to get the preview for",
                        },
                    },
                    "required": ["table_name"],
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_column_values",
                "description": "Get the unique values of a column in a table in Azure SQL, only use this if the main query has a WHERE clause",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "The name of the table to get the column values for",
                        },
                        "column_name": {
                            "type": "string",
                            "description": "The name of the column to get the values for",
                        },
                    },
                    "required": ["table_name", "column_name"],
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "agent_query_validator",
                "description": "Validate a SQL query for common mistakes, always call this before calling query_azure_sql",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The SQL query to validate",
                        }
                    },
                    "required": ["query"],
                },
            }
        },
        {"type": "function",
            "function":{
                "name": "plot_data",
                "description": "plot one or multiple timeseries of data points as a line chart, returns a mardown string",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": """A JSON string containing the different data series and timestamp axis with the following format:
                            {"timestamp": ["2022-01-01", "2022-01-02", "2022-01-03"],
                            "series1": [10, 20, 30],
                            "series2": [15, 25, 35]}
                            """,
                        },
                    },
                    "required": ["data"],
                },
            }
        }

    ]

def get_available_functions():
    return {
        "query_azure_sql":query_azure_sql, 
        "get_table_schema":get_table_schema,
        "get_table_rows":get_table_rows,
        "get_column_values":get_column_values,
        "agent_query_validator":agent_query_validator,
        "plot_data":plot_data
        }

@st.cache_data
def init_system_prompt():
    return [
    {"role":"system", "content":f"""You are a helpful AI data analyst assistant, 
     You can execute SQL queries to retrieve information from a sql database,
     The database is SQL server, use the right syntax to generate queries


     ### These are the available tables in the database:
    {list_database_tables()}

     When asked a question that could be answered with a SQL query: 
     - ALWAYS look up the schema of the table
     - ALWAYS preview the first 3 rows
     - ONLY IF YOU NEED TO USE WHERE CLAUSE TO FILTER ROWS, make sure to look up the unique values of the column, don't assume the filter values
     - ALWAYS validate the query for common mistakes before executing it
     - Only once this is done, create a sql query to retrieve the information based on your understanding of the table

    DO NOT RETURN ANY OF THE FUNCTION OUTPUTS IN YOUR RESPONSE
 
    Think step by step, before doing anything, share the different steps you'll execute to get the answer
    When you get to a final answer use the following structure to provide the answer:
    <RESPONSE>: Your final answer to the question

    DO not use LIMIT in your generated SQL, instead use the TOP() function as follows:
    
    question: "Show me the first 5 rows of the sales_data table"
    query: SELECT TOP 5 * FROM sales_data  

    
     """}
]

#    Think step by step, before doing anything, share the different steps you'll execute to get the answer


def reset_conversation():
  st.session_state.messages = []

client = AzureOpenAI(
    azure_endpoint=endpoint,
    api_key=api_key,
    api_version='2024-02-01'
)

st.set_page_config(page_title="Azure SQL Agent")
st.title("Chat with Azure SQL")

st.info("This is a simple chat app to demo how to create a database agent powered by Azure OpenAI and capable of interacting with Azure SQL", icon="📃")


st.button('Clear Chat History 🔄', on_click=reset_conversation)


# Set a default model
if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = deployment

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []


system_prompt = init_system_prompt()

def get_message_history():
    return system_prompt+st.session_state.messages
            


def process_stream(stream):
    # Empty container to display the assistant's reply
    assistant_reply_box = st.empty()
    
    # A blank string to store the assistant's reply
    assistant_reply = ""

    # Iterate through the stream
    tool_calls = []
    for event in stream:
        # Here, we only consider if there's a delta text
        delta = event.choices[0].delta if event.choices and event.choices[0].delta is not None else None
        if delta and delta.content:
            # empty the container
            assistant_reply_box.empty()
            # add the new text
            assistant_reply += delta.content
                # display the new text
            assistant_reply_box.markdown(assistant_reply)
            

        elif delta and delta.tool_calls:
            tc_chunk_list = delta.tool_calls
            for tc_chunk in tc_chunk_list:
                if len(tool_calls) <= tc_chunk.index:
                    tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})

                tc = tool_calls[tc_chunk.index]
                if tc_chunk.id:
                    tc["id"] += tc_chunk.id
                if tc_chunk.function.name:
                    tc["function"]["name"] += tc_chunk.function.name
                if tc_chunk.function.arguments:
                    tc["function"]["arguments"] += tc_chunk.function.arguments    
    
    if assistant_reply!="":
        st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
    if tool_calls:
        st.session_state.messages.append({"role": "assistant", "tool_calls": tool_calls})
        available_functions = get_available_functions()

        for tool_call in tool_calls:
            # Note: the JSON response may not always be valid; be sure to handle errors
            function_name = tool_call['function']['name']

            # Step 3: call the function with arguments if any
            function_to_call = available_functions[function_name]
            function_args = json.loads(tool_call['function']['arguments'])
            with st.status(f"Running function: {function_name}...", expanded=True) as status:
                
                if function_args.get("query"):
                    status.code(function_args.get("query"), language="sql")
                else:
                    status.write(f"Function arguments: {function_args}")
                function_response = function_to_call(**function_args)
                status.write(f"Function outputs: {function_response}")
                status.update(label=f"Function {function_name} completed!", state="complete", expanded=False)


            st.session_state.messages.append(
                {
                    "tool_call_id": tool_call['id'],
                    "role": "tool",
                    "name": function_name,
                    "content": function_response,
                }
            )
        return True
    else:
        if "![Image: plot](tmp/plot.png)" in assistant_reply:
            assistant_reply = assistant_reply.replace("![Image: plot](tmp/plot.png)", "")
            assistant_reply_box.empty()
            assistant_reply_box.markdown(assistant_reply)
            st.image("tmp/plot.png")
            st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
        
        return False

def speech_to_text(audio_file):
    result = client.audio.transcriptions.create(
        model=speech_deployment,
        file=open(audio_file, "rb"),
    )
    return result
    
    

messages = st.container(height=400, border=False)
# Display chat messages from history on app rerun
for message in st.session_state.messages:
    if message["role"] in ["user", "assistant"] and 'content' in message:
        with messages.chat_message(message["role"]):
            st.markdown(message["content"])
# Display chat input
prompt=st.chat_input("Ask me anything...")

audio = audiorecorder(start_prompt="", stop_prompt="", pause_prompt="", show_visualizer=False, key=None)

if 'audio' not in st.session_state:
    st.session_state['audio'] = []

new_audio = False
if len(audio)>0:
    audio_buffer = io.BytesIO()
    audio.export(audio_buffer, format="wav", parameters=["-ar", str(16000)])
    audio_array = np.frombuffer(audio_buffer.getvalue()[44:], dtype=np.int16).astype(np.float32) / 32768.0
    
    if str(st.session_state.audio) != str(audio_array):
        print('new audio')
        st.session_state.audio = audio_array
        new_audio = True
        if not os.path.exists("./tmp"):
            os.makedirs("./tmp")
        audio.export("./tmp/audio.wav", format="wav", parameters=["-ar", str(16000)])


with messages:
# Accept user input
    if new_audio:
        with st.spinner('Transcribing audio...'):
            transcription = speech_to_text("./tmp/audio.wav")
            print(transcription)
            prompt = transcription.text
    if prompt:
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        # Display user message in chat message container
        with messages.chat_message("user"):
            st.markdown(prompt)

    # Display assistant response in chat message container
        with st.chat_message("assistant"):
            has_more = True
            while has_more:
                stream = client.chat.completions.create(
                model=st.session_state["openai_model"],
                messages=get_message_history(),
                stream=True,
                tools = get_tools(),
                tool_choice="auto"
            )
                has_more = process_stream(stream)