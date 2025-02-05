
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple
import asyncio

from langchain_postgres.vectorstores import _get_embedding_collection_store
from typing import List, Optional, Dict, Any, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import Column, String, JSON
import uuid
from pgvector.sqlalchemy import Vector
import langsmith
import tiktoken
from langchain.chat_models import init_chat_model
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages.utils import get_buffer_string
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import (
    RunnableConfig,
    ensure_config,
    get_executor_for_config,
)
from langchain_core.tools import tool
from langchain_core.documents import Document
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from typing_extensions import Literal
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os
from my_memgpt import _constants as constants
from my_memgpt import _schemas as schemas
from my_memgpt import _settings as settings
from my_memgpt import _utils as utils

logger = logging.getLogger('memory')

_EMPTY_VEC = [0.0] * 768

os.environ['LANGCHAIN_TRACING_V2'] = settings.SETTINGS.langchain_tracing_v2
os.environ['LANGCHAIN_ENDPOINT'] = settings.SETTINGS.langchain_endpoint
os.environ['LANGCHAIN_API_KEY'] = settings.SETTINGS.langchain_api_key
os.environ["LANGCHAIN_PROJECT"] = settings.SETTINGS.langchain_project
os.environ["TAVILY_API_KEY"] = settings.SETTINGS.tavily_api_key
os.environ["OPENAI_API_KEY"] = settings.SETTINGS.openai_api_key
os.environ["OPENAI_API_BASE"] = settings.SETTINGS.openai_base_provider
search_tool = TavilySearchResults(max_results=1)
tools = [search_tool]

@tool
async def save_recall_memory(memory: str) -> str:
    """Save a memory to the database for later semantic retrieval.

    Args:
        memory (str): The memory to be saved.

    Returns:
        str: The saved memory.
    """
    config = ensure_config()
    configurable = utils.ensure_configurable(config)
    current_time = datetime.now(tz=timezone.utc)
    path = constants.INSERT_PATH.format(
        user_id=configurable["user_id"],
        event_id=str(uuid.uuid4()),
    )
    docs = [
        Document(
            page_content=memory,
            metadata={
                "id":path,
                constants.PATH_KEY: path,
                constants.TYPE_KEY: "recall",
                "user_id": configurable["user_id"],
            }
        )
    ]
    await utils.get_vectorstore().aadd_documents(
        docs,
        ids=[doc.metadata['id'] for doc in docs]
    )
    return memory


@tool
async def search_memory(query: str, top_k: int = 5) -> list[str]:
    """Search for memories in the database based on semantic similarity.

    Args:
        query (str): The search query.
        top_k (int): The number of results to return.

    Returns:
        list[str]: A list of relevant memories.
    """
    config = ensure_config()
    configurable = utils.ensure_configurable(config)
    with langsmith.trace("query", inputs={"query": query, "top_k": top_k}) as rt:
        response = await utils.get_vectorstore().asimilarity_search(
            query=query,
            k=top_k, 
            filter={
                "user_id":{"$eq":configurable['user_id']},
                constants.TYPE_KEY: {"$eq": "recall"}
            }
        )
        rt.end(outputs={"response": response})
    memories = [doc.page_content for doc in response]
    return memories



@langsmith.traceable
def fetch_core_memories(user_id: str) -> Tuple[str, list[str]]:
    """Fetch core memories for a specific user.

    Args:
        user_id (str): The ID of the user.

    Returns:
        Tuple[str, list[str]]: The path and list of core memories.
    """
    path = constants.PATCH_PATH.format(user_id=user_id)
    response = utils.get_index().fetch(
        ids=[path], namespace=settings.SETTINGS.pinecone_namespace
    )
    memories = []
    if vectors := response.get("vectors"):
        document = vectors[path]
        payload = document["metadata"][constants.PAYLOAD_KEY]
        memories = json.loads(payload)["memories"]
    return path, memories

async def fetch_rows_by_id(session: AsyncSession, path: str) -> Sequence[Any]:
    EmbeddingStore, CollectionStore = _get_embedding_collection_store()
    results = None
    try:
        stmt = (
            select(EmbeddingStore)
            .where(EmbeddingStore.id == path)
        )

        results: Optional[Sequence[Any]] = (await session.execute(stmt)).scalars().one_or_none()
    except:
        pass
    if results is None:
        return None
    return results

@langsmith.traceable
async def fetch_core_memories(user_id: str) -> Tuple[str, list[str]]:
    """Fetch core memories for a specific user.

    Args:
        user_id (str): The ID of the user.

    Returns:
        Tuple[str, list[str]]: The path and list of core memories.
    """
    path = constants.PATCH_PATH.format(user_id=user_id)
    engine = create_async_engine(settings.SETTINGS.pg_connection, echo=True)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        response = await fetch_rows_by_id(session, path)
    if response is None:
        return path, []
    memories = response.cmetadata[constants.PAYLOAD_KEY]
    return path, memories


@tool
async def store_core_memory(memory: str, index: Optional[int] = None) -> str:
    """Store a core memory in the database.

    Args:
        memory (str): The memory to store.
        index (Optional[int]): The index at which to store the memory.

    Returns:
        str: A confirmation message.
    """
    config = ensure_config()
    configurable = utils.ensure_configurable(config)
    path, memories = await fetch_core_memories(configurable["user_id"])
    if index is not None:
        if index < 0 or index >= len(memories):
            return "Error: Index out of bounds."
        memories[index] = memory
    else:
        memories.insert(0, memory)
    await utils.get_vectorstore().aadd_embeddings(
        texts=[''],
        embeddings=[_EMPTY_VEC],
        metadatas=[{
            constants.PAYLOAD_KEY:memories,
            constants.PATH_KEY:path,
            constants.TYPE_KEY: "core",
            "user_id": configurable["user_id"]
        }],
        ids=[path]
    )
    return "Memory stored."

# Combine all tools
all_tools = tools + [save_recall_memory, search_memory, store_core_memory]


# Define the prompt template for the agent
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant with advanced long-term memory"
            " capabilities. Powered by a stateless LLM, you must rely on"
            " external memory to store information between conversations."
            " Utilize the available memory tools to store and retrieve"
            " important details that will help you better attend to the user's"
            " needs and understand their context.\n\n"
            "Memory Usage Guidelines:\n"
            "1. Actively use memory tools (save_core_memory, save_recall_memory)"
            " to build a comprehensive understanding of the user.\n"
            "2. Make informed suppositions and extrapolations based on stored"
            " memories.\n"
            "3. Regularly reflect on past interactions to identify patterns and"
            " preferences.\n"
            "4. Update your mental model of the user with each new piece of"
            " information.\n"
            "5. Cross-reference new information with existing memories for"
            " consistency.\n"
            "6. Prioritize storing emotional context and personal values"
            " alongside facts.\n"
            "7. Use memory to anticipate needs and tailor responses to the"
            " user's style.\n"
            "8. Recognize and acknowledge changes in the user's situation or"
            " perspectives over time.\n"
            "9. Leverage memories to provide personalized examples and"
            " analogies.\n"
            "10. Recall past challenges or successes to inform current"
            " problem-solving.\n\n"
            "## Core Memories\n"
            "Core memories are fundamental to understanding the user and are"
            " always available:\n{core_memories}\n\n"
            "## Recall Memories\n"
            "Recall memories are contextually retrieved based on the current"
            " conversation:\n{recall_memories}\n\n"
            "## Instructions\n"
            "Engage with the user naturally, as a trusted colleague or friend."
            " There's no need to explicitly mention your memory capabilities."
            " Instead, seamlessly incorporate your understanding of the user"
            " into your responses. Be attentive to subtle cues and underlying"
            " emotions. Adapt your communication style to match the user's"
            " preferences and current emotional state. Use tools to persist"
            " information you want to retain in the next conversation. If you"
            " do call tools, all text preceding the tool call is an internal"
            " message. Respond AFTER calling the tool, once you have"
            " confirmation that the tool completed successfully.\n\n"
            "Current system time: {current_time}\n\n",
        ),
        ("placeholder", "{messages}"),
    ]
)


async def agent(state: schemas.State, config: RunnableConfig) -> schemas.State:
    """Process the current state and generate a response using the LLM.

    Args:
        state (schemas.State): The current state of the conversation.
        config (RunnableConfig): The runtime configuration for the agent.

    Returns:
        schemas.State: The updated state with the agent's response.
    """
    configurable = utils.ensure_configurable(config)
    llm = init_chat_model(configurable["model"], model_provider=settings.SETTINGS.model_provider)
    bound = prompt | llm.bind_tools(all_tools)
    core_str = (
        "<core_memory>\n" + "\n".join(state["core_memories"]) + "\n</core_memory>"
    )
    recall_str = (
        "<recall_memory>\n" + "\n".join(state["recall_memories"]) + "\n</recall_memory>"
    )
    prediction = await bound.ainvoke(
        {
            "messages": state["messages"],
            "core_memories": core_str,
            "recall_memories": recall_str,
            "current_time": datetime.now(tz=timezone.utc).isoformat(),
        }
    )
    return {
        "messages": prediction,
    }


async def load_memories(state: schemas.State, config: RunnableConfig) -> schemas.State:
    """Load core and recall memories for the current conversation.

    Args:
        state (schemas.State): The current state of the conversation.
        config (RunnableConfig): The runtime configuration for the agent.

    Returns:
        schemas.State: The updated state with loaded memories.
    """
    configurable = utils.ensure_configurable(config)
    user_id = configurable["user_id"]
    tokenizer = tiktoken.encoding_for_model("gpt-4o")
    convo_str = get_buffer_string(state["messages"])
    convo_str = tokenizer.decode(tokenizer.encode(convo_str)[:2048])
    futures = [
        await fetch_core_memories(user_id),
        await search_memory.ainvoke(convo_str),
    ]
    _, core_memories = futures[0]
    recall_memories = futures[1]
    return {
        "core_memories": core_memories,
        "recall_memories": recall_memories,
    }


def route_tools(state: schemas.State) -> Literal["tools", "__end__"]:
    """Determine whether to use tools or end the conversation based on the last message.

    Args:
        state (schemas.State): The current state of the conversation.

    Returns:
        Literal["tools", "__end__"]: The next step in the graph.
    """
    msg = state["messages"][-1]
    if msg.tool_calls:
        return "tools"
    return END


# Create the graph and add nodes
builder = StateGraph(schemas.State, schemas.GraphConfig)
builder.add_node(load_memories)
builder.add_node(agent)
builder.add_node("tools", ToolNode(all_tools))

# Add edges to the graph
builder.add_edge(START, "load_memories")
builder.add_edge("load_memories", "agent")
builder.add_conditional_edges("agent", route_tools)
builder.add_edge("tools", "agent")

# Compile the graph
memgraph = builder.compile()

__all__ = ["memgraph"]
