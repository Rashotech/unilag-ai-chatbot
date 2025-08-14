# # chatbot/services/fastmcp_server.py
# from mcp.server.fastmcp import FastMCP
# from mcp.types import Resource, Tool, TextContent
# from typing import Dict, Any, List, Optional, Sequence
# import json
# import logging
# from django.db import connection
# from django.core.serializers.json import DjangoJSONEncoder
# from ..models import Student, Course, Result, AcademicSession, Semester, Enrollment
# from django.db.models import Avg, Sum, Count, Q
# from decimal import Decimal
#
# logger = logging.getLogger(__name__)
#
#
# class UniversityMCPServer:
#     """FastMCP server for University Management System"""
#
#     def __init__(self):
#         self.mcp = FastMCP("UNILAG University System")
#         self._setup_tools()
#         self._setup_resources()
#
#     def _setup_tools(self):
#         """Setup MCP tools for database operations"""
#
#         @self.mcp.tool()
#         async def get_student_profile(student_id: str) -> Dict[str, Any]:
#             """Get comprehensive student profile information"""
#             try:
#                 student = Student.objects.select_related(
#                     'department', 'faculty', 'current_session', 'user'
#                 ).get(student_id=student_id)
#
#                 profile_data = {
#                     'student_id': student.student_id,
#                     'full_name': student.user.get_full_name(),
#                     'email': student.user.email,
#                     'department': student.department.name,
#                     'faculty': student.faculty.name,
#                     'current_level': student.current_level,
#                     'entry_session': student.entry_session.name if student.entry_session else None,
#                     'current_session': student.current_session.name if student.current_session else None,
#                     'current_cgpa': float(student.current_cgpa) if student.current_cgpa else None,
#                     'total_credits': student.total_credits_earned,
#                     'graduation_status': student.graduation_status,
#                     'is_active': student.is_active,
#                     'created_at': student.created_at.isoformat()
#                 }
#
#                 return {
#                     'success': True,
#                     'data': profile_data,
#                     'message': f'Profile retrieved for {student.user.get_full_name()}'
#                 }
#
#             except Student.DoesNotExist:
#                 return {
#                     'success': False,
#                     'error': f'Student with ID {student_id} not found',
#                     'data': None
#                 }
#             except Exception as e:
#                 logger.error(f"Error getting student profile: {e}")
#                 return {
#                     'success': False,
#                     'error': str(e),
#                     'data': None
#                 }
#
#         @self.mcp.tool()
#         async def get_student_results(
#                 student_id: str,
#                 session_name: Optional[str] = None,
#                 semester_number: Optional[str] = None
#         ) -> Dict[str, Any]:
#             """Get student's academic results"""
#             try:
#                 student = Student.objects.get(student_id=student_id)
#
#                 # Build query filters
#                 filters = Q(student=student)
#                 if session_name:
#                     filters &= Q(semester__session__name=session_name)
#                 if semester_number:
#                     filters &= Q(semester__semester_number=semester_number)
#
#                 results = Result.objects.select_related(
#                     'student', 'course', 'semester__session'
#                 ).filter(filters).order_by('-semester__session__start_date', 'course__code')
#
#                 results_data = []
#                 total_points = 0
#                 total_units = 0
#
#                 for result in results:
#                     result_info = {
#                         'course_code': result.course.code,
#                         'course_title': result.course.title,
#                         'course_units': result.course.units,
#                         'grade': result.grade,
#                         'grade_points': result.grade_points,
#                         'total_points': result.total_points,
#                         'session': result.semester.session.name,
#                         'semester': result.semester.get_semester_number_display(),
#                         'is_repeat': result.is_repeat,
#                         'date_recorded': result.created_at.isoformat()
#                     }
#                     results_data.append(result_info)
#
#                     if not result.is_repeat:
#                         total_points += result.total_points
#                         total_units += result.course.units
#
#                 # Calculate GPA for filtered results
#                 gpa = round(total_points / total_units, 2) if total_units > 0 else 0.0
#
#                 return {
#                     'success': True,
#                     'data': {
#                         'student_id': student_id,
#                         'results': results_data,
#                         'summary': {
#                             'total_courses': len(results_data),
#                             'total_units': total_units,
#                             'total_points': total_points,
#                             'gpa_for_period': gpa,
#                             'session_filter': session_name,
#                             'semester_filter': semester_number
#                         }
#                     },
#                     'message': f'Retrieved {len(results_data)} results for student {student_id}'
#                 }
#
#             except Student.DoesNotExist:
#                 return {
#                     'success': False,
#                     'error': f'Student with ID {student_id} not found',
#                     'data': None
#                 }
#             except Exception as e:
#                 logger.error(f"Error getting student results: {e}")
#                 return {
#                     'success': False,
#                     'error': str(e),
#                     'data': None
#                 }
#
#         @self.mcp.tool()
#         async def get_student_cgpa(student_id: str) -> Dict[str, Any]:
#             """Get student's CGPA and academic standing"""
#             try:
#                 student = Student.objects.get(student_id=student_id)
#
#                 # Get all non-repeat results
#                 results = Result.objects.filter(
#                     student=student,
#                     is_repeat=False
#                 ).select_related('course', 'semester__session')
#
#                 # Calculate CGPA manually for verification
#                 total_points = sum(result.total_points for result in results)
#                 total_units = sum(result.course.units for result in results)
#                 calculated_cgpa = round(total_points / total_units, 2) if total_units > 0 else 0.0
#
#                 # Get session-wise GPA
#                 session_gpas = []
#                 sessions = AcademicSession.objects.filter(
#                     semesters__results__student=student
#                 ).distinct().order_by('start_date')
#
#                 for session in sessions:
#                     session_results = results.filter(semester__session=session)
#                     session_points = sum(r.total_points for r in session_results)
#                     session_units = sum(r.course.units for r in session_results)
#                     session_gpa = round(session_points / session_units, 2) if session_units > 0 else 0.0
#
#                     session_gpas.append({
#                         'session': session.name,
#                         'gpa': session_gpa,
#                         'total_units': session_units,
#                         'courses_taken': len(session_results)
#                     })
#
#                 # Determine class of degree
#                 class_of_degree = self._get_class_of_degree(calculated_cgpa)
#
#                 cgpa_data = {
#                     'student_id': student_id,
#                     'current_cgpa': float(student.current_cgpa) if student.current_cgpa else None,
#                     'calculated_cgpa': calculated_cgpa,
#                     'total_credits_earned': total_units,
#                     'total_grade_points': total_points,
#                     'class_of_degree': class_of_degree,
#                     'academic_standing': self._get_academic_standing(calculated_cgpa),
#                     'session_gpas': session_gpas,
#                     'total_sessions': len(session_gpas),
#                     'last_updated': student.updated_at.isoformat()
#                 }
#
#                 return {
#                     'success': True,
#                     'data': cgpa_data,
#                     'message': f'CGPA information retrieved for student {student_id}'
#                 }
#
#             except Student.DoesNotExist:
#                 return {
#                     'success': False,
#                     'error': f'Student with ID {student_id} not found',
#                     'data': None
#                 }
#             except Exception as e:
#                 logger.error(f"Error getting student CGPA: {e}")
#                 return {
#                     'success': False,
#                     'error': str(e),
#                     'data': None
#                 }
#
#         @self.mcp.tool()
#         async def get_student_courses(
#                 student_id: str,
#                 session_name: Optional[str] = None,
#                 semester_number: Optional[str] = None,
#                 status: Optional[str] = "all"
#         ) -> Dict[str, Any]:
#             """Get student's course registrations and enrollments"""
#             try:
#                 student = Student.objects.get(student_id=student_id)
#
#                 # Build query filters
#                 filters = Q(student=student)
#                 if session_name:
#                     filters &= Q(semester__session__name=session_name)
#                 if semester_number:
#                     filters &= Q(semester__semester_number=semester_number)
#                 if status == "current":
#                     filters &= Q(semester__is_current=True)
#
#                 enrollments = Enrollment.objects.select_related(
#                     'course', 'semester__session'
#                 ).filter(filters).order_by('-semester__session__start_date', 'course__code')
#
#                 courses_data = []
#                 total_units = 0
#
#                 for enrollment in enrollments:
#                     # Check if student has result for this course
#                     result = Result.objects.filter(
#                         student=student,
#                         course=enrollment.course,
#                         semester=enrollment.semester
#                     ).first()
#
#                     course_info = {
#                         'course_code': enrollment.course.code,
#                         'course_title': enrollment.course.title,
#                         'course_units': enrollment.course.units,
#                         'course_type': enrollment.course.course_type,
#                         'is_elective': enrollment.course.is_elective,
#                         'prerequisite_courses': [
#                             prereq.code for prereq in enrollment.course.prerequisites.all()
#                         ],
#                         'session': enrollment.semester.session.name,
#                         'semester': enrollment.semester.get_semester_number_display(),
#                         'enrollment_date': enrollment.enrollment_date.isoformat(),
#                         'status': enrollment.status,
#                         'has_result': result is not None,
#                         'grade': result.grade if result else None,
#                         'grade_points': result.grade_points if result else None
#                     }
#                     courses_data.append(course_info)
#                     total_units += enrollment.course.units
#
#                 return {
#                     'success': True,
#                     'data': {
#                         'student_id': student_id,
#                         'courses': courses_data,
#                         'summary': {
#                             'total_courses': len(courses_data),
#                             'total_units': total_units,
#                             'completed_courses': len([c for c in courses_data if c['has_result']]),
#                             'pending_courses': len([c for c in courses_data if not c['has_result']]),
#                             'session_filter': session_name,
#                             'semester_filter': semester_number
#                         }
#                     },
#                     'message': f'Retrieved {len(courses_data)} course enrollments for student {student_id}'
#                 }
#
#             except Student.DoesNotExist:
#                 return {
#                     'success': False,
#                     'error': f'Student with ID {student_id} not found',
#                     'data': None
#                 }
#             except Exception as e:
#                 logger.error(f"Error getting student courses: {e}")
#                 return {
#                     'success': False,
#                     'error': str(e),
#                     'data': None
#                 }
#
#         @self.mcp.tool()
#         async def check_prerequisites(student_id: str, course_code: str) -> Dict[str, Any]:
#             """Check if student meets prerequisites for a course"""
#             try:
#                 student = Student.objects.get(student_id=student_id)
#                 course = Course.objects.get(code=course_code.upper())
#
#                 # Get all prerequisites for the course
#                 prerequisites = course.prerequisites.all()
#
#                 if not prerequisites.exists():
#                     return {
#                         'success': True,
#                         'data': {
#                             'student_id': student_id,
#                             'course_code': course_code.upper(),
#                             'course_title': course.title,
#                             'eligible': True,
#                             'prerequisites_required': [],
#                             'prerequisites_met': [],
#                             'prerequisites_missing': [],
#                             'message': 'No prerequisites required for this course'
#                         }
#                     }
#
#                 # Check which prerequisites are met
#                 student_results = Result.objects.filter(
#                     student=student,
#                     grade__in=['A', 'B', 'C', 'D', 'E']  # Passing grades
#                 ).values_list('course__code', flat=True)
#
#                 prerequisites_met = []
#                 prerequisites_missing = []
#
#                 for prereq in prerequisites:
#                     prereq_info = {
#                         'course_code': prereq.code,
#                         'course_title': prereq.title,
#                         'units': prereq.units
#                     }
#
#                     if prereq.code in student_results:
#                         prerequisites_met.append(prereq_info)
#                     else:
#                         prerequisites_missing.append(prereq_info)
#
#                 # Check level requirements
#                 level_eligible = True
#                 level_message = ""
#
#                 if course.level > student.current_level:
#                     level_eligible = False
#                     level_message = f"Course is for {course.level} level students, but student is currently in {student.current_level} level"
#
#                 # Overall eligibility
#                 eligible = len(prerequisites_missing) == 0 and level_eligible
#
#                 return {
#                     'success': True,
#                     'data': {
#                         'student_id': student_id,
#                         'course_code': course_code.upper(),
#                         'course_title': course.title,
#                         'course_level': course.level,
#                         'student_level': student.current_level,
#                         'eligible': eligible,
#                         'level_eligible': level_eligible,
#                         'level_message': level_message,
#                         'prerequisites_required': [
#                             {'course_code': p.code, 'course_title': p.title, 'units': p.units}
#                             for p in prerequisites
#                         ],
#                         'prerequisites_met': prerequisites_met,
#                         'prerequisites_missing': prerequisites_missing,
#                         'total_prerequisites': len(prerequisites),
#                         'prerequisites_satisfied': len(prerequisites_met),
#                         'message': 'Eligible for course' if eligible else 'Prerequisites not met'
#                     }
#                 }
#
#             except Student.DoesNotExist:
#                 return {
#                     'success': False,
#                     'error': f'Student with ID {student_id} not found',
#                     'data': None
#                 }
#             except Course.DoesNotExist:
#                 return {
#                     'success': False,
#                     'error': f'Course with code {course_code} not found',
#                     'data': None
#                 }
#             except Exception as e:
#                 logger.error(f"Error checking prerequisites: {e}")
#                 return {
#                     'success': False,
#                     'error': str(e),
#                     'data': None
#                 }
#
#         @self.mcp.tool()
#         async def get_graduation_status(student_id: str) -> Dict[str, Any]:
#             """Check student's graduation eligibility and requirements"""
#             try:
#                 student = Student.objects.get(student_id=student_id)
#                 department = student.department
#
#                 # Calculate current academic standing
#                 completed_results = Result.objects.filter(
#                     student=student,
#                     grade__in=['A', 'B', 'C', 'D', 'E'],  # Passing grades
#                     is_repeat=False
#                 )
#
#                 total_units_completed = sum(result.course.units for result in completed_results)
#                 total_points = sum(result.total_points for result in completed_results)
#                 current_cgpa = round(total_points / total_units_completed, 2) if total_units_completed > 0 else 0.0
#
#                 # Get minimum requirements (you may need to adjust based on your requirements)
#                 min_units_required = 120  # Adjust based on degree program
#                 min_cgpa_required = 1.50  # Minimum CGPA for graduation
#
#                 # Check course requirements by type
#                 core_courses_taken = completed_results.filter(course__course_type='CORE').count()
#                 elective_courses_taken = completed_results.filter(course__course_type='ELECTIVE').count()
#
#                 # Determine graduation eligibility
#                 units_requirement_met = total_units_completed >= min_units_required
#                 cgpa_requirement_met = current_cgpa >= min_cgpa_required
#                 eligible_for_graduation = units_requirement_met and cgpa_requirement_met
#
#                 # Calculate remaining requirements
#                 units_remaining = max(0, min_units_required - total_units_completed)
#
#                 # Get failed courses that need to be retaken
#                 failed_results = Result.objects.filter(
#                     student=student,
#                     grade='F'
#                 ).select_related('course')
#
#                 failed_courses = [{
#                     'course_code': result.course.code,
#                     'course_title': result.course.title,
#                     'units': result.course.units,
#                     'session_failed': result.semester.session.name
#                 } for result in failed_results]
#
#                 graduation_data = {
#                     'student_id': student_id,
#                     'student_name': student.user.get_full_name(),
#                     'department': department.name,
#                     'current_level': student.current_level,
#                     'eligible_for_graduation': eligible_for_graduation,
#                     'current_cgpa': current_cgpa,
#                     'total_units_completed': total_units_completed,
#                     'requirements': {
#                         'minimum_units_required': min_units_required,
#                         'minimum_cgpa_required': min_cgpa_required,
#                         'units_requirement_met': units_requirement_met,
#                         'cgpa_requirement_met': cgpa_requirement_met,
#                         'units_remaining': units_remaining
#                     },
#                     'course_breakdown': {
#                         'core_courses_completed': core_courses_taken,
#                         'elective_courses_completed': elective_courses_taken,
#                         'total_courses_completed': len(completed_results)
#                     },
#                     'failed_courses': failed_courses,
#                     'failed_courses_count': len(failed_courses),
#                     'class_of_degree': self._get_class_of_degree(current_cgpa),
#                     'academic_standing': self._get_academic_standing(current_cgpa),
#                     'last_updated': student.updated_at.isoformat()
#                 }
#
#                 return {
#                     'success': True,
#                     'data': graduation_data,
#                     'message': f'Graduation status retrieved for {student.user.get_full_name()}'
#                 }
#
#             except Student.DoesNotExist:
#                 return {
#                     'success': False,
#                     'error': f'Student with ID {student_id} not found',
#                     'data': None
#                 }
#             except Exception as e:
#                 logger.error(f"Error getting graduation status: {e}")
#                 return {
#                     'success': False,
#                     'error': str(e),
#                     'data': None
#                 }
#
#         @self.mcp.tool()
#         async def get_academic_calendar(session_name: Optional[str] = None) -> Dict[str, Any]:
#             """Get current academic calendar information"""
#             try:
#                 if session_name:
#                     session = AcademicSession.objects.get(name=session_name)
#                     sessions = [session]
#                 else:
#                     # Get current session or latest if no current
#                     current_session = AcademicSession.objects.filter(is_current=True).first()
#                     if current_session:
#                         sessions = [current_session]
#                     else:
#                         sessions = AcademicSession.objects.order_by('-start_date')[:1]
#
#                 calendar_data = []
#
#                 for session in sessions:
#                     semesters = session.semesters.all().order_by('semester_number')
#
#                     semesters_info = []
#                     for semester in semesters:
#                         semester_info = {
#                             'semester_id': str(semester.id),
#                             'semester_number': semester.semester_number,
#                             'semester_name': semester.get_semester_number_display(),
#                             'start_date': semester.start_date.isoformat(),
#                             'end_date': semester.end_date.isoformat(),
#                             'registration_deadline': semester.registration_deadline.isoformat(),
#                             'is_current': semester.is_current,
#                             'days_to_deadline': (semester.registration_deadline.date() -
#                                                  timezone.now().date()).days
#                         }
#                         semesters_info.append(semester_info)
#
#                     session_info = {
#                         'session_id': str(session.id),
#                         'session_name': session.name,
#                         'start_date': session.start_date.isoformat(),
#                         'end_date': session.end_date.isoformat(),
#                         'is_current': session.is_current,
#                         'semesters': semesters_info,
#                         'total_semesters': len(semesters_info)
#                     }
#                     calendar_data.append(session_info)
#
#                 return {
#                     'success': True,
#                     'data': {
#                         'sessions': calendar_data,
#                         'total_sessions': len(calendar_data),
#                         'query_session': session_name,
#                         'retrieved_at': timezone.now().isoformat()
#                     },
#                     'message': f'Academic calendar information retrieved'
#                 }
#
#             except AcademicSession.DoesNotExist:
#                 return {
#                     'success': False,
#                     'error': f'Academic session {session_name} not found',
#                     'data': None
#                 }
#             except Exception as e:
#                 logger.error(f"Error getting academic calendar: {e}")
#                 return {
#                     'success': False,
#                     'error': str(e),
#                     'data': None
#                 }
#
#         @self.mcp.tool()
#         async def get_course_info(course_code: str) -> Dict[str, Any]:
#             """Get detailed information about a specific course"""
#             try:
#                 course = Course.objects.select_related('department', 'faculty').prefetch_related(
#                     'prerequisites', 'corequisites'
#                 ).get(code=course_code.upper())
#
#                 # Get prerequisites and corequisites
#                 prerequisites = [
#                     {'code': p.code, 'title': p.title, 'units': p.units}
#                     for p in course.prerequisites.all()
#                 ]
#
#                 corequisites = [
#                     {'code': c.code, 'title': c.title, 'units': c.units}
#                     for c in course.corequisites.all()
#                 ]
#
#                 # Get statistics about the course
#                 total_enrollments = Enrollment.objects.filter(course=course).count()
#                 results_stats = Result.objects.filter(course=course).aggregate(
#                     total_attempts=Count('id'),
#                     average_gp=Avg('grade_points'),
#                     pass_count=Count('id', filter=Q(grade__in=['A', 'B', 'C', 'D', 'E'])),
#                     fail_count=Count('id', filter=Q(grade='F'))
#                 )
#
#                 pass_rate = 0
#                 if results_stats['total_attempts'] > 0:
#                     pass_rate = round((results_stats['pass_count'] / results_stats['total_attempts']) * 100, 2)
#
#                 course_data = {
#                     'course_code': course.code,
#                     'course_title': course.title,
#                     'course_units': course.units,
#                     'course_type': course.course_type,
#                     'level': course.level,
#                     'department': course.department.name,
#                     'faculty': course.faculty.name,
#                     'is_elective': course.is_elective,
#                     'description': course.description,
#                     'prerequisites': prerequisites,
#                     'corequisites': corequisites,
#                     'total_prerequisites': len(prerequisites),
#                     'total_corequisites': len(corequisites),
#                     'statistics': {
#                         'total_enrollments': total_enrollments,
#                         'total_attempts': results_stats['total_attempts'] or 0,
#                         'average_grade_point': round(results_stats['average_gp'] or 0, 2),
#                         'pass_count': results_stats['pass_count'] or 0,
#                         'fail_count': results_stats['fail_count'] or 0,
#                         'pass_rate_percentage': pass_rate
#                     },
#                     'created_at': course.created_at.isoformat(),
#                     'last_updated': course.updated_at.isoformat()
#                 }
#
#                 return {
#                     'success': True,
#                     'data': course_data,
#                     'message': f'Course information retrieved for {course_code}'
#                 }
#
#             except Course.DoesNotExist:
#                 return {
#                     'success': False,
#                     'error': f'Course with code {course_code} not found',
#                     'data': None
#                 }
#             except Exception as e:
#                 logger.error(f"Error getting course info: {e}")
#                 return {
#                     'success': False,
#                     'error': str(e),
#                     'data': None
#                 }
#
#         @self.mcp.tool()
#         async def search_courses(
#                 query: str,
#                 department_code: Optional[str] = None,
#                 level: Optional[int] = None,
#                 course_type: Optional[str] = None,
#                 limit: int = 20
#         ) -> Dict[str, Any]:
#             """Search for courses based on various criteria"""
#             try:
#                 # Build search filters
#                 filters = Q()
#
#                 # Text search in code, title, or description
#                 if query.strip():
#                     text_filter = (
#                             Q(code__icontains=query) |
#                             Q(title__icontains=query) |
#                             Q(description__icontains=query)
#                     )
#                     filters &= text_filter
#
#                 if department_code:
#                     filters &= Q(department__code=department_code.upper())
#
#                 if level:
#                     filters &= Q(level=level)
#
#                 if course_type:
#                     filters &= Q(course_type=course_type.upper())
#
#                 courses = Course.objects.select_related('department', 'faculty').filter(
#                     filters
#                 ).order_by('code')[:limit]
#
#                 courses_data = []
#                 for course in courses:
#                     course_info = {
#                         'course_code': course.code,
#                         'course_title': course.title,
#                         'course_units': course.units,
#                         'course_type': course.course_type,
#                         'level': course.level,
#                         'department': course.department.name,
#                         'department_code': course.department.code,
#                         'faculty': course.faculty.name,
#                         'is_elective': course.is_elective,
#                         'has_prerequisites': course.prerequisites.exists(),
#                         'description_snippet': course.description[:200] + '...' if len(
#                             course.description) > 200 else course.description
#                     }
#                     courses_data.append(course_info)
#
#                 return {
#                     'success': True,
#                     'data': {
#                         'courses': courses_data,
#                         'total_found': len(courses_data),
#                         'search_query': query,
#                         'filters_applied': {
#                             'department_code': department_code,
#                             'level': level,
#                             'course_type': course_type
#                         },
#                         'limit': limit
#                     },
#                     'message': f'Found {len(courses_data)} courses matching search criteria'
#                 }
#
#             except Exception as e:
#                 logger.error(f"Error searching courses: {e}")
#                 return {
#                     'success': False,
#                     'error': str(e),
#                     'data': None
#                 }
#
#     def _setup_resources(self):
#         """Setup MCP resources"""
#
#         @self.mcp.resource("student://{student_id}/profile")
#         async def student_profile_resource(student_id: str) -> str:
#             """Resource for student profile data"""
#             result = await self.mcp.call_tool("get_student_profile", {"student_id": student_id})
#             return json.dumps(result, cls=DjangoJSONEncoder, indent=2)
#
#         @self.mcp.resource("student://{student_id}/results")
#         async def student_results_resource(student_id: str) -> str:
#             """Resource for student results data"""
#             result = await self.mcp.call_tool("get_student_results", {"student_id": student_id})
#             return json.dumps(result, cls=DjangoJSONEncoder, indent=2)
#
#     def _get_class_of_degree(self, cgpa: float) -> str:
#         """Determine class of degree based on CGPA"""
#         if cgpa >= 4.50:
#             return "First Class"
#         elif cgpa >= 3.50:
#             return "Second Class Upper"
#         elif cgpa >= 2.40:
#             return "Second Class Lower"
#         elif cgpa >= 1.50:
#             return "Third Class"
#         else:
#             return "Pass/Fail"
#
#     def _get_academic_standing(self, cgpa: float) -> str:
#         """Determine academic standing"""
#         if cgpa >= 3.50:
#             return "Excellent"
#         elif cgpa >= 3.00:
#             return "Very Good"
#         elif cgpa >= 2.40:
#             return "Good"
#         elif cgpa >= 2.00:
#             return "Satisfactory"
#         elif cgpa >= 1.50:
#             return "Probation"
#         else:
#             return "Academic Probation"
#
#     def get_server(self) -> FastMCP:
#         """Get the configured FastMCP server"""
#         return self.mcp
#
#
# # Create global server instance
# university_mcp_server = UniversityMCPServer()
