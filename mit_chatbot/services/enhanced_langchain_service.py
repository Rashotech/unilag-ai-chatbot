import json
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, TypedDict, Annotated, Sequence, Optional
import operator

from langchain_core.tools import StructuredTool
from langgraph.graph import StateGraph, END
from langchain.schema.messages import HumanMessage, AIMessage
from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model

from .typesense_service import TypesenseService
from .mcp_service import MCPDatabaseService

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
    user_context: Dict
    is_authenticated: bool
    typesense_result: Annotated[Dict, lambda x, y: y if y else x]  # Take latest non-empty
    mcp_results: Annotated[List[Dict], operator.add]  # Accumulate results
    final_response: str
    escalation_needed: bool
    sources: Annotated[List[Dict], operator.add]  # Accumulate sources
    tools_used: Annotated[List[str], operator.add]  # Accumulate tools
    needs_tools: bool
    needs_rag: bool


class EnhancedLangChainService:
    """Enhanced LangChain service with MCP database integration"""

    def __init__(self):
        self.typesense = TypesenseService()
        self.mcp = MCPDatabaseService()
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.llm_base = init_chat_model("gpt-5-mini", model_provider="openai")

        self.authenticated_prompt = """
        You are UNILAG Assistant with access to real-time student data through MCP

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
        6. Combine database results with knowledge base information

        When you have access to student data, provide personalized, specific guidance
        rather than general information.
        """


        # System prompts
        self.authenticated_prompt2 = """
        You are UNILAG Assistant with access to real-time student data through MCP.

        CAPABILITIES:
        - Access to student profiles, academic records, and course information
        - Personalized responses based on student's current status
        - Integration with university database and knowledge base

        GUIDELINES:
        1. Use student's personal data for personalized responses
        2. Combine database results with knowledge base information
        3. Maintain confidentiality - only share information with authenticated student
        4. Be specific and actionable based on student's current status
        """

        self.unauthenticated_prompt = """
        You are UNILAG Assistant, providing general university information.

        CAPABILITIES:
        - Access to general university knowledge base
        - Can provide information about courses, programs, and policies
        - Cannot access personal student data

        GUIDELINES:
        1. Provide helpful general information
        2. Suggest logging in for personalized assistance when relevant
        3. Use knowledge base to answer general queries
        """

        # Initialize graph after setting up components
        self.graph = self._create_enhanced_conversation_graph()

    def _create_enhanced_conversation_graph(self) -> StateGraph:
        """Create enhanced conversation flow with conditional MCP integration"""

        def analyze_query(state: ConversationState) -> ConversationState:
            """Analyze query to determine what resources are needed"""
            query = state["query"]
            user_context = state.get("user_context", {})
            is_authenticated = user_context.get("authenticated", False) and user_context.get("student_id")

            # Determine if tools are needed (only for authenticated users)
            needs_tools = False
            if is_authenticated:
                # Check for personal/specific queries that need database access
                personal_indicators = [
                    "my", "i", "me", "my cgpa", "my results", "my courses",
                    "can i take", "am i eligible", "my profile", "my grades",
                    "my level", "my department", "my status"
                ]
                needs_tools = any(indicator in query.lower() for indicator in personal_indicators)

                # Also check for course-specific queries
                course_indicators = ["prerequisite", "can take", "eligible for", "requirements for"]
                if any(indicator in query.lower() for indicator in course_indicators):
                    needs_tools = True

            # Always use RAG for general information
            needs_rag = True

            if is_authenticated and needs_tools and needs_rag:
                logger.info("🚀 Query eligible for parallel execution")

            return {
                **state,
                "is_authenticated": is_authenticated,
                "needs_tools": needs_tools,
                "needs_rag": needs_rag
            }

        def typesense_rag_search(state: ConversationState) -> ConversationState:
            """Use Typesense RAG search for general university information"""
            if not state.get("needs_rag", True):
                return state

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

        def execute_tools(state: ConversationState) -> ConversationState:
            """Execute MCP tools for authenticated users"""
            if not state.get("needs_tools", False) or not state.get("is_authenticated", False):
                return state

            user_context = state.get("user_context", {})
            student_id = user_context.get("student_id")

            if not student_id:
                return state

            # Create tools specific to this user
            tools = self.create_mcp_tools()
            llm_with_tools = self.llm_base.bind_tools(self.create_mcp_tools())

            # Build messages
            messages = [
                HumanMessage(content=self.authenticated_prompt),
                HumanMessage(content=f"Student Context: {json.dumps(user_context)}"),
                HumanMessage(content=state["query"])
            ]

            try:
                # Get tool calls from LLM
                response = llm_with_tools.invoke(messages)

                tools_used = []
                mcp_results = []

                if response.tool_calls:
                    for tool_call in response.tool_calls:
                        tool_name = tool_call['name']
                        tool_args = tool_call['args']
                        tools_used.append(tool_name)

                        # Execute tool
                        for tool in tools:
                            if tool.name == tool_name:
                                try:
                                    result = tool.func(**tool_args)
                                    mcp_results.append({
                                        "tool": tool_name,
                                        "args": tool_args,
                                        "result": json.loads(result) if isinstance(result, str) else result
                                    })
                                except Exception as e:
                                    logger.error(f"Tool execution error: {e}")
                                    mcp_results.append({
                                        "tool": tool_name,
                                        "args": tool_args,
                                        "result": {"success": False, "error": str(e)}
                                    })
                                break

                return {
                    **state,
                    "tools_used": tools_used,
                    "mcp_results": mcp_results
                }

            except Exception as e:
                logger.error(f"Error in tool execution: {e}")
                return state

        def synthesize_response(state: ConversationState) -> ConversationState:
            """Synthesize final response from all available data"""
            is_authenticated = state.get("is_authenticated", False)
            mcp_results = state.get("mcp_results", [])
            typesense_result = state.get("typesense_result", {})
            user_context = state.get("user_context", {})

            # Choose appropriate system prompt
            system_prompt = self.authenticated_prompt if is_authenticated else self.unauthenticated_prompt

            # Build context
            context_parts = []

            # Add user context if authenticated
            if is_authenticated and user_context.get("student_id"):
                context_parts.append(f"""
                Student Information:
                - Name: {user_context.get('name', 'N/A')}
                - Student ID: {user_context['student_id']}
                - Department: {user_context.get('department', 'N/A')}
                - Level: {user_context.get('current_level', 'N/A')}
                - CGPA: {user_context.get('cgpa', 'N/A')}
                """)

            # Add MCP results if available
            if mcp_results:
                context_parts.append("DATABASE RESULTS:")
                for result in mcp_results:
                    if result["result"].get("success"):
                        context_parts.append(f"{result['tool']}: {json.dumps(result['result']['data'], indent=2)}")

            # Add RAG results
            if typesense_result.get("success") and typesense_result.get("answer"):
                context_parts.append(f"KNOWLEDGE BASE:\n{typesense_result['answer']}")

            # Generate final response
            try:
                messages = [
                    HumanMessage(content=system_prompt),
                    HumanMessage(content="\n\n".join(context_parts)),
                    HumanMessage(content=f"User Query: {state['query']}\n\nProvide a comprehensive response:")
                ]

                response = self.llm_base.invoke(messages)
                final_response = response.content

            except Exception as e:
                logger.error(f"Error generating response: {e}")
                final_response = self._create_fallback_response(state)

            return {
                **state,
                "final_response": final_response,
                "escalation_needed": False
            }

        def check_escalation(state: ConversationState) -> ConversationState:
            """Check if human escalation is needed"""
            response = state.get("final_response", "")
            mcp_results = state.get("mcp_results", [])

            # This list should now only contain strings.
            escalation_indicators = [
                "I don't have access",
                "contact the",
                "speak to",
                "visit the"
            ]

            escalation_needed = (
                # Condition 1: Check if any of the indicator strings are in the response.
                    any(indicator in response.lower() for indicator in escalation_indicators) or

                    # Condition 2: Check if the response is too short (moved from the list).
                    len(response) < 50 or

                    # Condition 3: Check if any tool execution failed.
                    any(not r["result"].get("success", True) for r in mcp_results)
            )

            return {
                **state,
                "escalation_needed": escalation_needed
            }

        def route_after_analysis(state: ConversationState) -> str:
            """Route based on authentication and query needs"""
            is_authenticated = state.get("is_authenticated", False)
            needs_tools = state.get("needs_tools", False)
            needs_rag = state.get("needs_rag", True)

            if is_authenticated and needs_tools and needs_rag:
                return "parallel_execution"  # ← CHANGE THIS LINE
            elif needs_tools and is_authenticated:
                return "execute_tools"
            elif needs_rag:
                return "typesense_search"
            else:
                return "synthesize_response"

        def parallel_execution(state: ConversationState) -> ConversationState:
            """Execute MCP tools and RAG search in parallel"""
            logger.info("🚀 Executing MCP tools and RAG search in parallel")

            # Use existing functions in parallel
            with ThreadPoolExecutor(max_workers=2) as executor:
                # Submit both tasks
                mcp_future = executor.submit(execute_tools, state)
                rag_future = executor.submit(typesense_rag_search, state)

                try:
                    # Get results (with timeout protection)
                    mcp_state = mcp_future.result(timeout=100)
                    rag_state = rag_future.result(timeout=100)

                    # Merge results into state
                    state['mcp_results'] = mcp_state.get('mcp_results', [])
                    state['typesense_result'] = rag_state.get('typesense_result', {})
                    state['tools_used'].extend(mcp_state.get('tools_used', []))
                    state['sources'].extend(rag_state.get('sources', []))

                except Exception as e:
                    logger.error(f"Parallel execution error: {e}")
                    # Fallback to sequential if parallel fails
                    state =execute_tools(state)
                    state = typesense_rag_search(state)

            return state

        def route_after_tools(state: ConversationState) -> str:
            """Route after tool execution"""
            needs_rag = state.get("needs_rag", True)
            if needs_rag:
                return "typesense_search"
            else:
                return "synthesize"

        # Build the graph
        graph = StateGraph(ConversationState)

        # Add nodes (ADD this one line)
        graph.add_node("analyze_query", analyze_query)
        graph.add_node("execute_tools", execute_tools)
        graph.add_node("typesense_search", typesense_rag_search)
        graph.add_node("parallel_execution", parallel_execution)  # ← ADD THIS
        graph.add_node("synthesize_response", synthesize_response)
        graph.add_node("check_escalation", check_escalation)

        # Set entry point
        graph.set_entry_point("analyze_query")

        # Routing (ADD parallel_execution to the mapping)
        graph.add_conditional_edges(
            "analyze_query",
            route_after_analysis,
            {
                "execute_tools": "execute_tools",
                "typesense_search": "typesense_search",
                "parallel_execution": "parallel_execution",  # ← ADD THIS LINE
                "synthesize_response": "synthesize_response"
            }
        )

        # Edges (ADD this one line)
        graph.add_edge("execute_tools", "synthesize_response")
        graph.add_edge("typesense_search", "synthesize_response")
        graph.add_edge("parallel_execution", "synthesize_response")  # ← ADD THIS
        graph.add_edge("synthesize_response", "check_escalation")
        graph.add_edge("check_escalation", END)

        return graph.compile()

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

    def _create_fallback_response(self, state: ConversationState) -> str:
        """Create fallback response when LLM fails"""
        typesense_result = state.get("typesense_result", {})
        mcp_results = state.get("mcp_results", [])

        if typesense_result.get("success") and typesense_result.get("answer"):
            return typesense_result["answer"]
        elif mcp_results:
            parts = ["Here's what I found:\n"]
            for result in mcp_results:
                if result["result"].get("success"):
                    parts.append(f"- {result['tool']}: {json.dumps(result['result']['data'])}")
            return "\n".join(parts)
        else:
            return "I'm having trouble processing your request. Please try rephrasing or contact support."

    def process_query(
            self,
            query: str,
            conversation_id: Optional[str] = None,
            user_context: Optional[Dict] = None
    ) -> Dict:
        """Process query with authentication-aware pipeline"""
        try:
            # Initialize state
            initial_state = ConversationState(
                messages=[HumanMessage(content=query)],
                query=query,
                conversation_id=conversation_id,
                user_context=user_context or {},
                is_authenticated=False,
                typesense_result={},
                mcp_results=[],
                final_response="",
                escalation_needed=False,
                sources=[],
                tools_used=[],
                needs_tools=False,
                needs_rag=True
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
                'mcp_data': final_state.get('mcp_results', []),
                'authenticated': final_state.get('is_authenticated', False)
            }

        except Exception as e:
            logger.error(f"Error in query processing: {e}")
            logging.error("An error occurred:", exc_info=True)

            # Alternatively, get the formatted stack trace as a string
            stack_trace_string = traceback.format_exc()
            logging.error(f"Error with traceback:\n{stack_trace_string}")
            return {
                'success': False,
                'response': "I'm experiencing technical difficulties. Please try again.",
                'conversation_id': conversation_id,
                'error': str(e),
                'escalation_needed': True
            }