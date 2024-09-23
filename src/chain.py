import streamlit as st
from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase
import mysql.connector
from mysql.connector import Error
import os
from langchain_core.messages import AIMessage,HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.chat_models import ChatOllama
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
load_dotenv()
######-------------------------------Get All Databases------------------------################
def get_database_names(host: str, user: str, password: str, port: str):
    try:
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            port=port
        )
        
        if connection.is_connected():
            cursor = connection.cursor()
            cursor.execute("SHOW DATABASES")  
            databases = cursor.fetchall()
            return [db[0] for db in databases]  # Return a list of database names
            
    except Error as e:
        st.error(f"❌ Error fetching databases: {str(e)}")
        return []
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'connection' in locals() and connection.is_connected():
            connection.close()

##################----------------------------------Start & Use the Database-------------------####################
def start_database(user: str, password: str, host: str, port: str, database: str) -> SQLDatabase:
    try:
        db_url = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}"
        db = SQLDatabase.from_uri(db_url)
        st.success("✅ Database connection successful!")
        return db
    except Exception as e:
        st.error(f"❌ Error connecting to the database: {str(e)}")
        return None

def get_sqlchain(db):
    template = """
    You are a data analyst at a company. You are interacting with a user who is asking you questions about the company's database.
    Based on the table schema below, write a SQL query that would answer the user's question. Take the conversation history into account.
    
    <SCHEMA>{schema}</SCHEMA>
    
    Conversation History: {chat_history}
    
    Write only the SQL query and nothing else. Do not wrap the SQL query in any other text, not even backticks.
    
    For example:
    Question: which 3 artists have the most tracks?
    SQL Query: SELECT ArtistId, COUNT(*) as track_count FROM Track GROUP BY ArtistId ORDER BY track_count DESC LIMIT 3;
    Question: Name 10 artists
    SQL Query: SELECT Name FROM Artist LIMIT 10;
    
    Your turn:
    
    Question: {question}
    SQL Query:
    """
    prompt = ChatPromptTemplate.from_template(template) #Prompt
    llm = ChatOllama(model="llama3.1:8b") #LLm Model
    # Toolkit/Tool
    def get_schema(_):
        return db.get_table_info()
    # Create Chains
    return (
    RunnablePassthrough.assign(schema=get_schema)
    | prompt
    | llm
    | StrOutputParser()
  )
def get_response(user_query :str,db:SQLDatabase,chat_history:list): # Pass sql query in this and get natural language resppnse
    sql_chain=get_sqlchain(db)
    template = """
    You are a data analyst at a company. You are interacting with a user who is asking you questions about the company's database.
    Based on the table schema below, question, sql query, and sql response, write a natural language response.
    <SCHEMA>{schema}</SCHEMA>

    Conversation History: {chat_history}
    SQL Query: <SQL>{query}</SQL>
    User question: {question}
    SQL Response: {response}"""
  
    prompt = ChatPromptTemplate.from_template(template)
    llm = ChatOllama(model="llama3.1:8b")
    chain=(RunnablePassthrough.assign(query=sql_chain).assign(schema=lambda _:db.get_table_info(),
                                                             response=lambda vars: db.run(vars["query"]),
                                                             )
                                                             | prompt
                                                             | llm
                                                             | StrOutputParser()
            )
    return chain.invoke({
    "question": user_query,
    "chat_history": chat_history,
  })
           
    
####---------Initializse Chat History
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [AIMessage(content="Hello! I am Data Analyst.Aske me anything about your database"),]
    
 #####################--------------Side Bar Design   
st.set_page_config(page_title="Chat with Your Database", page_icon="💬")
st.title("💬 Chat with Your Database")


with st.sidebar:
    st.subheader("⚙️ Settings")
    st.write("A simple Agnetic Application to chat with your database. Connect to your database and start chatting.")

    host = st.text_input("🌐 Host", value=os.getenv("DB_HOST", "localhost"), key="Host")
    user = st.text_input("👤 User", value=os.getenv("DB_USER", "root"), key="User")
    port = st.text_input("🔌 Port", value=os.getenv("DB_PORT", "3306"), key="Port")
    password = st.text_input("🔑 Password", type="password", value=os.getenv("DB_PASSWORD", ""), key="Password")

    if "database" not in st.session_state:
        st.session_state["database"] = None

    if st.button("📋 Fetch Databases"):
        databases = get_database_names(host, user, password, port)
        if databases:
            st.session_state["databases"] = databases  
            st.session_state["database"] = st.selectbox("💾 Select Database", databases, key="database_select")
        else:
            st.session_state["databases"] = []

    if st.button("🔗 Connect to Database"):
        if st.session_state["database"] is None:
            st.warning("⚠️ Please select a database")
        else:
            db = start_database(user, password, host, port, st.session_state["database"])
            if db:
                st.session_state["db"] = db

if "db" in st.session_state:
    st.success("🎉 You are connected to the database!")
    for i in st.session_state.chat_history:
        if isinstance(i,AIMessage):
            with st.chat_message("AI"):
                st.markdown(i.content)
        elif isinstance(i, HumanMessage):
            with st.chat_message("Human"):
                st.write(i.content)
            
    user_query=st.chat_input("Type a message...")
    if user_query is not None and user_query.strip() != "":
        st.session_state.chat_history.append(HumanMessage(content=user_query)) # Takes User query in Chat history
        with st.chat_message("Human"):
            st.markdown(user_query)  ## Show user query
        with st.chat_message("AI"):
            with st.spinner("⏳ Generating response..."):
                response=get_response(user_query,st.session_state.db,st.session_state.chat_history)
                print(f"Response will Give SQL Query: {response}")
                st.markdown(response) 
        st.session_state.chat_history.append(AIMessage(content=user_query))  # Take AI Response in Chat History
            
    

else:
    st.info("ℹ️ Please connect to a database to start chatting.")
