import streamlit as st
from backend import chatbot
from langchain_core.messages import HumanMessage,AIMessage
import uuid
# *************************************************************Utility Functions***********************************************************************

def generate_thread_id():
    thread_id = str(uuid.uuid4())
    return thread_id

def create_new_chat():
    st.session_state['thread_id'] = generate_thread_id()
    st.session_state['message_history']=[]
    st.session_state['thread_history'].append(st.session_state['thread_id'])

def load_conversation(thread_id):
    messages = chatbot.get_state(config={'configurable':{'thread_id':thread_id}}).values['messages']
    # but here the format of the messages and the message_history is different so convert messages to the type of the message_history
    temp_message_history =[]
    for message in messages:
        if isinstance(message,HumanMessage):
            role = 'user'
        else:
            role = 'assitant'
        temp_message_history.append({'role':role,'content':message.content})
    
    st.session_state['message_history'] = temp_message_history
    st.session_state['thread_id'] = thread_id

# *************************************************************Session Setup***********************************************************************

if 'message_history' not in st.session_state:
    st.session_state['message_history']=[]

if 'thread_history' not in st.session_state:
    st.session_state['thread_history']=[]

if 'thread_id' not in st.session_state:
    st.session_state['thread_id']=generate_thread_id()
    st.session_state['thread_history'].append(st.session_state['thread_id'])




# *************************************************************Sidebar UI***********************************************************************
st.sidebar.title('LangGraph Chatbot')
if st.sidebar.button('New Chat'):
    create_new_chat()
st.sidebar.header('My Conversations')

for thread_id in st.session_state['thread_history'][::-1]:
    if st.sidebar.button(label=thread_id):
        load_conversation(thread_id)

# *************************************************************Main UI***********************************************************************




user_input = st.chat_input('Type here')


# load the messages from the st.session_state['message_history']
for message in st.session_state['message_history']:
    with st.chat_message(name=message['role']):
        st.text(message['content'])


if user_input:

    st.session_state['message_history'].append({'role':'user','content':user_input})
    with st.chat_message(name='user'):
        st.text(user_input)


    CONFIG = {'configurable':{'thread_id':st.session_state['thread_id']}}
# here chatbot.stream give tuple(message_chunk,metadata) read the documentation of langgraph
    generator = chatbot.stream(input={'messages':[HumanMessage(content=user_input)]},
                               config=CONFIG,
                               stream_mode='messages')
    
    # generator function
    def message_generator():
        for message_chunk,metadata in generator:
            if message_chunk.content:
                yield message_chunk.content

    with st.chat_message(name='assistant'):
        ai_message = st.write_stream(stream=message_generator())
        st.session_state['message_history'].append({'role':'assistant','content': ai_message})

    # similar alternative for this  
    # with st.chat_message(name='assistant'):
    #     ai_message = st.write_stream(message_chunk.content for message_chunk,metadata in generator if message_chunk.content)
    #     st.session_state['message_history'].append({'role':'assistant','content':ai_message})


