from django.core.management.base import BaseCommand
from django.db.models import Avg, Count
import csv
from datetime import datetime

from mit_chatbot.models import Student, Department


class Command(BaseCommand):
    help = 'Generate student academic reports'

    def handle(self, *args, **options):
        self.stdout.write('Generating student reports...')

        # Generate CSV report
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'unilag_student_report_{timestamp}.csv'

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Header
            writer.writerow([
                'Student ID', 'Full Name', 'Department', 'Faculty',
                'Current Level', 'CGPA', 'Academic Standing', 'Status',
                'Entry Session', 'Total Credits'
            ])

            # Data
            students = Student.objects.select_related(
                'user', 'department', 'faculty', 'entry_session'
            ).all()

            for student in students:
                writer.writerow([
                    student.student_id,
                    student.user.get_full_name(),
                    student.department.name,
                    student.faculty.name,
                    student.current_level,
                    student.current_cgpa,
                    student.academic_standing,
                    student.status,
                    student.entry_session.name,
                    student.total_credits_earned or 0
                ])

        # Generate summary statistics
        total_students = Student.objects.count()
        active_students = Student.objects.filter(status='ACTIVE').count()
        avg_cgpa = Student.objects.aggregate(Avg('current_cgpa'))['current_cgpa__avg']

        # Department statistics
        dept_stats = Department.objects.annotate(
            student_count=Count('students')
        ).values('name', 'student_count')

        self.stdout.write(f'Report saved to: {filename}')
        self.stdout.write(f'Total Students: {total_students}')
        self.stdout.write(f'Active Students: {active_students}')
        self.stdout.write(f'Average CGPA: {avg_cgpa:.2f}')

        self.stdout.write('\nDepartment Statistics:')
        for dept in dept_stats:
            self.stdout.write(f"  {dept['name']}: {dept['student_count']} students")
