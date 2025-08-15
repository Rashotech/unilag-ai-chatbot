import json

from langchain_core.tools import StructuredTool
from langgraph.graph import StateGraph, END
from typing import Dict, List, TypedDict, Annotated, Sequence, Optional
import operator
from langchain.schema.messages import HumanMessage, AIMessage
from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model

from .typesense_service import TypesenseService
from .mcp_service import MCPDatabaseService
import logging

logger = logging.getLogger(__name__)


class SearchCoursesInput(BaseModel):
    query: str = Field(None,
                       description="Specific search terms for course code, title, or subject keywords. Extract meaningful terms only, not full user questions. Examples: 'programming', 'CSC101', 'calculus'")
    level: int = Field(None,
                       description="Course level as integer (100, 200, 300, 400, 500). Extract from phrases like '200 level', '300l', 'second year'")
    department_code: str = Field(None,
                                 description="Department code (CSC, PHY, MTH, CHM, etc). Extract from department names or codes mentioned")
    course_type: str = Field(None, description="Course type like 'CORE', 'ELECTIVE', 'REQUIRED' if specified")


class GetStudentProfileInput(BaseModel):
    student_id: str = Field(description="Student ID from user context")


class GetStudentResultsInput(BaseModel):
    student_id: str = Field(description="Student ID from user context")
    session: str = Field(None, description="Specific session/year if mentioned")
    semester: str = Field(None, description="Specific semester if mentioned")


class CheckPrerequisitesInput(BaseModel):
    course_code: str = Field(description="Course code to check prerequisites for")
    student_id: str = Field(None, description="Student ID if checking for specific student")


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
        self.tools = self.create_mcp_tools()
        self.llm = init_chat_model("gpt-5-mini", model_provider="openai").bind_tools(self.tools)

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
            user_context = state.get("user_context", {})
            if user_context.get("student_id"):
                context_msg = f"""
                    User Context:
                    - Student ID: {user_context['student_id']}
                    - Name: {user_context.get('name', 'N/A')}
                    - Department: {user_context.get('department', 'N/A')}
                    - Current Level: {user_context.get('current_level', 'N/A')}
                    - CGPA: {user_context.get('cgpa', 'N/A')}
                    """
                context_parts.append(f"Student Context: {context_msg}")

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

        def generate_response_with_tools(state: ConversationState) -> ConversationState:
            """Generate response with automatic tool calling and results processing"""
            from langchain.schema.messages import HumanMessage, AIMessage, ToolMessage

            # Build message history
            messages = [HumanMessage(content=self.system_prompt)]

            # Add user context
            user_context = state.get("user_context", {})
            if user_context.get("student_id"):
                context_msg = f"""
                User Context:
                - Student ID: {user_context['student_id']}
                - Name: {user_context.get('name', 'N/A')}
                - Department: {user_context.get('department', 'N/A')}
                - Current Level: {user_context.get('current_level', 'N/A')}
                - CGPA: {user_context.get('cgpa', 'N/A')}
                """
                messages.append(HumanMessage(content=f"Context: {context_msg}"))

            # Add user query
            messages.append(HumanMessage(content=state["query"]))

            try:
                # Step 1: LLM decides which tools to call
                response = self.llm.invoke(messages)
                messages.append(response)

                tools_used = []
                mcp_results = []

                # Step 2: Execute tool calls and collect results
                if response.tool_calls:
                    for tool_call in response.tool_calls:
                        tool_name = tool_call['name']
                        tool_args = tool_call['args']
                        tools_used.append(tool_name)

                        # Find and execute the tool
                        tool_result = None
                        for tool in self.tools:
                            if tool.name == tool_name:
                                try:
                                    tool_result = tool.func(**tool_args)
                                    mcp_results.append({
                                        "tool": tool_name,
                                        "args": tool_args,
                                        "result": tool_result
                                    })
                                except Exception as e:
                                    tool_result = {"success": False, "error": str(e)}
                                break

                        # Add tool result to conversation
                        if tool_result:
                            messages.append(ToolMessage(
                                content=str(tool_result),
                                tool_call_id=tool_call['id']
                            ))

                    # Step 3: LLM generates final response using tool results
                    final_response = self.llm.invoke(messages)
                    final_answer = final_response.content

                else:
                    # No tools needed, use original response
                    final_answer = response.content

                return {
                    **state,
                    "final_response": final_answer,
                    "tools_used": tools_used,
                    "mcp_results": mcp_results,
                    "escalation_needed": False
                }

            except Exception as e:
                logger.error(f"Error in tool calling: {e}")
                return {
                    **state,
                    "final_response": f"I encountered an error while processing your request: {str(e)}",
                    "escalation_needed": True,
                    "tools_used": [],
                    "mcp_results": []
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
        # graph.add_node("typesense_search", typesense_rag_search)
        graph.add_node("synthesize", generate_response_with_tools)
        graph.add_node("check_escalation", check_escalation)

        # Define the flow
        graph.add_edge("analyze_query", "synthesize")
        # graph.add_edge("typesense_search", "synthesize")
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

    # Create the tools
    def create_mcp_tools(self):
        """Create LangChain tools that wrap MCP service calls"""

        def search_courses_wrapper(query: str = None, level: int = None,
                                   department_code: str = None, course_type: str = None) -> str:
            """Search for university courses"""
            try:
                params = {}
                if query: params['query'] = query
                if level: params['level'] = level
                if department_code: params['department_code'] = department_code
                if course_type: params['course_type'] = course_type

                result = self.mcp.execute_tool("search_courses", params)
                return json.dumps(result)
            except Exception as e:
                return f"Error searching courses: {str(e)}"

        def get_student_profile_wrapper(student_id: str) -> str:
            """Get student profile information"""
            try:
                result = self.mcp.execute_tool("get_student_profile", {"student_id": student_id})
                return json.dumps(result)
            except Exception as e:
                return f"Error getting student profile: {str(e)}"

        def get_student_results_wrapper(student_id: str, session: str = None, semester: str = None) -> str:
            """Get student academic results"""
            try:
                params = {"student_id": student_id}
                if session: params['session'] = session
                if semester: params['semester'] = semester

                result = self.mcp.execute_tool("get_student_results", params)
                return json.dumps(result)
            except Exception as e:
                return f"Error getting student results: {str(e)}"

        def check_prerequisites_wrapper(course_code: str, student_id: str = None) -> str:
            """Check course prerequisites"""
            try:
                params = {"course_code": course_code}
                if student_id: params['student_id'] = student_id

                result = self.mcp.execute_tool("check_prerequisites", params)
                return json.dumps(result)
            except Exception as e:
                return f"Error checking prerequisites: {str(e)}"

        return [
            StructuredTool.from_function(
                func=search_courses_wrapper,
                name="search_courses",
                description="Search for university courses with filters. Use this when users ask about courses, subjects, or specific course codes.",
                args_schema=SearchCoursesInput
            ),
            StructuredTool.from_function(
                func=get_student_profile_wrapper,
                name="get_student_profile",
                description="Get student profile information. Use when users ask about their profile, details, or personal information.",
                args_schema=GetStudentProfileInput
            ),
            StructuredTool.from_function(
                func=get_student_results_wrapper,
                name="get_student_results",
                description="Get student academic results and grades. Use when users ask about their results, grades, or performance.",
                args_schema=GetStudentResultsInput
            ),
            StructuredTool.from_function(
                func=check_prerequisites_wrapper,
                name="check_prerequisites",
                description="Check course prerequisites and eligibility. Use when users ask if they can take a course or about requirements.",
                args_schema=CheckPrerequisitesInput
            )
            # Add more tools as needed...
        ]


