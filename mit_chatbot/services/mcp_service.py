from typing import Dict, List, Optional, Any
from django.db.models import Q, Avg, Sum, Count
from datetime import datetime
import logging

from mit_chatbot.models import Student, Course, AcademicSession, Semester, Department, Faculty, Enrollment, Result

logger = logging.getLogger(__name__)


class MCPDatabaseService:
    """MCP Service for University Database Operations"""

    def __init__(self):
        self.available_tools = {
            'get_student_profile': self.get_student_profile,
            'get_student_results': self.get_student_results,
            'get_student_cgpa': self.get_student_cgpa,
            'get_course_info': self.get_course_info,
            'get_student_courses': self.get_student_courses,
            'get_semester_results': self.get_semester_results,
            'check_prerequisites': self.check_prerequisites,
            'get_graduation_status': self.get_graduation_status,
            'get_academic_calendar': self.get_academic_calendar,
            'search_courses': self.search_courses,
            'get_department_info': self.get_department_info,
        }

    def execute_tool(self, tool_name: str, parameters: Dict) -> Dict:
        """Execute MCP tool and return structured data"""
        try:
            if tool_name not in self.available_tools:
                return {
                    'success': False,
                    'error': f"Unknown tool: {tool_name}",
                    'available_tools': list(self.available_tools.keys())
                }

            result = self.available_tools[tool_name](**parameters)
            return {
                'success': True,
                'tool': tool_name,
                'data': result,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error executing MCP tool {tool_name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'tool': tool_name
            }

    def get_student_profile(self, student_id: str = None, email: str = None) -> Dict:
        """Get comprehensive student profile"""
        try:
            if student_id:
                student = Student.objects.select_related(
                    'user', 'department__faculty', 'entry_session', 'current_session'
                ).get(student_id=student_id)
            elif email:
                student = Student.objects.select_related(
                    'user', 'department__faculty', 'entry_session', 'current_session'
                ).get(user__email=email)
            else:
                raise ValueError("Either student_id or email must be provided")

            return {
                'student_id': student.student_id,
                'full_name': f"{student.user.first_name} {student.middle_name} {student.user.last_name}".replace('  ',
                                                                                                                 ' ').strip(),
                'first_name': student.user.first_name,
                'middle_name': student.middle_name,
                'last_name': student.user.last_name,
                'email': student.user.email,
                'phone': student.phone_number,
                'department': {
                    'name': student.department.name,
                    'code': student.department.code,
                    'faculty': student.department.faculty.name
                },
                'current_level': student.current_level,
                'entry_session': student.entry_session.name,
                'current_session': student.current_session.name,
                'mode_of_entry': student.mode_of_entry,
                'student_type': student.student_type,
                'status': student.status,
                'current_cgpa': float(student.current_cgpa),
                'total_credits_earned': student.total_credits_earned,
                'academic_standing': student.academic_standing,
                'address': student.address,
                'date_of_birth': student.date_of_birth.isoformat() if student.date_of_birth else None,
                'gender': student.gender,
                'state_of_origin': student.state_of_origin,
                'guardian_info': {
                    'name': student.guardian_name,
                    'phone': student.guardian_phone,
                    'relationship': student.guardian_relationship
                }
            }

        except Student.DoesNotExist:
            raise ValueError(f"Student not found")

    def get_student_results(self, student_id: str, session_name: str = None) -> Dict:
        """Get student's academic results"""
        try:
            student = Student.objects.get(student_id=student_id)

            query = student.results.select_related(
                'course', 'semester__session'
            ).filter(is_final=True)

            if session_name:
                query = query.filter(semester__session__name=session_name)

            results = []
            for result in query:
                results.append({
                    'course_code': result.course.code,
                    'course_title': result.course.title,
                    'credits': result.course.credits,
                    'ca_score': float(result.ca_score),
                    'exam_score': float(result.exam_score),
                    'total_score': float(result.total_score),
                    'grade': result.grade,
                    'grade_point': float(result.grade_point),
                    'credit_earned': result.credit_earned,
                    'semester': str(result.semester),
                    'session': result.semester.session.name,
                    'level': result.course.level,
                    'status': result.status
                })

            return {
                'student_id': student_id,
                'results': results,
                'total_courses': len(results)
            }

        except Student.DoesNotExist:
            raise ValueError(f"Student {student_id} not found")

    def get_student_cgpa(self, student_id: str) -> Dict:
        """Get student's CGPA and related statistics"""
        try:
            student = Student.objects.get(student_id=student_id)

            # Recalculate CGPA to ensure accuracy
            current_cgpa = student.calculate_cgpa()

            # Get semester statistics
            semester_stats = []
            for semester in Semester.objects.filter(
                    results__student=student
            ).distinct().select_related('session'):

                semester_results = student.results.filter(
                    semester=semester,
                    is_final=True
                )

                if semester_results.exists():
                    total_points = sum(
                        float(r.grade_point) * r.course.credits
                        for r in semester_results
                    )
                    total_credits = sum(r.course.credits for r in semester_results)
                    semester_gpa = total_points / total_credits if total_credits > 0 else 0

                    passed_courses = semester_results.filter(grade_point__gte=1.0).count()
                    total_courses = semester_results.count()

                    semester_stats.append({
                        'semester': str(semester),
                        'session': semester.session.name,
                        'gpa': round(semester_gpa, 2),
                        'courses_taken': total_courses,
                        'courses_passed': passed_courses,
                        'credits_taken': total_credits,
                        'credits_earned': sum(r.credit_earned for r in semester_results)
                    })

            return {
                'student_id': student_id,
                'current_cgpa': float(current_cgpa),
                'total_credits_earned': student.total_credits_earned,
                'academic_standing': student.academic_standing,
                'semester_statistics': semester_stats,
                'class_of_degree': self._determine_class_of_degree(float(current_cgpa)),
                'performance_summary': self._get_performance_summary(student)
            }

        except Student.DoesNotExist:
            raise ValueError(f"Student {student_id} not found")

    def get_course_info(self, course_code: str) -> Dict:
        """Get detailed course information"""
        try:
            course = Course.objects.select_related('department__faculty').get(
                code__iexact=course_code
            )

            prerequisites = []
            for prereq in course.prerequisites.all():
                prerequisites.append({
                    'code': prereq.code,
                    'title': prereq.title,
                    'credits': prereq.credits
                })

            return {
                'code': course.code,
                'title': course.title,
                'credits': course.credits,
                'level': course.level,
                'course_type': course.course_type,
                'department': {
                    'name': course.department.name,
                    'code': course.department.code,
                    'faculty': course.department.faculty.name
                },
                'description': course.description,
                'lecturer': course.lecturer,
                'has_practical': course.has_practical,
                'prerequisites': prerequisites,
                'is_active': course.is_active
            }

        except Course.DoesNotExist:
            raise ValueError(f"Course {course_code} not found")

    def get_student_courses(self, student_id: str, semester_id: str = None) -> Dict:
        """Get courses student is/was enrolled in"""
        try:
            student = Student.objects.get(student_id=student_id)

            query = student.enrollments.select_related('course', 'semester__session')

            if semester_id:
                query = query.filter(semester_id=semester_id)

            enrollments = []
            for enrollment in query:
                # Get result if exists
                result = student.results.filter(
                    course=enrollment.course,
                    semester=enrollment.semester
                ).first()

                enrollments.append({
                    'course': {
                        'code': enrollment.course.code,
                        'title': enrollment.course.title,
                        'credits': enrollment.course.credits,
                        'level': enrollment.course.level
                    },
                    'semester': str(enrollment.semester),
                    'session': enrollment.semester.session.name,
                    'enrollment_status': enrollment.status,
                    'enrollment_date': enrollment.enrollment_date.isoformat(),
                    'result': {
                        'ca_score': float(result.ca_score) if result else None,
                        'exam_score': float(result.exam_score) if result else None,
                        'total_score': float(result.total_score) if result else None,
                        'grade': result.grade if result else None,
                        'grade_point': float(result.grade_point) if result else None,
                        'status': result.status if result else None
                    } if result else None
                })

            return {
                'student_id': student_id,
                'enrollments': enrollments,
                'total_enrollments': len(enrollments)
            }

        except Student.DoesNotExist:
            raise ValueError(f"Student {student_id} not found")

    def get_semester_results(self, student_id: str, semester_id: str) -> Dict:
        """Get student results for a specific semester"""
        try:
            student = Student.objects.get(student_id=student_id)
            semester = Semester.objects.get(pk=semester_id)

            results = student.results.filter(
                semester=semester,
                is_final=True
            ).select_related('course')

            courses = []
            total_points = 0
            total_credits = 0

            for result in results:
                course_data = {
                    'course_code': result.course.code,
                    'course_title': result.course.title,
                    'credits': result.course.credits,
                    'ca_score': float(result.ca_score),
                    'exam_score': float(result.exam_score),
                    'total_score': float(result.total_score),
                    'grade': result.grade,
                    'grade_point': float(result.grade_point),
                    'credit_earned': result.credit_earned
                }
                courses.append(course_data)

                total_points += float(result.grade_point) * result.course.credits
                total_credits += result.course.credits

            semester_gpa = total_points / total_credits if total_credits > 0 else 0

            return {
                'student_id': student_id,
                'semester': str(semester),
                'session': semester.session.name,
                'courses': courses,
                'summary': {
                    'gpa': round(semester_gpa, 2),
                    'total_courses': len(courses),
                    'total_credits': total_credits,
                    'credits_earned': sum(r.credit_earned for r in results),
                    'courses_passed': len([c for c in courses if c['grade_point'] >= 1.0])
                }
            }

        except (Student.DoesNotExist, Semester.DoesNotExist):
            raise ValueError(f"Student or semester not found")

    def check_prerequisites(self, student_id: str, course_code: str) -> Dict:
        """Check if student has met prerequisites for a course"""
        try:
            student = Student.objects.get(student_id=student_id)
            course = Course.objects.get(code__iexact=course_code)

            prerequisites = course.prerequisites.all()

            if not prerequisites.exists():
                return {
                    'eligible': True,
                    'message': 'No prerequisites required',
                    'missing_prerequisites': []
                }

            # Check which prerequisites student has completed
            completed_courses = student.results.filter(
                grade_point__gte=1.0,  # Passing grade
                is_final=True
            ).values_list('course__code', flat=True)

            missing_prerequisites = []
            for prereq in prerequisites:
                if prereq.code not in completed_courses:
                    missing_prerequisites.append({
                        'code': prereq.code,
                        'title': prereq.title,
                        'credits': prereq.credits
                    })

            return {
                'course': {
                    'code': course.code,
                    'title': course.title
                },
                'eligible': len(missing_prerequisites) == 0,
                'message': 'Prerequisites met' if len(missing_prerequisites) == 0
                else f'Missing {len(missing_prerequisites)} prerequisite(s)',
                'missing_prerequisites': missing_prerequisites,
                'completed_prerequisites': [
                    {'code': prereq.code, 'title': prereq.title}
                    for prereq in prerequisites
                    if prereq.code in completed_courses
                ]
            }

        except (Student.DoesNotExist, Course.DoesNotExist) as e:
            raise ValueError(str(e))

    def get_graduation_status(self, student_id: str) -> Dict:
        """Check student's graduation eligibility"""
        try:
            student = Student.objects.get(student_id=student_id)

            # Get student's completed courses
            completed_results = student.results.filter(
                grade_point__gte=1.0,  # Passing grade
                is_final=True
            )

            completed_credits = sum(result.credit_earned for result in completed_results)
            total_courses_passed = completed_results.count()

            # UNILAG requirements (these should be configurable)
            min_credits_required = 120
            min_cgpa_required = 1.0
            min_level_required = 400

            current_cgpa = float(student.current_cgpa)
            eligible = (
                    completed_credits >= min_credits_required and
                    current_cgpa >= min_cgpa_required and
                    student.current_level >= min_level_required and
                    student.status == 'ACTIVE'
            )

            # Check for outstanding requirements
            outstanding_requirements = []
            if completed_credits < min_credits_required:
                outstanding_requirements.append(f"Need {min_credits_required - completed_credits} more credit units")
            if current_cgpa < min_cgpa_required:
                outstanding_requirements.append(f"CGPA below minimum requirement ({min_cgpa_required})")
            if student.current_level < min_level_required:
                outstanding_requirements.append(f"Must reach {min_level_required} level")

            return {
                'student_id': student_id,
                'student_name': f"{student.user.first_name} {student.user.last_name}",
                'eligible_for_graduation': eligible,
                'current_status': student.status,
                'requirements': {
                    'minimum_credits': min_credits_required,
                    'credits_completed': completed_credits,
                    'credits_remaining': max(0, min_credits_required - completed_credits),
                    'minimum_cgpa': min_cgpa_required,
                    'current_cgpa': current_cgpa,
                    'current_level': student.current_level,
                    'courses_passed': total_courses_passed
                },
                'outstanding_requirements': outstanding_requirements,
                'projected_class_of_degree': self._determine_class_of_degree(current_cgpa),
                'graduation_status': 'Eligible' if eligible else 'Not Eligible'
            }

        except Student.DoesNotExist:
            raise ValueError(f"Student {student_id} not found")

    def get_academic_calendar(self) -> Dict:
        """Get current academic calendar information"""
        try:
            current_session = AcademicSession.objects.filter(is_current=True).first()
            current_semester = Semester.objects.filter(is_current=True).first()

            upcoming_semesters = Semester.objects.filter(
                start_date__gt=datetime.now().date()
            ).select_related('session').order_by('start_date')[:5]

            return {
                'current_session': {
                    'name': current_session.name,
                    'start_date': current_session.start_date.isoformat(),
                    'end_date': current_session.end_date.isoformat(),
                } if current_session else None,
                'current_semester': {
                    'name': str(current_semester),
                    'semester_number': current_semester.semester_number,
                    'start_date': current_semester.start_date.isoformat(),
                    'end_date': current_semester.end_date.isoformat(),
                    'session': current_semester.session.name
                } if current_semester else None,
                'upcoming_semesters': [
                    {
                        'name': str(sem),
                        'semester_number': sem.semester_number,
                        'session': sem.session.name,
                        'start_date': sem.start_date.isoformat(),
                        'end_date': sem.end_date.isoformat(),
                    } for sem in upcoming_semesters
                ]
            }

        except Exception as e:
            raise ValueError(f"Error fetching academic calendar: {e}")

    def search_coursesd(self, query: str, level: int = None, department_code: str = None,
                       course_type: str = None) -> Dict:
        """Search for courses"""
        try:
            courses_query = Course.objects.select_related('department__faculty').filter(is_active=True)

            # Text search
            if query:
                courses_query = courses_query.filter(
                    Q(code__icontains=query) |
                    Q(title__icontains=query) |
                    Q(description__icontains=query)
                )

            # Filter by level if provided
            if level:
                courses_query = courses_query.filter(level=level)

            # Filter by department if provided
            if department_code:
                courses_query = courses_query.filter(department__code__iexact=department_code)

            # Filter by course type if provided
            if course_type:
                courses_query = courses_query.filter(course_type__iexact=course_type)

            courses = []
            for course in courses_query.order_by('code')[:20]:  # Limit results
                courses.append({
                    'code': course.code,
                    'title': course.title,
                    'credits': course.credits,
                    'level': course.level,
                    'course_type': course.course_type,
                    'department': {
                        'name': course.department.name,
                        'code': course.department.code
                    },
                    'lecturer': course.lecturer,
                    'has_practical': course.has_practical
                })

            return {
                'query': query,
                'filters': {
                    'level': level,
                    'department': department_code,
                    'course_type': course_type
                },
                'courses': courses,
                'total_found': len(courses)
            }

        except Exception as e:
            raise ValueError(f"Error searching courses: {e}")

    def search_courses(self, query: str = None, level: int = None, department_code: str = None,
                       course_type: str = None) -> Dict:
        """Search for courses - expects properly formatted parameters from LLM"""
        try:
            courses_query = Course.objects.select_related('department__faculty').filter(is_active=True)

            # Apply filters as provided by LLM
            if query and query.strip():
                courses_query = courses_query.filter(
                    Q(code__icontains=query.strip()) |
                    Q(title__icontains=query.strip()) |
                    Q(description__icontains=query.strip())
                )

            if level:
                courses_query = courses_query.filter(level=level)

            if department_code and department_code.strip():
                courses_query = courses_query.filter(department__code__iexact=department_code.strip())

            if course_type and course_type.strip():
                courses_query = courses_query.filter(course_type__iexact=course_type.strip())

            courses = []
            for course in courses_query.order_by('code')[:20]:
                courses.append({
                    'code': course.code,
                    'title': course.title,
                    'credits': getattr(course, 'credits', 0),
                    'level': course.level,
                    'course_type': getattr(course, 'course_type', ''),
                    'department': {
                        'name': course.department.name,
                        'code': course.department.code
                    },
                    'lecturer': getattr(course, 'lecturer', ''),
                    'has_practical': getattr(course, 'has_practical', False)
                })

            return {
                'courses': courses,
                'total_found': courses_query.count(),
                'showing': len(courses),
                'filters_used': {
                    'query': query,
                    'level': level,
                    'department_code': department_code,
                    'course_type': course_type
                }
            }

        except Exception as e:
            return {
                'error': str(e),
                'courses': [],
                'total_found': 0
            }

    def get_department_info(self, department_code: str) -> Dict:
        """Get department information"""
        try:
            department = Department.objects.select_related('faculty').get(
                code__iexact=department_code
            )

            # Get course statistics
            course_stats = department.courses.filter(is_active=True).aggregate(
                total_courses=Count('id'),
                total_credits=Sum('credits'),
                core_courses=Count('id', filter=Q(course_type='CORE')),
                elective_courses=Count('id', filter=Q(course_type='ELECTIVE'))
            )

            # Get student count by level
            student_stats = department.students.filter(status='ACTIVE').values('current_level').annotate(
                count=Count('id')
            ).order_by('current_level')

            level_distribution = {stat['current_level']: stat['count'] for stat in student_stats}
            total_students = sum(level_distribution.values())

            return {
                'name': department.name,
                'code': department.code,
                'faculty': {
                    'name': department.faculty.name,
                    'code': department.faculty.code
                },
                'hod': department.hod,
                'description': department.description,
                'is_active': department.is_active,
                'statistics': {
                    'total_students': total_students,
                    'student_distribution': level_distribution,
                    'total_courses': course_stats['total_courses'] or 0,
                    'total_course_credits': course_stats['total_credits'] or 0,
                    'core_courses': course_stats['core_courses'] or 0,
                    'elective_courses': course_stats['elective_courses'] or 0
                }
            }

        except Department.DoesNotExist:
            raise ValueError(f"Department {department_code} not found")

    def _determine_class_of_degree(self, cgpa: float) -> str:
        """Determine class of degree based on CGPA (UNILAG system)"""
        if cgpa >= 4.50:
            return "First Class Honours"
        elif cgpa >= 3.50:
            return "Second Class Honours (Upper Division)"
        elif cgpa >= 2.40:
            return "Second Class Honours (Lower Division)"
        elif cgpa >= 1.50:
            return "Third Class Honours"
        elif cgpa >= 1.00:
            return "Pass"
        else:
            return "Fail"

    def _get_performance_summary(self, student: Student) -> Dict:
        """Get student performance summary"""
        total_results = student.results.filter(is_final=True)

        if not total_results.exists():
            return {
                'total_courses': 0,
                'courses_passed': 0,
                'courses_failed': 0,
                'pass_rate': 0,
                'average_score': 0
            }

        courses_passed = total_results.filter(grade_point__gte=1.0).count()
        courses_failed = total_results.filter(grade_point=0).count()
        total_courses = total_results.count()

        avg_score = total_results.aggregate(
            avg_score=Avg('total_score')
        )['avg_score'] or 0

        return {
            'total_courses': total_courses,
            'courses_passed': courses_passed,
            'courses_failed': courses_failed,
            'pass_rate': round((courses_passed / total_courses) * 100, 1) if total_courses > 0 else 0,
            'average_score': round(float(avg_score), 1)
        }