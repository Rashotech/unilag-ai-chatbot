# 🎓 UNILAG AI Assistant

A comprehensive AI-powered assistant for the University of Lagos (UNILAG) that provides personalized academic support through advanced RAG (Retrieval-Augmented Generation) and MCP (Model Context Protocol) integration.

## 🌟 Features

### 🔐 Smart Authentication & Context-Aware Responses
- **Conditional Tool Usage**: MCP tools only activate for authenticated users
- **Public Information Access**: General university information available to all users
- **Personalized Responses**: Tailored answers based on student context and academic history

### 🧠 Dual Intelligence System
- **Typesense RAG**: Lightning-fast semantic search through university knowledge base
- **LLM with Tools**: Advanced reasoning with access to real-time student data
- **Smart Routing**: Automatically chooses the best approach for each query

### 🛠️ Advanced MCP Integration
- **Real-time Database Access**: Live student records, grades, and academic information
- **Course Management**: Search courses, check prerequisites, and track graduation status
- **Academic Analytics**: CGPA calculations, performance tracking, and academic planning

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   User Query    │───▶│  LangGraph       │───▶│  Final Response │
└─────────────────┘    │  Orchestrator    │    └─────────────────┘
                       └──────────────────┘
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
              ┌──────────┐ ┌────────┐ ┌────────┐
              │Typesense │ │  LLM   │ │  MCP   │
              │   RAG    │ │ Tools  │ │Service │
              └──────────┘ └────────┘ └────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- OpenAI API Key
- Typesense Server
- PostgreSQL Database

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/unilag-ai-assistant.git
cd unilag-ai-assistant

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration
```

### Environment Configuration

```env
# .env file
OPENAI_API_KEY=your_openai_api_key_here
TYPESENSE_API_KEY=your_typesense_api_key
TYPESENSE_HOST=localhost
TYPESENSE_PORT=8108

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/unilag_db
```

### Running the Application

```bash
# Create and activate a new virtual environment:
python -m venv env
source env/bin/activate

# Install the project dependencies
pip install -r requirements.txt

# Create the database tables
python manage.py migrate

#Run the development server
python manage.py runserver
```


## 🔧 Core Components

### 1. **LangGraph State Management**

```python
class ConversationState(TypedDict):
    messages: Annotated[Sequence[HumanMessage | AIMessage], operator.add]
    query: str
    conversation_id: Optional[str]
    user_context: Dict
    typesense_result: Dict
    mcp_results: List[Dict]
    final_response: str
    escalation_needed: bool
    sources: List[Dict]
    tools_used: List[str]
```

### 2. **Smart Query Routing**

The system intelligently routes queries through three main pathways:

- **🚫 Authentication Required**: Personal queries without login
- **📚 RAG-Only**: General information queries
- **🔗 RAG + Tools**: Authenticated personal queries

### 3. **MCP Tool Integration**

Available tools for authenticated users:

```python
# Student Information
get_student_profile(student_id)
get_student_results(student_id, session, semester)

# Course Management
search_courses(query, level, department_code, course_type)
check_prerequisites(course_code, student_id)

# Academic Planning
get_graduation_status(student_id)
calculate_cgpa(student_id)
```

## 📊 Query Processing Flow

```mermaid
graph TD
    A[User Query] --> B{User Authenticated?}

    B -->|No| C{Personal Query?}
    C -->|Yes| D[Request Authentication]
    C -->|No| E[Typesense RAG Only]

    B -->|Yes| F[Analyze Query Context]
    F --> G{Need Personal Data?}

    G -->|No| E
    G -->|Yes| H[RAG + MCP Tools]

    E --> I[Generate Response]
    H --> I[Generate Response]
    D --> I
    I --> J[Final Response]
```

## 🛡️ Security Features

### Authentication & Authorization
- **Cookie Auth**: Secure student authentication
- **Role-Based Access**: Different permissions for students, staff, and admin
- **Data Privacy**: Personal information only accessible to authenticated users


*Empowering students with AI-driven academic assistance*
