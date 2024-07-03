import asyncio

from dotenv import load_dotenv
import os 
from openai import AzureOpenAI
import pandas as pd

load_dotenv()

endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
api_key = os.getenv('AZURE_OPENAI_API_KEY')

client = AzureOpenAI(
    azure_endpoint=endpoint,
    api_key=api_key,
    api_version='2024-02-01'
)

deployment_name ='gpt-4o-global'

def run_conversation():
    stream = client.chat.completions.create(
            model='gpt-4o-global',
            messages=[
                {'role': 'user', 'content': "If Paris wasn't the capital of France, what city would be and why?"}
            ],
            stream=True,
            temperature=0 # this time, we set stream=True
        )


    async def print_stream_chunks(stream):
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                print(chunk.choices[0].delta.content, end="", flush=True)
                await asyncio.sleep(0.1)

    asyncio.run(print_stream_chunks(stream))

result = run_conversation()
