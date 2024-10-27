import os
from typing import Annotated, TypedDict
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage           # type: ignore
from langgraph.graph import StateGraph, START, END                                     # type: ignore
from langgraph.graph.message import add_messages                                       # type: ignore
from langchain_groq import ChatGroq                                                    # type: ignore
import tool_def as tldf

# Load LLM model and bind tools
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
llama3 = ChatGroq(api_key=GROQ_API_KEY, model="llama-3.1-70b-versatile")

class AgentState(TypedDict):
    """Defining state of nodes to be used for LAM graph"""
    messages: Annotated[list, add_messages]

class BrowserAgent:
    """Class object for custom Browser Agent"""
    def __init__(self, model, tools, system_msg=""):
        self.system = system_msg
        self.tools = {tool.name: tool for tool in tools}
        self.model = model.bind_tools(tldf.tools, tool_choice="auto")

        graph = StateGraph(AgentState)
        graph.add_node("model", self.call_llm)
        graph.add_node("tool_action", self.call_tool)
        graph.add_conditional_edges(
            "model",
            self.does_tool_exist,
            {True: "tool_action", False: END}
        )
        graph.add_edge("tool_action", "model")
        graph.add_edge(START, "model")
        # memory = MemorySaver()
        self.graph = graph.compile()

    def does_tool_exist(self, state: AgentState):
        """Checks whether relevant tool exists or not."""
        result = state['messages'][-1]
        return len(result.tool_calls) > 0
    
    def call_llm(self, state: AgentState):
        """Invokes LLM with custom prompt if any."""
        messages = state['messages']
        if self.system:
            messages = [SystemMessage(content=self.system)] + messages
        ai_message = self.model.invoke(messages)
        return {'messages': ai_message}
    
    def call_tool(self, state: AgentState):
        """Uses existing tools and appends to message state for model to interpret."""
        tool_calls = state['messages'][-1].tool_calls
        results = []
        for t in tool_calls:
            print(t['name'])
            if not t['name'] in self.tools:
                print(f"Tool with name: {t['name']} not found in arsenal.")
                result = "Alas! Tool not found. Please try again with different tools."
            else:
                result = self.tools[t['name']].invoke(t['args'])
            results.append(ToolMessage(tool_call_id=t['id'], name=t['name'], content=str(result)))
            return {'messages': results}

# Can add additional system prompt if required          
# system_prompt = """
#     You are a smart web browsing agent capable of browsing websites on your own
#     Use the custom tools at your disposal to complete the tasks
# """

# Define custom RAG agent
react_agent = BrowserAgent(llama3, tldf.tools)

# Test Results
messages = [HumanMessage(content="""
    Log in to https://availity-clone.vercel.app/ using the following credentials:
        - Email: demo@availity.com
        - Password: password123
    Find and click Patient Registration button and Eligibility link on next page
    Fill the eligibility form on next page and use the following data:
        - Organization: Select an option similar to "Organization A" from the dropdown
        - Payer: Select an option similar to "Payer X" from the dropdown
        - Provider ID: Select an option similar to "ID123" from the dropdown
        - Provider NPI: Enter "NPI456" in the text field
        - Provider Tax ID#: Enter "000000000" in the text field
        - Provider Type: Select an option similar to "Provider Type 1" from the dropdown
        - Provider Last Name: Select an option similar to "Williams" from the dropdown
        - Provider First Name: Select an option similar to "Jane" from the dropdown
        - Provider Address Line 1: Select an option similar to "789 Oak St" from the dropdown
        - Provider Address Line 2: Enter "Suite 201" in the text field
        - Provider Zip Code: Select an option similar to "90001" from the dropdown
    """)]
result = react_agent.graph.invoke({"messages": messages})
