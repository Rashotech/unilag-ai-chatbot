from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal
import random
from datetime import date
from django.db import transaction

from mit_chatbot.models import AcademicSession, Department, Student

User = get_user_model()


class Command(BaseCommand):
    help = 'Populate database with UNILAG student dummy data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=50,
            help='Number of students to create (default: 50)',
        )

    def handle(self, *args, **options):
        student_count = options['count']
        self.stdout.write(f'Creating {student_count} UNILAG students...')

        try:
            with transaction.atomic():
                self.create_unilag_students(student_count)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating students: {e}'))
            return

        self.stdout.write(self.style.SUCCESS('Successfully populated UNILAG student data'))

    def create_unilag_students(self, count):
        """Create realistic UNILAG students with proper Nigerian names"""

        # Realistic UNILAG student data with Nigerian names
        student_templates = [
            # Computer Science Students
            ('Adeyemi', 'Olumide', 'Tunde', 'oadeyemi@student.unilag.edu.ng', 'CSC', 'M', 'Lagos'),
            ('Okafor', 'Chioma', 'Grace', 'cokafor@student.unilag.edu.ng', 'CSC', 'F', 'Anambra'),
            ('Ibrahim', 'Fatima', 'Aisha', 'fibrahim@student.unilag.edu.ng', 'CSC', 'F', 'Kano'),
            ('Williams', 'David', 'Emeka', 'dwilliams@student.unilag.edu.ng', 'CSC', 'M', 'Rivers'),
            ('Balogun', 'Khadijah', 'Monsurat', 'kbalogun@student.unilag.edu.ng', 'CSC', 'F', 'Oyo'),

            # Accounting Students
            ('Eze', 'Chukwuemeka', 'Daniel', 'ceze@student.unilag.edu.ng', 'ACC', 'M', 'Enugu'),
            ('Adebayo', 'Temitope', 'Folake', 'tadebayo@student.unilag.edu.ng', 'ACC', 'F', 'Osun'),
            ('Suleiman', 'Amina', 'Halima', 'asuleiman@student.unilag.edu.ng', 'ACC', 'F', 'Sokoto'),
            ('Okoro', 'Kingsley', 'Chinedu', 'kokoro@student.unilag.edu.ng', 'ACC', 'M', 'Imo'),
            ('Lawal', 'Mariam', 'Abosede', 'mlawal@student.unilag.edu.ng', 'ACC', 'F', 'Kwara'),

            # Mass Communication Students
            ('Danbaki', 'Ahmad', 'Musa', 'adanbaki@student.unilag.edu.ng', 'MCO', 'M', 'Kaduna'),
            ('Onwurah', 'Blessing', 'Chinelo', 'bonwurah@student.unilag.edu.ng', 'MCO', 'F', 'Delta'),
            ('Yusuf', 'Zainab', 'Hauwa', 'zyusuf@student.unilag.edu.ng', 'MCO', 'F', 'Katsina'),
            ('Ogbonnaya', 'Victor', 'Ikechukwu', 'vogbonnaya@student.unilag.edu.ng', 'MCO', 'M', 'Abia'),
            ('Adeyinka', 'Funmilayo', 'Adeola', 'fadeyinka@student.unilag.edu.ng', 'MCO', 'F', 'Ogun'),

            # Law Students
            ('Nwankwo', 'Chineye', 'Ifeoma', 'cnwankwo@student.unilag.edu.ng', 'LAW', 'F', 'Anambra'),
            ('Abdullahi', 'Umar', 'Sadiq', 'uabdullahi@student.unilag.edu.ng', 'LAW', 'M', 'Zamfara'),
            ('Ogundimu', 'Ayomide', 'Titilope', 'aogundimu@student.unilag.edu.ng', 'LAW', 'F', 'Lagos'),
            ('Emeka', 'Justice', 'Chukwudi', 'jemeka@student.unilag.edu.ng', 'LAW', 'M', 'Ebonyi'),
            ('Bello', 'Safiyyah', 'Khadija', 'sbello@student.unilag.edu.ng', 'LAW', 'F', 'Niger'),

            # Medicine Students
            ('Okolie', 'Chukwuma', 'Anthony', 'cokolie@student.unilag.edu.ng', 'MED', 'M', 'Delta'),
            ('Adebisi', 'Folashade', 'Omolara', 'fadebisi@student.unilag.edu.ng', 'MED', 'F', 'Osun'),
            ('Mohammed', 'Aliyu', 'Ibrahim', 'amohammed@student.unilag.edu.ng', 'MED', 'M', 'Bauchi'),
            ('Nwachukwu', 'Ugochi', 'Amarachi', 'unwachukwu@student.unilag.edu.ng', 'MED', 'F', 'Imo'),
            ('Oladele', 'Bamidele', 'Adekunle', 'boladele@student.unilag.edu.ng', 'MED', 'M', 'Ekiti'),

            # Engineering Students
            ('Chukwu', 'Michael', 'Obinna', 'mchukwu@student.unilag.edu.ng', 'EEE', 'M', 'Enugu'),
            ('Adamu', 'Salamatu', 'Hadiza', 'sadamu@student.unilag.edu.ng', 'EEE', 'F', 'Yobe'),
            ('Onyekwelu', 'Precious', 'Chiamaka', 'ponyekwelu@student.unilag.edu.ng', 'CVE', 'F', 'Anambra'),
            ('Garba', 'Abdulrazaq', 'Shehu', 'agarba@student.unilag.edu.ng', 'MEE', 'M', 'Kebbi'),
            ('Afolabi', 'Tolani', 'Bukola', 'tafolabi@student.unilag.edu.ng', 'CHE', 'F', 'Ondo'),

            # Physics Students
            ('Ikechukwu', 'Samuel', 'Chuka', 'sikechukwu@student.unilag.edu.ng', 'PHY', 'M', 'Abia'),
            ('Aliyu', 'Maimuna', 'Fatima', 'maliyu@student.unilag.edu.ng', 'PHY', 'F', 'Jigawa'),
            ('Ogundipe', 'Oluwaseun', 'Adebayo', 'oogundipe@student.unilag.edu.ng', 'PHY', 'M', 'Ogun'),
            ('Nduka', 'Rita', 'Chinyere', 'rnduka@student.unilag.edu.ng', 'PHY', 'F', 'Rivers'),
            ('Hassan', 'Ibrahim', 'Yusuf', 'ihassan@student.unilag.edu.ng', 'PHY', 'M', 'Gombe'),

            # Economics Students
            ('Olaleye', 'Adunni', 'Abosede', 'aolaleye@student.unilag.edu.ng', 'ECO', 'F', 'Lagos'),
            ('Uche', 'Franklin', 'Nnamdi', 'fuche@student.unilag.edu.ng', 'ECO', 'M', 'Anambra'),
            ('Dauda', 'Rahmat', 'Aisha', 'rdauda@student.unilag.edu.ng', 'ECO', 'F', 'Kwara'),
            ('Emeka', 'Daniel', 'Chibueze', 'demeka@student.unilag.edu.ng', 'ECO', 'M', 'Imo'),
            ('Adeyemi', 'Morenikeji', 'Yetunde', 'madeyemi@student.unilag.edu.ng', 'ECO', 'F', 'Oyo'),

            # English Students
            ('Obiora', 'Gift', 'Chioma', 'gobiora@student.unilag.edu.ng', 'ENG', 'F', 'Anambra'),
            ('Musa', 'Yakubu', 'Ahmad', 'ymusa@student.unilag.edu.ng', 'ENG', 'M', 'Plateau'),
            ('Adebayo', 'Omolola', 'Funmilola', 'oadebayo@student.unilag.edu.ng', 'ENG', 'F', 'Ekiti'),
            ('Nwosu', 'Chidubem', 'Kelechi', 'cnwosu@student.unilag.edu.ng', 'ENG', 'M', 'Imo'),
            ('Saliu', 'Abiola', 'Monsurat', 'asaliu@student.unilag.edu.ng', 'ENG', 'F', 'Lagos'),
        ]

        created_count = 0
        current_session = AcademicSession.objects.filter(is_current=True).first()
        if not current_session:
            current_session = AcademicSession.objects.first()

        # Get all available departments for random assignment
        departments = list(Department.objects.all())
        available_sessions = list(AcademicSession.objects.all()[:5])  # Last 5 sessions

        # Nigerian states for random selection
        nigerian_states = [
            'Lagos', 'Kano', 'Rivers', 'Kaduna', 'Oyo', 'Delta', 'Anambra', 'Sokoto',
            'Kwara', 'Ogun', 'Osun', 'Ondo', 'Ekiti', 'Enugu', 'Abia', 'Imo',
            'Ebonyi', 'Cross River', 'Akwa Ibom', 'Bayelsa', 'Edo', 'Niger',
            'Kogi', 'Benue', 'Plateau', 'Nasarawa', 'Taraba', 'Adamawa',
            'Bauchi', 'Gombe', 'Yobe', 'Borno', 'Jigawa', 'Katsina',
            'Zamfara', 'Kebbi', 'Sokoto', 'FCT'
        ]

        # Create students using templates multiple times to reach desired count
        for i in range(count):
            template_index = i % len(student_templates)
            last_name, first_name, middle_name, base_email, dept_code, gender, state = student_templates[template_index]

            # Modify names slightly for variety
            variation_suffix = f"{i // len(student_templates) + 1}" if i >= len(student_templates) else ""
            modified_first_name = f"{first_name}{variation_suffix}" if variation_suffix else first_name
            modified_email = base_email.replace('@', f"{variation_suffix}@") if variation_suffix else base_email

            try:
                # Get or create department
                try:
                    department = Department.objects.get(code=dept_code)
                except Department.DoesNotExist:
                    # If specific department doesn't exist, use a random one
                    department = random.choice(departments)
                    dept_code = department.code

                # Create academic progression
                current_year = 2024
                levels = [100, 200, 300, 400]
                weights = [0.3, 0.3, 0.25, 0.15]  # More students in lower levels
                current_level = random.choices(levels, weights=weights)[0]

                # Determine entry session
                years_in_uni = (current_level // 100)
                entry_year = current_year - years_in_uni + 1
                entry_session_name = f"{entry_year - 1}/{entry_year}"

                try:
                    entry_session = AcademicSession.objects.get(name=entry_session_name)
                except AcademicSession.DoesNotExist:
                    entry_session = random.choice(available_sessions)

                # Create email and username with proper variation
                email_prefix = modified_email.split('@')[0]
                username = f"{email_prefix}"
                email = modified_email

                # Ensure unique username
                counter = 1
                original_username = username
                while User.objects.filter(username=username).exists():
                    username = f"{original_username}{counter}"
                    counter += 1

                # Ensure unique email
                counter = 1
                original_email = email
                while User.objects.filter(email=email).exists():
                    email_parts = original_email.split('@')
                    email = f"{email_parts[0]}{counter}@{email_parts[1]}"
                    counter += 1

                # Create user
                user = User.objects.create_user(
                    email=email,
                    password='student123',  # Default password
                    first_name=modified_first_name,
                    last_name=last_name,
                    user_type='student'
                )

                # Create realistic birth date
                birth_year = entry_year - random.randint(17, 22)  # 17-22 years old at entry
                birth_date = date(
                    birth_year,
                    random.randint(1, 12),
                    random.randint(1, 28)
                )

                # Generate phone number
                phone_prefixes = ['0803', '0806', '0813', '0816', '0703', '0706', '0708', '0802', '0808', '0812']
                phone_number = f"{random.choice(phone_prefixes)}{random.randint(1000000, 9999999)}"

                # Generate guardian information
                guardian_names = [
                    'Mr. Adebayo Johnson', 'Mrs. Fatima Ibrahim', 'Chief Samuel Okafor',
                    'Dr. Amina Mohammed', 'Engr. Peter Nwankwo', 'Mrs. Kemi Adeyemi',
                    'Alhaji Musa Garba', 'Prof. Grace Okolie', 'Barr. David Williams',
                    'Mrs. Folake Balogun', 'Mr. Chinedu Eze', 'Dr. Halima Suleiman'
                ]
                guardian_phone = f"{random.choice(phone_prefixes)}{random.randint(1000000, 9999999)}"

                # Create student profile
                student = Student.objects.create(
                    user=user,
                    faculty=department.faculty,
                    department=department,
                    current_level=current_level,
                    entry_session=entry_session,
                    current_session=current_session,
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
                    address=self.generate_nigerian_address(),
                    phone_number=phone_number,
                    guardian_name=random.choice(guardian_names),
                    guardian_phone=guardian_phone,
                    guardian_relationship=random.choice(['Father', 'Mother', 'Uncle', 'Aunt', 'Guardian']),
                    status='ACTIVE',
                    graduation_status='IN_PROGRESS' if current_level < 400 else random.choices(
                        ['IN_PROGRESS', 'GRADUATED'], weights=[0.6, 0.4]
                    )[0]
                )

                # Generate realistic CGPA based on level
                if current_level == 100:
                    cgpa = round(random.uniform(2.5, 4.8), 2)
                elif current_level == 200:
                    cgpa = round(random.uniform(2.3, 4.7), 2)
                elif current_level == 300:
                    cgpa = round(random.uniform(2.1, 4.6), 2)
                else:  # 400 level
                    cgpa = round(random.uniform(2.0, 4.5), 2)

                # Set academic standing based on CGPA
                if cgpa >= 4.5:
                    academic_standing = 'FIRST_CLASS'
                elif cgpa >= 3.5:
                    academic_standing = 'SECOND_CLASS_UPPER'
                elif cgpa >= 2.5:
                    academic_standing = 'SECOND_CLASS_LOWER'
                elif cgpa >= 2.0:
                    academic_standing = 'THIRD_CLASS'
                else:
                    academic_standing = 'PROBATION'

                student.current_cgpa = Decimal(str(cgpa))
                student.academic_standing = academic_standing
                student.total_credits_earned = (current_level // 100) * random.randint(15, 25)
                student.save()

                created_count += 1

                if created_count % 25 == 0:
                    self.stdout.write(f'Created {created_count} students...')

            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'Error creating student {i + 1}: {e}')
                )
                continue

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} UNILAG students')
        )

    def generate_nigerian_address(self):
        """Generate realistic Nigerian addresses"""
        streets = [
            'Allen Avenue', 'Victoria Island', 'Ikorodu Road', 'Surulere Street',
            'Ikeja GRA', 'Yaba Road', 'Akoka Estate', 'Maryland', 'Ojuelegba',
            'Mushin Road', 'Agege Motor Road', 'Oshodi Express', 'Alaba Market Road',
            'Festac Town', 'Satellite Town', 'Ago Palace Way', 'College Road',
            'University Road', 'Stadium Road', 'Hospital Road', 'Church Street',
            'Market Street', 'School Road', 'Government Avenue', 'Independence Way'
        ]

        areas = [
            'Lagos', 'Ikeja', 'Surulere', 'Yaba', 'Victoria Island', 'Ikoyi',
            'Maryland', 'Mushin', 'Oshodi', 'Agege', 'Alaba', 'Festac',
            'Satellite Town', 'Gbagada', 'Ketu', 'Mile 2', 'Ojo', 'Badagry'
        ]

        return f"{random.randint(1, 999)} {random.choice(streets)}, {random.choice(areas)}, Lagos State"