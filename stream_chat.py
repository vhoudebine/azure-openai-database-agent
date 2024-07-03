import asyncio
from dotenv import load_dotenv
import os 
from openai import AzureOpenAI, AsyncAzureOpenAI
import pandas as pd
from typing import Any, Tuple
from typing import Tuple
import json
import pyodbc
from sqlalchemy import create_engine
import urllib


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

client = AsyncAzureOpenAI(
    azure_endpoint=endpoint,
    api_key=api_key,
    api_version='2024-02-01'
)

deployment_name ='gpt-4o-global'

def query_azure_sql(query: str) -> str:
    """Run a SQL query on Azure SQL and return results as a pandas DataFrame"""
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
        }
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

def get_user_input() -> str:
    try:
        user_input = input("\nUser:> ")
    except KeyboardInterrupt:
        print("\n\nExiting chat...")
        return ""
    except EOFError:
        print("\n\nExiting chat...")
        return ""

    # Handle exit command
    if user_input == "exit":
        print("\n\nExiting chat...")
        return ""

    return user_input

async def chat(messages) -> Tuple[Any, bool]:
    # User's input
    user_input = get_user_input()
    if not user_input:
        return False
    messages.append({"role": "user", "content": user_input})

    # Step 1: send the conversation and available functions to the model
    stream_response = await client.chat.completions.create(
        model=deployment_name,
        messages=messages,
        temperature=0,  # Adjust the variance by changing the temperature value (default is 0.8)
        stream=True,
        tools=get_tools(),
        tool_choice="auto"
    )

    print("Assistant:> ", end="")
    tool_calls=[] # accumulator for tool calls to process later
    full_delta_content = "" # Accumulator for the full assistant's content


    async for chunk in stream_response:
        delta = chunk.choices[0].delta if chunk.choices and chunk.choices[0].delta is not None else None

        if delta and delta.content:
            full_delta_content += delta.content
            await asyncio.sleep(0.1)
            print(delta.content, end="", flush=True)

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
                if function_name not in available_functions:
                    return "Function " + function_name + " does not exist"
            
                # Step 3: call the function with arguments if any
                function_to_call = available_functions[function_name]
                function_args = json.loads(tool_call['function']['arguments'])
                function_response = function_to_call(**function_args)

                # Step 4: send the info for each function call and function response to the model
                messages.append(
                    {
                        "tool_call_id": tool_call['id'],
                        "role": "tool",
                        "name": function_name,
                        "content": function_response,
                    }
                )  # extend conversation with function response

                stream_response2 = await client.chat.completions.create(
                model=deployment_name,
                messages=messages,
                temperature=0,  # Adjust the variance by changing the temperature value (default is 0.8)
                stream=True,
            )
        async def print_stream_chunks(stream):
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content is not None:
                    print(chunk.choices[0].delta.content, end="", flush=True)
                    await asyncio.sleep(0.1)

        await print_stream_chunks(stream_response2)

        print("")
        return True
            


    messages.append({ "role": "assistant", "content": full_delta_content })
    return True

messages = init_messages()


async def main() -> None:

    chatting = True
    while chatting:
        chatting = await chat(messages)

if __name__ == "__main__":
    asyncio.run(main())