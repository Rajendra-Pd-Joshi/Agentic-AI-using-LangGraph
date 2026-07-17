import os
from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import StateGraph,START,END
from langchain_openai import ChatOpenAI
from typing import TypedDict,Annotated
from langchain_core.messages import BaseMessage,HumanMessage,AIMessage
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver

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

checkpointer = InMemorySaver()
chatbot = graph.compile(checkpointer= checkpointer)

chatbot.invoke(input={
    'messages':[HumanMessage(content='what is the capital of nepal?')]
},config = {'configurable':{'thread_id':1}})

print(chatbot.get_state(config={'configurable':{'thread_id':1}}).values['messages'])