from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from mit_chatbot.models import Result, Enrollment, Student, Course, Semester, AcademicSession, Department, Faculty

User = get_user_model()


class Command(BaseCommand):
    help = 'Reset all UNILAG data (destructive operation)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion of all data',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    'This will delete ALL data. Use --confirm to proceed.'
                )
            )
            return

        self.stdout.write('Deleting all UNILAG data...')

        # Delete in reverse order of dependencies
        Result.objects.all().delete()
        Enrollment.objects.all().delete()
        # Student.objects.all().delete()
        Course.objects.all().delete()
        Semester.objects.all().delete()
        AcademicSession.objects.all().delete()
        Department.objects.all().delete()
        Faculty.objects.all().delete()
        # User.objects.filter(user_type='student').delete()

        self.stdout.write(self.style.SUCCESS('Successfully deleted all data'))