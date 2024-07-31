from my_memgpt import memgraph
from langchain_core.runnables.config import RunnableConfig
from my_memgpt._schemas import GraphConfig
import asyncio
conf = GraphConfig(model="openai/gpt-4o", thread_id='1', user_id='2')

config = RunnableConfig(
    configurable={
        "thread_id":'1',
        "user_id":"user1"
    }
)

class Chat:
    def __init__(self, user_id: str, thread_id: str):
        self.thread_id = thread_id
        self.user_id = user_id

    async def __call__(self, query: str) -> str:
        res = await memgraph.ainvoke(
            input={
                "messages": [("user", query)],
            },
            config={
                "configurable": {
                    "user_id": self.user_id,
                    "thread_id": self.thread_id,
                }
            },
        )
        return res



if __name__ == "__main__":
    chat = Chat('1', '2')
    inp = input()
    while inp != '':
        print(asyncio.run(chat(inp)))
        inp = input()