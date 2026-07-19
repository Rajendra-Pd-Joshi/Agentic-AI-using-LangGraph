import os
from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import StateGraph,START,END
from langchain_openai import ChatOpenAI
from typing import TypedDict,Annotated
from langchain_core.messages import BaseMessage,HumanMessage,AIMessage
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3

class chatState(TypedDict):
    messages : Annotated[list[BaseMessage],add_messages]

llm = ChatOpenAI()
graph = StateGraph(state_schema=chatState)

def chat_node(state:chatState):
    messages = state['messages']
    response = llm.invoke(messages)
    return {'messages':[response]}

graph.add_node('chat_node',chat_node)
graph.add_edge(START,'chat_node')
graph.add_edge('chat_node',END)

conn = sqlite3.connect(
    database='chatbot.db',
    check_same_thread=False
    )
checkpointer = SqliteSaver(conn)
chatbot = graph.compile(checkpointer= checkpointer)



# function to return the list uniques thread id presents
def retrieve_all_threads():
    st = set()
    for checkpoint in checkpointer.list(None):
        st.add(checkpoint.config['configurable']['thread_id'])
    return list(st)