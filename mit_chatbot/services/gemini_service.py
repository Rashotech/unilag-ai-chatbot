import google.generativeai as genai
from typing import Dict, List, Optional
from django.conf import settings


class GeminiService2:
    """Service for Google Gemini API operations"""

    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.0-flash')

        # System prompt for university chatbot
        self.system_prompt = """
        You are a helpful university student support assistant for University of Lagos. 
        Your role is to provide accurate, helpful, and polite responses to student queries 
        about academic policies, procedures, registration, grades, and general university information.

        Guidelines:
        1. Always be polite and professional
        2. Provide clear, concise answers
        3. Use only the provided context to answer questions
        4. If you cannot answer based on the context, politely say so and suggest contacting the appropriate department
        5. Include relevant policy numbers or section references when available
        6. For complex procedures, provide step-by-step guidance
        7. Encourage students to verify important information with official sources

        If the context doesn't contain sufficient information, respond with:
        "I don't have enough information in my knowledge base to fully answer your question. 
        Please contact [appropriate department] at [contact info if available] for accurate information."
        """

    def generate_response(self, query: str, context: List[Dict],
                          conversation_history: Optional[List[Dict]] = None) -> Dict:
        """Generate response using Gemini with context"""
        try:
            # Prepare context string
            context_str = self._format_context(context)

            # Prepare conversation history
            history_str = self._format_history(conversation_history) if conversation_history else ""

            # Create the full prompt
            full_prompt = f"""
            {self.system_prompt}

            Context from university documents:
            {context_str}

            {history_str}

            Student Question: {query}

            Please provide a helpful answer based on the context above:
            """

            # Generate response
            response = self.model.generate_content(full_prompt)

            return {
                'success': True,
                'response': response.text.strip(),
                'model': 'gemini-2.5-flash',
                'context_used': len(context)
            }

        except Exception as e:
            print(f"Error generating response with Gemini: {e}")
            return {
                'success': False,
                'response': "I'm experiencing technical difficulties. Please try again later or contact student support directly.",
                'error': str(e)
            }

    def _format_context(self, context: List[Dict]) -> str:
        """Format context documents for the prompt with relevance scores"""
        if not context:
            return "No relevant documents found."

        formatted_context = []
        for i, doc in enumerate(context, 1):
            score = doc.get('score', 0)
            formatted_context.append(f"""
            Document {i} (Relevance: {score:.2f}): {doc.get('title', 'Unknown Title')}
            Type: {doc.get('document_type', 'Unknown')}
            Content: {doc.get('content', '')[:1200]}
            """)

        return "\n".join(formatted_context)
    
    def _filter_relevant_context(self, query: str, context: List[Dict]) -> List[Dict]:
        """Filter context to only include highly relevant documents"""
        if not context:
            return []
            
        # Sort by relevance score and take top results
        sorted_context = sorted(context, key=lambda x: x.get('score', 0), reverse=True)
        
        # Only include documents with reasonable relevance
        relevant_docs = [doc for doc in sorted_context if doc.get('score', 0) > 0.2]
        
        return relevant_docs[:8]  # Limit to top 8 most relevant
    
    def _assess_context_quality(self, query: str, context: List[Dict]) -> Dict:
        """Assess the quality of retrieved context for the query"""
        if not context:
            return {
                'score': 0,
                'instruction': 'No relevant context found. Acknowledge the query and provide specific guidance on who to contact.'
            }
        
        avg_score = sum(doc.get('score', 0) for doc in context) / len(context)
        max_score = max(doc.get('score', 0) for doc in context)
        
        if max_score > 0.7 and avg_score > 0.5:
            return {
                'score': 9,
                'instruction': 'High quality context available. Provide comprehensive answer using the context.'
            }
        elif max_score > 0.5 and avg_score > 0.3:
            return {
                'score': 6,
                'instruction': 'Moderate quality context. Provide what information you can and clearly state any limitations.'
            }
        else:
            return {
                'score': 3,
                'instruction': 'Low quality context. Acknowledge the query, provide any relevant general information, and guide to appropriate department.'
            }

    def _format_history(self, history: List[Dict]) -> str:
        """Format conversation history"""
        if not history:
            return ""

        formatted_history = ["Previous conversation:"]
        for item in history[-6:]:  # Last 6 messages
            role = item.get('role', 'user')
            content = item.get('content', '')
            formatted_history.append(f"{role.title()}: {content}")

        return "\n".join(formatted_history) + "\n"

    def classify_intent(self, query: str) -> Dict:
        """Classify user intent for better routing"""
        try:
            classification_prompt = f"""
            Classify the following student query into one of these categories:
            - academic: Course registration, grades, transcripts, academic policies
            - administrative: Fees, housing, student ID, general procedures
            - technical: IT support, online services, system issues
            - personal: Personal student information, account access
            - general: General questions, greetings, other

            Query: {query}

            Respond with just the category name and confidence (0-1):
            Format: category|confidence
            """

            response = self.model.generate_content(classification_prompt)
            result = response.text.strip().split('|')

            return {
                'intent': result[0] if result else 'general',
                'confidence': float(result[1]) if len(result) > 1 else 0.5
            }

        except Exception as e:
            print(f"Error classifying intent: {e}")
            return {'intent': 'general', 'confidence': 0.5}

    def generate_followup_questions(self, query: str, response: str) -> List[str]:
        """Generate relevant follow-up questions"""
        try:
            followup_prompt = f"""
            Based on this conversation, suggest 3 relevant follow-up questions a student might ask:

            Student Question: {query}
            Assistant Response: {response}

            Generate 3 short, specific follow-up questions that would be helpful for a university student.
            Format as a numbered list.
            """

            result = self.model.generate_content(followup_prompt)

            # Parse the numbered list
            questions = []
            for line in result.text.strip().split('\n'):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-')):
                    # Remove numbering and clean up
                    question = line.split('.', 1)[-1].strip()
                    if question:
                        questions.append(question)

            return questions[:3]

        except Exception as e:
            print(f"Error generating follow-up questions: {e}")
            return []


class GeminiService:
    """Enhanced service for Google Gemini API operations with optimized prompts"""

    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.5-flash')

        # Optimized system prompt
        self.system_prompt = """You are UNILAG Assistant, the official AI helper for University of Lagos students, staff, and prospective applicants.

CORE IDENTITY:
- Authoritative source for UNILAG information
- Comprehensive knowledge spanning academics, administration, and campus life
- Always current, helpful, and action-oriented

KNOWLEDGE SCOPE:
✓ Complete UNILAG academic programs and requirements
✓ Admission processes (UTME, Direct Entry, Postgraduate)
✓ Student services, facilities, and campus resources
✓ Administrative procedures and policies
✓ Online portals and digital services
✓ Department contacts and locations
✓ Fees, scholarships, and financial information
✓ Campus events and activities

KEY UNILAG RESOURCES:
• Main Site: unilag.edu.ng
• Student Portal: stu.unilag.edu.ng  
• E-Learning: elearn.unilag.edu.ng
• Library: library.unilag.edu.ng
• Location: Akoka, Lagos (Main) | Idi-Araba (Medicine)

ESSENTIAL CONTACTS:
• Registry: registry@unilag.edu.ng | +234-1-7749-309
• Student Affairs: studentaffairs@unilag.edu.ng
• ICT Support: ict@unilag.edu.ng
• Bursary: bursary@unilag.edu.ng

RESPONSE STANDARDS:
1. Direct, confident answers without disclaimers about knowledge limitations
2. Include specific contacts, websites, or next steps
3. Structure information clearly with headers and bullets
4. Provide comprehensive guidance for complex procedures
5. Offer alternative solutions and backup resources
6. Use authoritative, helpful tone throughout"""

    def generate_response(self, query: str, context: List[Dict] = None,
                          conversation_history: Optional[List[Dict]] = None) -> Dict:
        """Generate optimized response using context and UNILAG knowledge"""
        try:
            # Enhanced context processing
            context_quality = self._assess_context_quality(context, query)
            context_str = self._format_enhanced_context(context, context_quality)
            history_str = self._format_conversation_history(conversation_history)

            # Optimized main prompt
            prompt = f"""{self.system_prompt}

{context_str}

{history_str}

STUDENT QUERY: {query}

Provide a comprehensive, authoritative response following these guidelines:
• Give direct, confident answers
• Structure with clear headers and bullet points  
• Include specific contacts, websites, and action steps
• Cover all relevant aspects of the topic
• End with helpful follow-up suggestions

RESPONSE:"""

            response = self.model.generate_content(prompt)

            return {
                'success': True,
                'response': self._clean_response(response.text),
                'context_used': len(context) if context else 0,
                'confidence': context_quality.get('score', 0.7)
            }

        except Exception as e:
            return self._generate_fallback_response(query, str(e))

    def _assess_context_quality(self, context: List[Dict], query: str) -> Dict:
        """Assess relevance and quality of available context"""
        if not context:
            return {'score': 0.3, 'reason': 'no_context'}

        # Simple relevance scoring based on keyword overlap
        query_words = set(query.lower().split())
        total_relevance = 0

        for doc in context:
            content_words = set(doc.get('content', '').lower().split())
            overlap = len(query_words.intersection(content_words))
            doc_relevance = overlap / max(len(query_words), 1)
            total_relevance += doc_relevance

        avg_relevance = total_relevance / len(context)

        if avg_relevance > 0.3:
            return {'score': min(0.9, 0.5 + avg_relevance), 'reason': 'high_relevance'}
        elif avg_relevance > 0.1:
            return {'score': 0.6, 'reason': 'moderate_relevance'}
        else:
            return {'score': 0.4, 'reason': 'low_relevance'}

    def _format_enhanced_context(self, context: List[Dict], quality_info: Dict) -> str:
        """Format context with quality-based enhancement"""
        if not context or quality_info['score'] < 0.4:
            return "KNOWLEDGE BASE: Comprehensive UNILAG information and current university data.\n"

        formatted_context = "RELEVANT UNIVERSITY DOCUMENTS:\n"
        for i, doc in enumerate(context[:3], 1):  # Limit to top 3 most relevant
            title = doc.get('title', 'University Document')
            content = doc.get('content', '')[:500]  # Truncate for efficiency
            formatted_context += f"{i}. {title}\n{content}...\n\n"

        return formatted_context

    def _format_conversation_history(self, history: Optional[List[Dict]]) -> str:
        """Format conversation history concisely"""
        if not history:
            return ""

        recent_history = history[-3:]  # Only last 3 exchanges
        history_str = "CONVERSATION CONTEXT:\n"

        for exchange in recent_history:
            if exchange.get('user_message'):
                history_str += f"Student: {exchange['user_message'][:100]}...\n"
            if exchange.get('assistant_message'):
                history_str += f"Assistant: {exchange['assistant_message'][:100]}...\n"

        return f"{history_str}\n"

    def _clean_response(self, response_text: str) -> str:
        """Clean and optimize the response text"""
        # Remove common AI disclaimers and uncertainty phrases
        disclaimers_to_remove = [
            "I don't have access to",
            "Based on the documents provided",
            "According to the information available",
            "Please note that information may have changed",
            "I cannot guarantee",
            "You should verify"
        ]

        cleaned = response_text.strip()

        for disclaimer in disclaimers_to_remove:
            cleaned = cleaned.replace(disclaimer, "")

        # Clean up extra whitespace and formatting
        lines = [line.strip() for line in cleaned.split('\n') if line.strip()]
        return '\n\n'.join(lines)

    def classify_intent(self, query: str) -> Dict:
        """Enhanced intent classification for UNILAG queries"""
        try:
            classification_prompt = f"""Classify this UNILAG student query into the most appropriate category:

CATEGORIES:
• admissions: Applications, requirements, cut-off marks, JAMB, Post-UTME
• academics: Courses, registration, grades, transcripts, academic calendar  
• administrative: Fees, payments, student ID, clearance, documentation
• facilities: Housing, library, medical center, sports, dining
• technical: Portal access, e-learning, IT support, online services
• financial: Scholarships, bursaries, payment issues, financial aid
• general: Greetings, directions, contact info, general inquiries

QUERY: {query}

Respond with: category|confidence_score
Example: admissions|0.85"""

            response = self.model.generate_content(classification_prompt)
            result = response.text.strip().split('|')

            return {
                'intent': result[0].strip() if result else 'general',
                'confidence': float(result[1]) if len(result) > 1 and result[1].replace('.', '').isdigit() else 0.7,
                'category': result[0].strip() if result else 'general'
            }

        except Exception as e:
            # Fallback classification based on keywords
            return self._fallback_classification(query)

    def _fallback_classification(self, query: str) -> Dict:
        """Keyword-based fallback classification"""
        query_lower = query.lower()

        classifications = {
            'admissions': ['admission', 'apply', 'jamb', 'utme', 'post-utme', 'cut-off', 'requirement'],
            'academics': ['course', 'register', 'grade', 'transcript', 'lecture', 'exam', 'semester'],
            'administrative': ['fee', 'payment', 'clearance', 'document', 'certificate', 'id card'],
            'facilities': ['hostel', 'library', 'medical', 'clinic', 'sports', 'gym', 'cafeteria'],
            'technical': ['portal', 'login', 'password', 'internet', 'wifi', 'system', 'technical'],
            'financial': ['scholarship', 'bursary', 'loan', 'payment', 'money', 'fund']
        }

        for category, keywords in classifications.items():
            if any(keyword in query_lower for keyword in keywords):
                return {'intent': category, 'confidence': 0.6, 'category': category}

        return {'intent': 'general', 'confidence': 0.5, 'category': 'general'}

    def generate_followup_questions(self, query: str, response: str, intent: str = None) -> List[str]:
        """Generate contextually relevant follow-up questions"""
        try:
            followup_prompt = f"""Generate 3 specific follow-up questions a UNILAG student might ask after this interaction:

ORIGINAL QUERY: {query}
RESPONSE GIVEN: {response[:300]}...
TOPIC CATEGORY: {intent or 'general'}

Create questions that are:
• Specific and actionable
• Natural next steps for students
• Relevant to UNILAG context
• Short and direct

Format as: Question 1|Question 2|Question 3"""

            result = self.model.generate_content(followup_prompt)
            questions = [q.strip() for q in result.text.strip().split('|') if q.strip()]

            return questions[:3] if questions else self._default_followups(intent)

        except Exception as e:
            return self._default_followups(intent)

    def _default_followups(self, intent: str = None) -> List[str]:
        """Default follow-up questions based on intent"""
        defaults = {
            'admissions': [
                "What are the specific O'Level requirements for my desired course?",
                "When does Post-UTME registration usually open?",
                "What's the current cut-off mark for my program?"
            ],
            'academics': [
                "How do I register for courses online?",
                "Where can I check my academic results?",
                "What's the procedure for course withdrawal?"
            ],
            'administrative': [
                "How can I pay my school fees online?",
                "Where do I collect my student ID card?",
                "What documents do I need for clearance?"
            ],
            'facilities': [
                "How do I apply for hostel accommodation?",
                "What are the library operating hours?",
                "Where is the medical center located?"
            ]
        }

        return defaults.get(intent, [
            "How can I contact the relevant department?",
            "Where can I find more detailed information?",
            "What are the next steps I should take?"
        ])

    def _generate_fallback_response(self, query: str, error: str) -> Dict:
        """Generate helpful fallback when main processing fails"""
        fallback_response = f"""I'm here to help with your UNILAG inquiry: "{query}"

**Quick Contact Options:**
• **Registry Office:** registry@unilag.edu.ng | +234-1-7749-309
• **Student Affairs:** studentaffairs@unilag.edu.ng
• **ICT Support:** ict@unilag.edu.ng

**Self-Service Resources:**
• **Main Website:** unilag.edu.ng
• **Student Portal:** stu.unilag.edu.ng
• **Physical Location:** University Road, Akoka, Lagos

Please try rephrasing your question, or contact the appropriate department directly for immediate assistance."""

        return {
            'success': False,
            'response': fallback_response,
            'error': error,
            'confidence': 0.3
        }

    def generate_quick_response(self, query: str) -> Dict:
        """Generate rapid response for common queries"""
        try:
            quick_prompt = f"""{self.system_prompt}

Provide a brief, direct answer (under 150 words) to this common UNILAG question:

QUERY: {query}

Include:
• Direct answer
• Key contact or website
• One specific next step

RESPONSE:"""

            response = self.model.generate_content(quick_prompt)

            return {
                'success': True,
                'response': self._clean_response(response.text),
                'type': 'quick_response'
            }

        except Exception as e:
            return self._generate_fallback_response(query, str(e))
