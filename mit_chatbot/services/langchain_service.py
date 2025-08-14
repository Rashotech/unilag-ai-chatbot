# chatbot/services/langchain_service.py
from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from typing import Dict, List, TypedDict, Annotated, Sequence
import operator
from langchain.schema.messages import HumanMessage, AIMessage
from .typesense_service import TypesenseService
import logging
import uuid

logger = logging.getLogger(__name__)


class ConversationState(TypedDict):
    """State for the conversation graph"""
    messages: Annotated[Sequence[HumanMessage | AIMessage], operator.add]
    query: str
    conversation_id: str
    typesense_result: Dict
    final_response: str
    escalation_needed: bool
    sources: List[Dict]


class LangChainService:
    """Enhanced service using LangChain and LangGraph with Typesense RAG"""

    def __init__(self):
        self.typesense = TypesenseService()

        # Keep Gemini as backup for specific tasks
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.2
        ) if hasattr(settings, 'GOOGLE_API_KEY') else None

        # Create the conversation graph
        self.graph = self._create_conversation_graph()

    def _create_conversation_graph(self) -> StateGraph:
        """Create the LangGraph conversation flow with Typesense RAG"""

        def typesense_rag_search(state: ConversationState) -> ConversationState:
            """Use Typesense's built-in RAG for search and response generation"""
            query = state["query"]
            conversation_id = state.get("conversation_id")

            # Use Typesense conversational search (handles RAG internally)
            result = self.typesense.conversational_search(
                query=query,
                conversation_id=conversation_id
            )

            updated_conversation_id = result.get('conversation_id')

            return {
                **state,
                "conversation_id": updated_conversation_id,
                "typesense_result": result,
                "final_response": result.get('answer', 'I apologize, but I cannot provide an answer at this time.'),
                "sources": result.get('sources', [])
            }

        def post_process_response(state: ConversationState) -> ConversationState:
            """Post-process the response and check for escalation"""
            response = state["final_response"]
            query = state["query"]

            # Check for escalation scenarios
            escalation_indicators = [
                "I don't have that specific information",
                "contact the relevant department",
                "speak to human",
                "urgent",
                "emergency",
                "complaint",
                "not satisfied"
            ]

            escalation_needed = any(
                indicator in response.lower() or indicator in query.lower()
                for indicator in escalation_indicators
            )

            # Enhance response if escalation is needed
            if escalation_needed:
                enhanced_response = f"{response}\n\n*If you need immediate assistance, please contact our support team or visit the relevant department office.*"
            else:
                enhanced_response = response

            return {
                **state,
                "final_response": enhanced_response,
                "escalation_needed": escalation_needed
            }

        def fallback_response(state: ConversationState) -> ConversationState:
            """Fallback response if Typesense fails"""
            typesense_result = state.get("typesense_result", {})

            if not typesense_result.get('success', False):
                fallback_msg = """I apologize, but I'm experiencing technical difficulties right now. 

For immediate assistance, please:
- Visit the UNILAG student services office
- Check the official UNILAG website
- Contact the relevant department directly

Is there anything else I can help you with?"""

                return {
                    **state,
                    "final_response": fallback_msg,
                    "escalation_needed": True
                }

            return state

        # Create the graph
        workflow = StateGraph(ConversationState)

        # Add nodes
        workflow.add_node("typesense_rag_search", typesense_rag_search)
        workflow.add_node("post_process_response", post_process_response)
        workflow.add_node("fallback_response", fallback_response)

        # Add edges
        workflow.set_entry_point("typesense_rag_search")
        workflow.add_edge("typesense_rag_search", "fallback_response")
        workflow.add_edge("fallback_response", "post_process_response")
        workflow.add_edge("post_process_response", END)

        return workflow.compile()

    def process_conversation(
            self,
            query: str,
            conversation_id: str = None,
            user_id: str = None
    ) -> Dict:
        """Process a conversation using the LangGraph workflow with Typesense RAG"""
        try:
            # Convert query to messages
            messages = [HumanMessage(content=query)]

            # Initial state
            initial_state = {
                "messages": messages,
                "query": query,
                "conversation_id": conversation_id,
                "typesense_result": {},
                "final_response": "",
                "escalation_needed": False,
                "sources": []
            }

            # Run the graph
            final_state = self.graph.invoke(initial_state)

            return {
                'success': True,
                'response': final_state['final_response'],
                'conversation_id': final_state['conversation_id'],
                'sources': final_state['sources'],
                'escalation_needed': final_state['escalation_needed'],
                'typesense_data': final_state.get('typesense_result', {})
            }

        except Exception as e:
            logger.error(f"Error in LangChain processing: {e}")
            return {
                'success': False,
                'response': "I'm experiencing technical difficulties. Please try again later or contact support directly.",
                'conversation_id': conversation_id,
                'error': str(e),
                'escalation_needed': True
            }