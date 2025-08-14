from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal
import random
from datetime import date, datetime
from django.db import transaction

from mit_chatbot.models import Faculty, Department, AcademicSession, Semester, Course, Student, Enrollment, Result, \
    CustomUser

User = get_user_model()


class Command(BaseCommand):
    help = 'Populate database with UNILAG dummy data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--students',
            type=int,
            default=100,
            help='Number of students to create (default: 100)',
        )

    def handle(self, *args, **options):
        self.student_count = options['students']
        self.stdout.write('Creating UNILAG dummy data...')

        try:
                # Create data in order of dependencies
                # self.create_faculties()
                # self.create_departments()
                # self.create_academic_sessions()
                # self.create_semesters()
                # self.create_courses()
                # self.create_users_and_students()
                # self.create_enrollments()
                # self.create_results()
                self.update_student_cgpa()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating data: {e}'))
            return

        self.stdout.write(self.style.SUCCESS('Successfully populated UNILAG data'))

    def create_faculties(self):
        """Create UNILAG faculties"""
        self.stdout.write('Creating faculties...')

        faculties_data = [
            ('ARTS', 'Faculty of Arts', 'Prof. Adeyemi Johnson', 'Arts courses and humanities'),
            ('BMS', 'Faculty of Basic Medical Sciences', 'Prof. Fatima Ibrahim', 'Basic medical sciences'),
            ('CMS', 'Faculty of Clinical Sciences', 'Prof. Samuel Okafor', 'Clinical medical sciences'),
            ('DENT', 'Faculty of Dental Sciences', 'Prof. Grace Okolie', 'Dental sciences and oral health'),
            ('EDU', 'Faculty of Education', 'Prof. Kemi Adebayo', 'Education and teaching'),
            ('ENG', 'Faculty of Engineering', 'Prof. Chinedu Nwankwo', 'Engineering disciplines'),
            ('ENV', 'Faculty of Environmental Sciences', 'Prof. Amina Suleiman', 'Environmental studies'),
            ('LAW', 'Faculty of Law', 'Prof. David Williams', 'Legal studies and jurisprudence'),
            ('MGMT', 'Faculty of Management Sciences', 'Prof. Musa Garba', 'Business and management'),
            ('PHARM', 'Faculty of Pharmacy', 'Prof. Blessing Onwurah', 'Pharmaceutical sciences'),
            ('SCI', 'Faculty of Science', 'Prof. Ahmad Danbaki', 'Pure and applied sciences'),
            ('SOC', 'Faculty of Social Sciences', 'Prof. Folake Balogun', 'Social sciences and humanities'),
        ]

        created_count = 0
        for code, name, dean, description in faculties_data:
            faculty, created = Faculty.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'dean': dean,
                    'description': description,
                    'established_year': random.randint(1960, 1990)
                }
            )
            if created:
                created_count += 1

        self.stdout.write(f'Created {created_count} faculties')

    def create_departments(self):
        """Create UNILAG departments"""
        self.stdout.write('Creating departments...')

        departments_data = [
            # Faculty of Arts
            ('ENG', 'English Language', 'ARTS'),
            ('HIS', 'History', 'ARTS'),
            ('LIN', 'Linguistics', 'ARTS'),
            ('PHI', 'Philosophy', 'ARTS'),
            ('MUS', 'Creative Arts', 'ARTS'),

            # Faculty of Science
            ('CSC', 'Computer Science', 'SCI'),
            ('MAT', 'Mathematics', 'SCI'),
            ('PHY', 'Physics', 'SCI'),
            ('CHE', 'Chemistry', 'SCI'),
            ('BIO', 'Biology', 'SCI'),
            ('GEO', 'Geology', 'SCI'),
            ('STA', 'Statistics', 'SCI'),

            # Faculty of Engineering
            ('CVE', 'Civil Engineering', 'ENG'),
            ('EEE', 'Electrical/Electronics Engineering', 'ENG'),
            ('MEE', 'Mechanical Engineering', 'ENG'),
            ('CHM', 'Chemical Engineering', 'ENG'),
            ('SYE', 'Systems Engineering', 'ENG'),

            # Faculty of Management Sciences
            ('ACC', 'Accounting', 'MGMT'),
            ('BUS', 'Business Administration', 'MGMT'),
            ('FIN', 'Finance', 'MGMT'),
            ('MKT', 'Marketing', 'MGMT'),
            ('ACT', 'Actuarial Science', 'MGMT'),

            # Faculty of Social Sciences
            ('ECO', 'Economics', 'SOC'),
            ('POL', 'Political Science', 'SOC'),
            ('SOC', 'Sociology', 'SOC'),
            ('PSY', 'Psychology', 'SOC'),
            ('MCO', 'Mass Communication', 'SOC'),
            ('IRS', 'International Relations', 'SOC'),

            # Faculty of Law
            ('LAW', 'Law', 'LAW'),

            # Faculty of Education
            ('EDU', 'Education', 'EDU'),

            # Faculty of Basic Medical Sciences
            ('ANA', 'Anatomy', 'BMS'),
            ('PHY', 'Physiology', 'BMS'),
            ('BCH', 'Biochemistry', 'BMS'),

            # Faculty of Clinical Sciences
            ('MED', 'Medicine', 'CMS'),
            ('SUR', 'Surgery', 'CMS'),
            ('PED', 'Paediatrics', 'CMS'),

            # Faculty of Pharmacy
            ('PHM', 'Pharmacy', 'PHARM'),

            # Faculty of Dental Sciences
            ('DEN', 'Dentistry', 'DENT'),

            # Faculty of Environmental Sciences
            ('ARC', 'Architecture', 'ENV'),
            ('EST', 'Estate Management', 'ENV'),
            ('QSV', 'Quantity Surveying', 'ENV'),
            ('URP', 'Urban Planning', 'ENV'),
        ]

        created_count = 0
        for code, name, faculty_code in departments_data:
            try:
                faculty = Faculty.objects.get(code=faculty_code)
                department, created = Department.objects.get_or_create(
                    code=code,
                    defaults={
                        'name': name,
                        'faculty': faculty,
                        'hod': f'Dr. {random.choice(["Adebayo", "Chukwu", "Ibrahim", "Okafor", "Balogun"])} {random.choice(["Johnson", "Williams", "Mohammed", "Eze"])}',
                        'description': f'{name} department offering undergraduate and postgraduate programs',
                    }
                )
                if created:
                    created_count += 1
            except Faculty.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Faculty {faculty_code} not found for department {name}'))

        self.stdout.write(f'Created {created_count} departments')

    def create_academic_sessions(self):
        """Create UNILAG academic sessions"""
        self.stdout.write('Creating academic sessions...')

        sessions_data = [
            ('2020/2021', date(2020, 9, 1), date(2021, 9, 30), False),
            ('2021/2022', date(2021, 9, 1), date(2022, 9, 30), False),
            ('2022/2023', date(2022, 9, 1), date(2023, 9, 30), False),
            ('2023/2024', date(2023, 9, 1), date(2024, 9, 30), False),
            ('2024/2025', date(2024, 9, 1), date(2025, 9, 30), True),
        ]

        created_count = 0
        for name, start_date, end_date, is_current in sessions_data:
            session, created = AcademicSession.objects.get_or_create(
                name=name,
                defaults={
                    'start_date': start_date,
                    'end_date': end_date,
                    'is_current': is_current,
                }
            )
            if created:
                created_count += 1

        self.stdout.write(f'Created {created_count} academic sessions')

    def create_semesters(self):
        """Create semesters for each academic session"""
        self.stdout.write('Creating semesters...')

        sessions = AcademicSession.objects.all()
        created_count = 0

        for session in sessions:
            # First semester
            first_sem, created1 = Semester.objects.get_or_create(
                session=session,
                semester_number=1,
                defaults={
                    'start_date': session.start_date,
                    'end_date': date(session.start_date.year, 12, 31),
                    'is_current': session.is_current and True,
                }
            )

            # Second semester
            second_sem, created2 = Semester.objects.get_or_create(
                session=session,
                semester_number=2,
                defaults={
                    'start_date': date(session.end_date.year, 1, 15),
                    'end_date': session.end_date,
                    'is_current': session.is_current and False,
                }
            )

            if created1:
                created_count += 1
            if created2:
                created_count += 1

        self.stdout.write(f'Created {created_count} semesters')

    def create_courses(self):
        """Create UNILAG courses"""
        self.stdout.write('Creating courses...')

        courses_data = [
            # Computer Science courses
            ('CSC101', 'Introduction to Computer Science', 'CSC', 100, 3, 1, 'Basic concepts of computing'),
            ('CSC201', 'Data Structures and Algorithms', 'CSC', 200, 3, 1, 'CSC101'),
            ('CSC202', 'Object Oriented Programming', 'CSC', 200, 3, 2, 'CSC101'),
            ('CSC301', 'Database Management Systems', 'CSC', 300, 3, 1, 'CSC201'),
            ('CSC302', 'Software Engineering', 'CSC', 300, 3, 2, 'CSC202'),
            ('CSC401', 'Artificial Intelligence', 'CSC', 400, 3, 1, 'CSC301'),

            # Mathematics courses
            ('MAT101', 'Elementary Mathematics I', 'MAT', 100, 3, 1, 'Basic mathematics'),
            ('MAT102', 'Elementary Mathematics II', 'MAT', 100, 3, 2, 'MAT101'),
            ('MAT201', 'Linear Algebra', 'MAT', 200, 3, 1, 'MAT102'),
            ('MAT301', 'Real Analysis', 'MAT', 300, 3, 1, 'MAT201'),

            # Accounting courses
            ('ACC101', 'Principles of Accounting', 'ACC', 100, 3, 1, 'Basic accounting principles'),
            ('ACC201', 'Financial Accounting', 'ACC', 200, 3, 1, 'ACC101'),
            ('ACC301', 'Advanced Financial Accounting', 'ACC', 300, 3, 1, 'ACC201'),
            ('ACC401', 'Auditing and Assurance', 'ACC', 400, 3, 1, 'ACC301'),

            # Mass Communication courses
            ('MCO101', 'Introduction to Mass Communication', 'MCO', 100, 3, 1, 'Basic communication concepts'),
            ('MCO201', 'News Writing and Reporting', 'MCO', 200, 3, 1, 'MCO101'),
            ('MCO301', 'Broadcast Journalism', 'MCO', 300, 3, 1, 'MCO201'),

            # Law courses
            ('LAW101', 'Introduction to Nigerian Legal System', 'LAW', 100, 3, 1, 'Basic legal concepts'),
            ('LAW201', 'Constitutional Law', 'LAW', 200, 4, 1, 'LAW101'),
            ('LAW301', 'Criminal Law', 'LAW', 300, 4, 1, 'LAW201'),

            # Medicine courses (Basic Medical Sciences)
            ('MED101', 'Human Anatomy I', 'MED', 100, 4, 1, 'Basic anatomy'),
            ('MED102', 'Human Physiology I', 'MED', 100, 4, 2, 'Basic physiology'),
            ('MED201', 'Pathology', 'MED', 200, 4, 1, 'MED101,MED102'),

            # Engineering courses
            ('EEE101', 'Circuit Analysis I', 'EEE', 100, 3, 1, 'Basic electrical circuits'),
            ('EEE201', 'Circuit Analysis II', 'EEE', 200, 3, 1, 'EEE101'),
            ('CVE101', 'Engineering Drawing', 'CVE', 100, 2, 1, 'Basic engineering drawing'),
            ('MEE101', 'Engineering Mechanics', 'MEE', 100, 3, 1, 'Basic mechanics'),

            # Economics courses
            ('ECO101', 'Principles of Economics I', 'ECO', 100, 3, 1, 'Basic economic principles'),
            ('ECO102', 'Principles of Economics II', 'ECO', 100, 3, 2, 'ECO101'),
            ('ECO201', 'Microeconomics', 'ECO', 200, 3, 1, 'ECO102'),
            ('ECO202', 'Macroeconomics', 'ECO', 200, 3, 2, 'ECO102'),

            # English courses
            ('ENG101', 'Use of English I', 'ENG', 100, 2, 1, 'Basic English usage'),
            ('ENG102', 'Use of English II', 'ENG', 100, 2, 2, 'ENG101'),
            ('ENG201', 'Introduction to Literature', 'ENG', 200, 3, 1, 'ENG102'),
            ('ENG301', 'African Literature', 'ENG', 300, 3, 1, 'ENG201'),

            # General Studies (University-wide)
            ('GST101', 'Use of English and Communication Skills I', 'GST', 100, 2, 1, 'General studies'),
            ('GST102', 'Use of English and Communication Skills II', 'GST', 100, 2, 2, 'GST101'),
            ('GST201', 'Nigerian Peoples and Culture', 'GST', 200, 2, 1, 'General studies'),
            ('GST301', 'Entrepreneurship Studies', 'GST', 300, 2, 1, 'General studies'),
        ]

        created_count = 0
        for code, title, dept_code, level, credits, semester, prerequisites_str in courses_data:
            try:
                # Get or create department for General Studies
                if dept_code == 'GST':
                    department, _ = Department.objects.get_or_create(
                        code='GST',
                        defaults={
                            'name': 'General Studies',
                            'faculty': Faculty.objects.first(),  # Assign to first faculty
                            'description': 'General Studies courses for all students'
                        }
                    )
                else:
                    department = Department.objects.get(code=dept_code)

                course, created = Course.objects.get_or_create(
                    code=code,
                    defaults={
                        'title': title,
                        'department': department,
                        'level': level,
                        'credits': credits,
                        'description': f'{title} - {level} level course',
                        'is_active': True
                    }
                )

                # Set prerequisites after creation
                if created and prerequisites_str and prerequisites_str != 'Basic concepts of computing':
                    prerequisite_codes = [code.strip() for code in prerequisites_str.split(',')]
                    for prereq_code in prerequisite_codes:
                        try:
                            prereq_course = Course.objects.get(code=prereq_code)
                            course.prerequisites.add(prereq_course)
                        except Course.DoesNotExist:
                            pass

                if created:
                    created_count += 1

            except Department.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Department {dept_code} not found for course {code}'))
                continue

        self.stdout.write(f'Created {created_count} courses')

    def create_users_and_students(self):
        """Create UNILAG users and students"""
        self.stdout.write(f'Creating {self.student_count} users and students...')

        # Realistic UNILAG student data with Nigerian names
        student_templates = [
            ('Adeyemi', 'Olumide', 'Tunde', 'CSC', 'M'),
            ('Okafor', 'Chioma', 'Grace', 'CSC', 'F'),
            ('Ibrahim', 'Fatima', 'Aisha', 'MAT', 'F'),
            ('Williams', 'David', 'Emeka', 'EEE', 'M'),
            ('Balogun', 'Khadijah', 'Monsurat', 'ACC', 'F'),
            ('Eze', 'Chukwuemeka', 'Daniel', 'ACC', 'M'),
            ('Adebayo', 'Temitope', 'Folake', 'ECO', 'F'),
            ('Suleiman', 'Amina', 'Halima', 'MCO', 'F'),
            ('Okoro', 'Kingsley', 'Chinedu', 'LAW', 'M'),
            ('Lawal', 'Mariam', 'Abosede', 'BUS', 'F'),
            ('Danbaki', 'Ahmad', 'Musa', 'ENG', 'M'),
            ('Onwurah', 'Blessing', 'Chinelo', 'PHY', 'F'),
            ('Yusuf', 'Zainab', 'Hauwa', 'CHE', 'F'),
            ('Nwankwo', 'Chineye', 'Ifeoma', 'LAW', 'F'),
            ('Abdullahi', 'Umar', 'Sadiq', 'POL', 'M'),
            ('Ogundimu', 'Ayomide', 'Titilope', 'PSY', 'F'),
            ('Emeka', 'Justice', 'Chukwudi', 'SOC', 'M'),
            ('Bello', 'Safiyyah', 'Khadija', 'HIS', 'F'),
            ('Okolie', 'Chukwuma', 'Anthony', 'MED', 'M'),
            ('Adebisi', 'Folashade', 'Omolara', 'MED', 'F'),
        ]

        # Get available data
        departments = list(Department.objects.all())
        sessions = list(AcademicSession.objects.all())
        current_session = AcademicSession.objects.filter(is_current=True).first()

        nigerian_states = [
            'Lagos', 'Kano', 'Rivers', 'Kaduna', 'Oyo', 'Delta', 'Anambra', 'Sokoto',
            'Kwara', 'Ogun', 'Osun', 'Ondo', 'Ekiti', 'Enugu', 'Abia', 'Imo'
        ]

        created_count = 0
        for i in range(self.student_count):
            try:
                # Select template and modify for uniqueness
                template_idx = i % len(student_templates)
                last_name, first_name, middle_name, preferred_dept, gender = student_templates[template_idx]

                # Add variation for uniqueness
                variation = f"{i // len(student_templates) + 1}" if i >= len(student_templates) else ""
                unique_first_name = f"{first_name}{variation}" if variation else first_name

                # Get department
                try:
                    department = Department.objects.get(code=preferred_dept)
                except Department.DoesNotExist:
                    department = random.choice(departments)

                # Academic details
                current_year = 2024
                levels = [100, 200, 300, 400]
                weights = [0.3, 0.3, 0.25, 0.15]
                current_level = random.choices(levels, weights=weights)[0]

                # Entry session
                years_in_uni = (current_level // 100)
                entry_year = current_year - years_in_uni + 1
                entry_session_name = f"{entry_year - 1}/{entry_year}"

                try:
                    entry_session = AcademicSession.objects.get(name=entry_session_name)
                except AcademicSession.DoesNotExist:
                    entry_session = random.choice(sessions)

                # Create unique email and username
                base_email = f"{unique_first_name.lower()}.{last_name.lower()}{i + 1}@student.unilag.edu.ng"
                username = f"{unique_first_name.lower()}.{last_name.lower()}{i + 1}"

                # Create user
                user = CustomUser.objects.create_user(
                    email=base_email,
                    password='Test12ad346@28',
                    first_name=unique_first_name,
                    last_name=last_name,
                    user_type='student',
                    user_id=username
                )

                # Create student details
                birth_year = entry_year - random.randint(17, 22)
                birth_date = date(birth_year, random.randint(1, 12), random.randint(1, 28))

                phone_prefixes = ['0803', '0806', '0813', '0816', '0703', '0706']
                phone = f"{random.choice(phone_prefixes)}{random.randint(1000000, 9999999)}"

                guardian_names = [
                    'Mr. Adebayo Johnson', 'Mrs. Fatima Ibrahim', 'Chief Samuel Okafor',
                    'Dr. Amina Mohammed', 'Engr. Peter Nwankwo', 'Mrs. Kemi Adeyemi'
                ]

                # Create student
                student = Student.objects.create(
                    user=user,
                    faculty=department.faculty,
                    department=department,
                    current_level=current_level,
                    entry_session=entry_session,
                    current_session=current_session or entry_session,
                    mode_of_entry=random.choices(
                        ['UTME', 'DIRECT', 'TRANSFER', 'PRE_DEGREE'],
                        weights=[0.7, 0.15, 0.1, 0.05]
                    )[0],
                    student_type=random.choices(
                        ['REGULAR', 'PART_TIME', 'SANDWICH'],
                        weights=[0.85, 0.1, 0.05]
                    )[0],
                    middle_name=middle_name,
                    date_of_birth=birth_date,
                    gender=gender,
                    state_of_origin=random.choice(nigerian_states),
                    address=self.generate_address(),
                    phone_number=phone,
                    guardian_name=random.choice(guardian_names),
                    guardian_phone=f"{random.choice(phone_prefixes)}{random.randint(1000000, 9999999)}",
                    guardian_relationship=random.choice(['Father', 'Mother', 'Uncle', 'Aunt']),
                    status='ACTIVE'
                )

                created_count += 1

                if created_count % 25 == 0:
                    self.stdout.write(f'Created {created_count} students...')

            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Error creating student {i + 1}: {e}'))
                continue

        self.stdout.write(f'Created {created_count} users and students')

    def generate_address(self):
        """Generate realistic Lagos addresses"""
        areas = [
            'Yaba, Lagos', 'Surulere, Lagos', 'Ikeja, Lagos', 'Victoria Island, Lagos',
            'Lekki, Lagos', 'Ikorodu, Lagos', 'Alaba, Lagos', 'Mushin, Lagos',
            'Gbagada, Lagos', 'Maryland, Lagos', 'Festac Town, Lagos', 'Isolo, Lagos'
        ]
        return f"{random.randint(1, 100)} {random.choice(areas)} State"

    def create_enrollments(self):
        """Create course enrollments for students"""
        self.stdout.write('Creating course enrollments...')

        students = Student.objects.filter(status='ACTIVE')
        current_semester = Semester.objects.filter(is_current=True).first()

        if not current_semester:
            current_semester = Semester.objects.first()

        created_count = 0
        for student in students:
            # Get courses for student's level and department
            dept_courses = Course.objects.filter(
                department=student.department,
                level=student.current_level,
                is_active=True
            )

            # Get general studies courses
            gst_courses = Course.objects.filter(
                department__code='GST',
                level=student.current_level,
                is_active=True
            )

            # Combine available courses
            available_courses = list(dept_courses) + list(gst_courses)

            # Enroll in 5-8 courses
            num_courses = min(random.randint(5, 8), len(available_courses))
            selected_courses = random.sample(available_courses, num_courses)

            for course in selected_courses:
                enrollment, created = Enrollment.objects.get_or_create(
                    student=student,
                    course=course,
                    semester=current_semester,
                    defaults={
                        'status': 'ENROLLED',
                        'enrollment_date': current_semester.start_date
                    }
                )
                if created:
                    created_count += 1

        self.stdout.write(f'Created {created_count} enrollments')

    def create_results(self):
        """Create academic results for students"""
        self.stdout.write('Creating academic results...')

        students = Student.objects.filter(status='ACTIVE')
        past_semesters = Semester.objects.exclude(is_current=True)[:8]  # Last 8 semesters

        created_count = 0
        for student in students:
            for semester in past_semesters:
                # Determine if student was enrolled in this semester
                semester_level = self.get_student_level_for_semester(student, semester)
                if semester_level <= 0 or semester_level > student.current_level:
                    continue

                # Get courses for that level
                courses = Course.objects.filter(
                    department=student.department,
                    level=semester_level,
                    is_active=True
                )[:random.randint(4, 7)]

                for course in courses:
                    # Create enrollment record
                    enrollment, _ = Enrollment.objects.get_or_create(
                        student=student,
                        course=course,
                        semester=semester,
                        defaults={
                            'status': 'COMPLETED',
                            'enrollment_date': semester.start_date
                        }
                    )

                    # Create result
                    ca_score = round(random.uniform(10, 30), 2)
                    exam_score = round(random.uniform(20, 70), 2)

                    result, created = Result.objects.get_or_create(
                        student=student,
                        course=course,
                        semester=semester,
                        defaults={
                            'ca_score': Decimal(str(ca_score)),
                            'exam_score': Decimal(str(exam_score)),
                            'is_final': True,
                            'recorded_by': 'System Admin'
                        }
                    )

                    if created:
                        created_count += 1

        self.stdout.write(f'Created {created_count} results')

    def update_student_cgpa(self):
        """Calculate and update student CGPAs"""
        self.stdout.write('Updating student CGPAs...')

        students = Student.objects.filter(status='ACTIVE')
        updated_count = 0

        for student in students:
            try:
                # Calculate CGPA based on results
                results = Result.objects.filter(student=student, is_final=True)

                total_points = 0
                total_units = 0

                for result in results:
                    total_score = result.ca_score + result.exam_score
                    grade_point = self.get_grade_point_from_score(total_score)

                    if grade_point is not None:
                        total_points += grade_point * result.course.credits
                        total_units += result.course.credits

                if total_units > 0:
                    cgpa = round(total_points / total_units, 2)

                    # Determine academic standing
                    if cgpa >= 4.5:
                        standing = 'FIRST_CLASS'
                    elif cgpa >= 3.5:
                        standing = 'SECOND_CLASS_UPPER'
                    elif cgpa >= 2.5:
                        standing = 'SECOND_CLASS_LOWER'
                    elif cgpa >= 2.0:
                        standing = 'THIRD_CLASS'
                    else:
                        standing = 'PROBATION'

                    student.current_cgpa = Decimal(str(cgpa))
                    student.academic_standing = standing
                    student.total_credits_earned = total_units
                    student.save(update_fields=['current_cgpa', 'academic_standing', 'total_credits_earned'])

                    updated_count += 1

            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Error updating CGPA for {student}: {e}'))
                continue

        self.stdout.write(f'Updated CGPA for {updated_count} students')

        def get_student_level_for_semester(self, student, semester):
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

        def get_grade_point_from_score(self, total_score):
            """Convert total score to grade point (UNILAG system)"""
            if total_score >= 70:
                return 5.0  # A
            elif total_score >= 60:
                return 4.0  # B
            elif total_score >= 50:
                return 3.0  # C
            elif total_score >= 45:
                return 2.0  # D
            elif total_score >= 40:
                return 1.0  # E
            else:
                return 0.0  # F

        def generate_address(self):
            """Generate realistic Lagos/Nigerian addresses"""
            streets = [
                'Victoria Island', 'Ikeja GRA', 'Lekki Phase 1', 'Surulere',
                'Yaba', 'Maryland', 'Gbagada', 'Ikoyi', 'Ajah', 'Magodo',
                'Ogba', 'Isolo', 'Alaba', 'Festac Town', 'Anthony Village'
            ]

            return f"{random.randint(1, 50)} {random.choice(streets)}, Lagos State"

        def generate_student_id(self, entry_year, department_code, sequence):
            """Generate UNILAG student ID format"""
            year_code = str(entry_year)[-2:]  # Last 2 digits of year
            dept_code = department_code[:3].upper()

            # Get department numeric code
            dept_numeric = {
                'CSC': '04', 'MAT': '03', 'PHY': '02', 'CHE': '01', 'BIO': '05',
                'ACC': '01', 'ECO': '02', 'MGT': '03', 'BUS': '04', 'FIN': '05',
                'LAW': '01', 'MED': '01', 'ENG': '01', 'ARC': '01', 'MCO': '01'
            }.get(dept_code, '00')

            sequence_str = str(sequence).zfill(3)
            return f"{year_code}{dept_numeric}{sequence_str}"

    def get_grade_point_from_score(self, total_score):
        """Convert total score to grade point (UNILAG system)"""
        if total_score >= 70:
            return 5.0  # A
        elif total_score >= 60:
            return 4.0  # B
        elif total_score >= 50:
            return 3.0  # C
        elif total_score >= 45:
            return 2.0  # D
        elif total_score >= 40:
            return 1.0  # E
        else:
            return 0.0  # F

    def get_student_level_for_semester(self, student, semester):
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
