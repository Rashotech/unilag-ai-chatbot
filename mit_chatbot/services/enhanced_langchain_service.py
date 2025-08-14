import json
import re

from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from typing import Dict, List, TypedDict, Annotated, Sequence, Optional
import operator
from langchain.schema.messages import HumanMessage, AIMessage
from .typesense_service import TypesenseService
from .mcp_service import MCPDatabaseService
import logging

logger = logging.getLogger(__name__)


class ConversationState(TypedDict):
    """Enhanced state for the conversation graph with MCP support"""
    messages: Annotated[Sequence[HumanMessage | AIMessage], operator.add]
    query: str
    conversation_id: Optional[str]
    user_context: Dict  # Student info, session context, etc.
    typesense_result: Dict
    mcp_results: List[Dict]  # Results from MCP tools
    final_response: str
    escalation_needed: bool
    sources: List[Dict]
    tools_used: List[str]
    tools_needed: List[str]


class EnhancedLangChainService:
    """Enhanced LangChain service with MCP database integration"""

    def __init__(self):
        self.typesense = TypesenseService()
        self.mcp = MCPDatabaseService()

        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.2
        ) if hasattr(settings, 'GOOGLE_API_KEY') else None

        self.graph = self._create_enhanced_conversation_graph()

        # System prompt for MCP-aware responses
        self.system_prompt = """
        You are UNILAG Assistant, the official AI helper for University of Lagos students, staff, and prospective applicants.

        ENHANCED CAPABILITIES:
        - Access to real-time student data through MCP (Model Context Protocol)
        - Integration with university database for personalized responses
        - Can retrieve student profiles, academic records, course information, and more
        - Web search capabilities for current university information

        MCP TOOLS AVAILABLE:
        - get_student_profile: Get student personal and academic information
        - get_student_results: Get academic results and grades
        - get_student_cgpa: Get CGPA and academic performance
        - get_course_info: Get detailed course information
        - check_prerequisites: Check course prerequisites
        - get_graduation_status: Check graduation eligibility
        - get_academic_calendar: Get current session/semester info
        - search_courses: Search for specific courses

        RESPONSE GUIDELINES:
        1. Always use student's personal data when available for personalized responses
        2. Combine MCP database results with RAG knowledge base information
        3. Provide specific, actionable information based on student's current status
        4. Maintain confidentiality - only share information with the authenticated student
        5. Use official UNILAG terminology and procedures
        6. Cite sources clearly (database vs. knowledge base vs. web search)

        When you have access to student data, provide personalized, specific guidance
        rather than general information.
        """

    def _create_enhanced_conversation_graph(self) -> StateGraph:
        """Create enhanced conversation flow with MCP integration"""

        def analyze_query_and_context(state: ConversationState) -> ConversationState:
            """Analyze query to determine if MCP tools are needed"""
            query = state["query"].lower()
            user_context = state.get("user_context", {})

            # Determine which MCP tools might be needed based on query content
            needed_tools = []

            # Student-specific queries
            if any(keyword in query for keyword in ["my result", "my grade", "my cgpa", "my gpa", "my performance"]):
                needed_tools.extend(["get_student_results", "get_student_cgpa"])

            if any(keyword in query for keyword in ["my profile", "my details", "my information", "my data"]):
                needed_tools.append("get_student_profile")

            if any(keyword in query for keyword in ["my courses", "registered courses", "course registration"]):
                needed_tools.append("get_student_courses")

            if any(keyword in query for keyword in ["can i take", "prerequisite", "eligible for"]):
                # Extract course code from query if possible
                course_match = re.search(r'\b[A-Z]{2,4}\s*\d{3}\b', query.upper())
                if course_match:
                    needed_tools.append("check_prerequisites")

            if any(keyword in query for keyword in ["graduation", "graduate", "degree", "final year"]):
                needed_tools.append("get_graduation_status")

            if any(keyword in query for keyword in ["semester", "session", "calendar", "deadline"]):
                needed_tools.append("get_academic_calendar")

            # Course information queries
            course_match = re.search(r'\b[A-Z]{2,4}\s*\d{3}\b', query.upper())
            if course_match or any(keyword in query for keyword in ["course", "subject", "unit"]):
                if course_match:
                    needed_tools.append("get_course_info")
                else:
                    needed_tools.append("search_courses")

            return {
                **state,
                "tools_needed": needed_tools,
                "mcp_results": []
            }

        def execute_mcp_tools(state: ConversationState) -> ConversationState:
            """Execute necessary MCP tools to get database information"""
            tools_needed = state.get("tools_needed", [])
            user_context = state.get("user_context", {})
            query = state["query"]
            mcp_results = []
            tools_used = []

            student_id = user_context.get("student_id")

            try:
                for tool in tools_needed:
                    if tool == "get_student_profile" and student_id:
                        result = self.mcp.execute_tool("get_student_profile", {"student_id": student_id})
                        mcp_results.append({"tool": tool, "result": result})
                        tools_used.append(tool)

                    elif tool == "get_student_results" and student_id:
                        result = self.mcp.execute_tool("get_student_results", {"student_id": student_id})
                        mcp_results.append({"tool": tool, "result": result})
                        tools_used.append(tool)

                    elif tool == "get_student_cgpa" and student_id:
                        result = self.mcp.execute_tool("get_student_cgpa", {"student_id": student_id})
                        mcp_results.append({"tool": tool, "result": result})
                        tools_used.append(tool)

                    elif tool == "get_student_courses" and student_id:
                        result = self.mcp.execute_tool("get_student_courses", {"student_id": student_id})
                        mcp_results.append({"tool": tool, "result": result})
                        tools_used.append(tool)

                    elif tool == "check_prerequisites" and student_id:
                        # Extract course code from query
                        course_match = re.search(r'\b[A-Z]{2,4}\s*\d{3}\b', query.upper())
                        if course_match:
                            course_code = course_match.group().replace(" ", "")
                            result = self.mcp.execute_tool("check_prerequisites", {
                                "student_id": student_id,
                                "course_code": course_code
                            })
                            mcp_results.append({"tool": tool, "result": result})
                            tools_used.append(tool)

                    elif tool == "get_graduation_status" and student_id:
                        result = self.mcp.execute_tool("get_graduation_status", {"student_id": student_id})
                        mcp_results.append({"tool": tool, "result": result})
                        tools_used.append(tool)

                    elif tool == "get_academic_calendar":
                        result = self.mcp.execute_tool("get_academic_calendar", {})
                        mcp_results.append({"tool": tool, "result": result})
                        tools_used.append(tool)

                    elif tool == "get_course_info":
                        course_match = re.search(r'\b[A-Z]{2,4}\s*\d{3}\b', query.upper())
                        if course_match:
                            course_code = course_match.group().replace(" ", "")
                            result = self.mcp.execute_tool("get_course_info", {"course_code": course_code})
                            mcp_results.append({"tool": tool, "result": result})
                            tools_used.append(tool)

                    elif tool == "search_courses":
                        # Extract search terms
                        search_terms = query.replace("course", "").replace("subject", "").strip()
                        result = self.mcp.execute_tool("search_courses", {"query": search_terms})
                        mcp_results.append({"tool": tool, "result": result})
                        tools_used.append(tool)

            except Exception as e:
                logger.error(f"Error executing MCP tools: {e}")
                mcp_results.append({
                    "tool": "error",
                    "result": {"success": False, "error": str(e)}
                })

            return {
                **state,
                "mcp_results": mcp_results,
                "tools_used": tools_used
            }

        def typesense_rag_search(state: ConversationState) -> ConversationState:
            """Use Typesense RAG search for general university information"""
            query = state["query"]
            conversation_id = state.get("conversation_id")

            try:
                result = self.typesense.conversational_search(
                    query=query,
                    conversation_id=conversation_id
                )

                return {
                    **state,
                    "typesense_result": result,
                    "conversation_id": result.get('conversation_id', conversation_id),
                    "sources": result.get('sources', [])
                }
            except Exception as e:
                logger.error(f"Error in Typesense search: {e}")
                return {
                    **state,
                    "typesense_result": {"success": False, "error": str(e)},
                    "sources": []
                }

        def synthesize_response(state: ConversationState) -> ConversationState:
            """Combine MCP results with RAG information to create comprehensive response"""
            mcp_results = state.get("mcp_results", [])
            typesense_result = state.get("typesense_result", {})
            user_context = state.get("user_context", {})
            tools_used = state.get("tools_used", [])

            # Prepare context for LLM
            context_parts = []

            # Add student context
            if user_context.get("student_id"):
                context_parts.append(f"Student Context: Responding to student {user_context['student_id']}")

            # Add MCP results
            if mcp_results:
                context_parts.append("DATABASE INFORMATION:")
                for mcp_result in mcp_results:
                    if mcp_result["result"].get("success"):
                        context_parts.append(
                            f"{mcp_result['tool']}: {json.dumps(mcp_result['result']['data'], indent=2)}")
                    else:
                        context_parts.append(
                            f"{mcp_result['tool']}: Error - {mcp_result['result'].get('error', 'Unknown error')}")

            # Add RAG results
            if typesense_result.get("success"):
                rag_answer = typesense_result.get("answer", "")
                if rag_answer:
                    context_parts.append(f"KNOWLEDGE BASE INFORMATION:\n{rag_answer}")

            # Create prompt for LLM
            if self.llm and context_parts:
                try:
                    full_context = "\n\n".join(context_parts)
                    prompt = f"""
                            {self.system_prompt}

                            CONTEXT INFORMATION:
                            {full_context}

                            USER QUERY: {state['query']}

                            INSTRUCTIONS:
                            1. Provide a comprehensive, personalized response using the database information when available
                            2. If you have student-specific data, prioritize that in your response
                            3. Combine database results with knowledge base information for complete answers
                            4. Be specific and actionable in your guidance
                            5. Maintain a helpful, professional tone
                            6. If information is missing or unclear, explain what additional details might be needed

                            Respond as UNILAG Assistant:
                            """

                    response = self.llm.invoke(prompt)
                    final_response = response.content

                except Exception as e:
                    logger.error(f"Error generating LLM response: {e}")
                    final_response = self._create_fallback_response(state)
            else:
                final_response = self._create_fallback_response(state)

            return {
                **state,
                "final_response": final_response,
                "escalation_needed": False
            }

        def check_escalation(state: ConversationState) -> ConversationState:
            """Check if the query requires human escalation"""
            response = state["final_response"]
            mcp_results = state.get("mcp_results", [])

            # Check for escalation indicators
            escalation_needed = any([
                "I don't have access" in response,
                "contact the" in response.lower(),
                "speak to" in response.lower(),
                any(not result["result"].get("success", True) for result in mcp_results),
                len(response) < 50,  # Very short responses might indicate issues
            ])

            return {
                **state,
                "escalation_needed": escalation_needed
            }

            # Build the graph

        graph = StateGraph(ConversationState)

        # Add nodes
        graph.add_node("analyze_query", analyze_query_and_context)
        graph.add_node("execute_mcp", execute_mcp_tools)
        graph.add_node("typesense_search", typesense_rag_search)
        graph.add_node("synthesize", synthesize_response)
        graph.add_node("check_escalation", check_escalation)

        # Define the flow
        graph.add_edge("analyze_query", "execute_mcp")
        graph.add_edge("execute_mcp", "typesense_search")
        graph.add_edge("typesense_search", "synthesize")
        graph.add_edge("synthesize", "check_escalation")
        graph.add_edge("check_escalation", END)

        # Set entry point
        graph.set_entry_point("analyze_query")

        return graph.compile()

    def _create_fallback_response(self, state: ConversationState) -> str:
        """Create fallback response when LLM is not available"""
        mcp_results = state.get("mcp_results", [])
        typesense_result = state.get("typesense_result", {})

        if mcp_results:
            # Use MCP data to create basic response
            response_parts = ["Here's the information I found:\n"]

            for mcp_result in mcp_results:
                if mcp_result["result"].get("success"):
                    tool_name = mcp_result["tool"].replace("_", " ").title()
                    data = mcp_result["result"]["data"]
                    response_parts.append(f"{tool_name}: {self._format_mcp_data(data)}")

            return "\n\n".join(response_parts)

        elif typesense_result.get("success"):
            return typesense_result.get("answer",
                                        "I found some relevant information, but couldn't process it properly.")

        else:
            return "I'm experiencing technical difficulties. Please try rephrasing your question or contact support directly."

    def _format_mcp_data(self, data: Dict) -> str:
        """Format MCP data for display"""
        if not data:
            return "No data available"

        # Handle different data types
        if isinstance(data, dict):
            if "student_id" in data and "full_name" in data:
                # Student profile
                return f"Student: {data['full_name']} ({data['student_id']}), CGPA: {data.get('current_cgpa', 'N/A')}"
            elif "current_cgpa" in data:
                # CGPA info
                return f"Current CGPA: {data['current_cgpa']}, Class: {data.get('class_of_degree', 'N/A')}"
            elif "eligible_for_graduation" in data:
                # Graduation status
                return f"Graduation Status: {'Eligible' if data['eligible_for_graduation'] else 'Not Eligible'}"
            else:
                return str(data)

        return str(data)

    def process_query(
            self,
            query: str,
            conversation_id: Optional[str] = None,
            user_context: Optional[Dict] = None
    ) -> Dict:
        """Process query with enhanced MCP and RAG capabilities"""
        try:
            initial_state = ConversationState(
                messages=[HumanMessage(content=query)],
                query=query,
                conversation_id=conversation_id,
                user_context=user_context or {},
                typesense_result={},
                mcp_results=[],
                final_response="",
                escalation_needed=False,
                sources=[],
                tools_used=[]
            )

            # Execute the graph
            final_state = self.graph.invoke(initial_state)

            return {
                'success': True,
                'response': final_state.get('final_response'),
                'conversation_id': final_state.get('conversation_id'),
                'escalation_needed': final_state.get('escalation_needed', False),
                'tools_used': final_state.get('tools_used', []),
                'sources': final_state.get('sources', []),
                'mcp_data': final_state.get('mcp_results', [])
            }

        except Exception as e:
            logger.error(f"Error in enhanced LangChain processing: {e}")
            return {
                'success': False,
                'response': "I'm experiencing technical difficulties. Please try again later.",
                'conversation_id': conversation_id,
                'error': str(e),
                'escalation_needed': True
            }

    def get_student_context(self, user) -> Dict:
        """Extract student context from authenticated user"""
        try:
            if not user or not user.is_authenticated:
                return {'authenticated': False, 'user_type': 'anonymous'}

            context = {
                'authenticated': True,
                'user_id': user.id,
                'name': user.get_full_name(),
                'email': user.email,
                'user_type': user.user_type
            }

            # Add student context if user is a student
            if hasattr(user, 'student_profile'):
                student = user.student_profile
                context.update({
                    'student_id': student.student_id,
                    'department': student.department.name,
                    'faculty': student.department.faculty.name,
                    'current_level': student.current_level,
                    'cgpa': float(student.current_cgpa) if student.current_cgpa else 0.0,
                    'entry_year': student.entry_session.name if student.entry_session else None,
                    'status': student.status,
                    "student_type": student.student_type
                })

            return context
        except Exception as e:
            print(e)
            return {'is_authenticated': False}


