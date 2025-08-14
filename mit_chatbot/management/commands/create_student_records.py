# management/commands/create_student_records.py
from django.core.management.base import BaseCommand
import random
from decimal import Decimal

from mit_chatbot.models import Student, Semester, Course, Enrollment, Result


class Command(BaseCommand):
    help = 'Create enrollments and results for existing students'

    def handle(self, *args, **options):
        self.stdout.write('Creating student enrollments and results...')

        students = Student.objects.filter(status='ACTIVE')
        current_semester = Semester.objects.filter(is_current=True).first()

        if not current_semester:
            self.stdout.write(self.style.ERROR('No current semester found'))
            return

        for student in students:
            self.create_student_enrollments(student, current_semester)
            self.create_student_results(student)

        # Update CGPAs
        for student in students:
            student.calculate_cgpa()

        self.stdout.write(self.style.SUCCESS('Successfully created student records'))

    def create_student_enrollments(self, student, current_semester):
        """Create course enrollments for student"""
        # Get courses for student's level and department
        level_courses = Course.objects.filter(
            level=student.current_level,
            department=student.department,
            is_active=True
        )

        # Enroll in 5-8 courses
        courses_to_enroll = random.sample(
            list(level_courses),
            min(random.randint(5, 8), level_courses.count())
        )

        for course in courses_to_enroll:
            Enrollment.objects.get_or_create(
                student=student,
                course=course,
                semester=current_semester,
                defaults={'status': 'ENROLLED'}
            )

    def create_student_results(self, student):
        """Create academic results for previous semesters"""
        # Get past semesters
        past_semesters = Semester.objects.filter(
            session__start_date__lt=student.current_session.start_date
        )[:4]  # Last 4 semesters

        for semester in past_semesters:
            semester_level = self.get_level_for_semester(student, semester)
            if semester_level <= 0:
                continue

            courses = Course.objects.filter(
                level=semester_level,
                department=student.department
            )[:random.randint(4, 7)]

            for course in courses:
                # Create enrollment first
                enrollment, _ = Enrollment.objects.get_or_create(
                    student=student,
                    course=course,
                    semester=semester,
                    defaults={'status': 'COMPLETED'}
                )

                # Create result
                ca_score = random.uniform(15, 30)
                exam_score = random.uniform(30, 70)

                Result.objects.get_or_create(
                    student=student,
                    course=course,
                    semester=semester,
                    defaults={
                        'ca_score': Decimal(str(round(ca_score, 2))),
                        'exam_score': Decimal(str(round(exam_score, 2))),
                        'is_final': True,
                        'recorded_by': 'System'
                    }
                )

    def get_level_for_semester(self, student, semester):
        """Calculate student's level for a given semester"""
        entry_year = int(student.entry_session.name.split('/')[1])
        semester_year = int(semester.session.name.split('/')[1])
        years_difference = semester_year - entry_year

        if years_difference < 0:
            return 0
        elif years_difference == 0:
            return 100
        elif years_difference == 1:
            return 200
        elif years_difference == 2:
            return 300
        elif years_difference == 3:
            return 400
        else:
            return 500