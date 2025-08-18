import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager, UserManager


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    USER_TYPE_CHOICES = [
        ('admin', 'Administrator'),
        ('staff', 'Staff Member'),
        ('student', 'Student'),
    ]

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='student')
    department = models.CharField(max_length=100, blank=True)
    user_id = models.CharField(max_length=50, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)

    # Django required fields
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    # Timestamps
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Profile fields
    profile_picture = models.URLField(blank=True, null=True)
    bio = models.TextField(blank=True)
    preferences = models.JSONField(default=dict, blank=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    # Fix the reverse accessor conflicts
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='custom_user_set',  # Changed from default 'user_set'
        related_query_name='custom_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='custom_user_set',  # Changed from default 'user_set'
        related_query_name='custom_user',
    )

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        return self.first_name

    @property
    def is_admin(self):
        return self.user_type == 'admin' or self.is_superuser

    @property
    def can_manage_documents(self):
        return self.user_type in ['admin', 'staff'] or self.is_staff


class Document(models.Model):
    DOCUMENT_TYPES = [
        ('policy', 'Policy Document'),
        ('handbook', 'Student Handbook'),
        ('course', 'Course Information'),
        ('procedure', 'Procedure Guide'),
        ('faq', 'FAQ Document'),
        ('regulation', 'Regulation Document'),
        ('form', 'Form Template'),
        ('announcement', 'Announcement'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    title = models.CharField(max_length=255)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    description = models.TextField(blank=True, null=True)
    tags = models.CharField(max_length=500, blank=True, null=True, help_text="Comma-separated tags")

    # Firebase storage fields
    firebase_url = models.URLField(blank=True, null=True)
    firebase_path = models.CharField(max_length=500, blank=True, null=True)
    file_size = models.BigIntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True, null=True)

    # Extracted content
    extracted_text = models.TextField(blank=True, null=True)
    extraction_metadata = models.JSONField(default=dict)  # Tika metadata

    # Status fields
    is_active = models.BooleanField(default=True)
    processing_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], default='pending')
    error_message = models.TextField(blank=True, null=True)
    source_url = models.URLField(blank=True, null=True, help_text="URL to extract content from")

    # Audit fields
    uploaded_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    # Search and indexing
    vector_indexed = models.BooleanField(default=False)
    index_version = models.IntegerField(default=1)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.title} ({self.document_type})"

    @property
    def file_size_mb(self):
        return round(self.file_size / (1024 * 1024), 2) if self.file_size else 0

    def get_extraction_summary(self):
        """Get a summary of extraction metadata"""
        if not self.extraction_metadata:
            return {}

        return {
            'pages': self.extraction_metadata.get('xmpTPg:NPages', 'N/A'),
            'author': self.extraction_metadata.get('meta:author', 'N/A'),
            'creation_date': self.extraction_metadata.get('meta:creation-date', 'N/A'),
            'content_type': self.extraction_metadata.get('Content-Type', 'N/A'),
            'word_count': len(self.extracted_text.split()) if self.extracted_text else 0,
        }

    def get_tags_list(self):
        """Return tags as a list"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return []

    def set_tags_from_list(self, tag_list):
        """Set tags from a list"""
        if tag_list:
            self.tags = ', '.join(tag_list)
        else:
            self.tags = ''


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    session_id = models.CharField(max_length=100, blank=True, null=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    context = models.JSONField(default=dict, blank=True)  # Store conversation context
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        user_id = self.user.user_id if self.user else f"Session:{self.session_id[:8]}"
        return f"Conversation {user_id} - {self.started_at.strftime('%Y-%m-%d %H:%M')}"

    def get_message_count(self):
        return self.messages.count()

    def get_duration(self):
        if self.ended_at:
            return self.ended_at - self.started_at
        return timezone.now() - self.started_at


class Message(models.Model):
    MESSAGE_TYPES = [
        ('user', 'User Message'),
        ('bot', 'Bot Response'),
        ('system', 'System Message'),
    ]

    RATING_CHOICES = [
        (1, 'Poor'),
        (2, 'Good'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)  # Intent, confidence, etc.
    timestamp = models.DateTimeField(auto_now_add=True)
    rating = models.IntegerField(choices=RATING_CHOICES, null=True, blank=True)
    response_time = models.FloatField(null=True, blank=True)  # Response time in seconds

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.message_type}: {self.content[:50]}..."


class MessageSource(models.Model):
    """Documents that were used as sources for a bot response"""
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='sources')
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    relevance_score = models.FloatField(default=0.0)
    chunk_content = models.TextField(blank=True)  # The specific chunk used
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Source: {self.document.title} for {self.message.id}"


class EscalationTicket(models.Model):
    STATUS_CHOICES = [
        ('new', 'New'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    assigned_staff = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    subject = models.CharField(max_length=255)
    description = models.TextField()
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True, related_name='created_tickets')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Ticket #{self.id} - {self.subject}"


class SystemAnalytics(models.Model):
    """Track system usage and performance metrics"""
    date = models.DateField(unique=True)
    total_conversations = models.IntegerField(default=0)
    total_messages = models.IntegerField(default=0)
    avg_response_time = models.FloatField(default=0.0)
    successful_queries = models.IntegerField(default=0)
    escalated_queries = models.IntegerField(default=0)
    user_satisfaction = models.FloatField(default=0.0)  # Average rating
    popular_topics = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Analytics for {self.date}"


class Faculty(models.Model):
    """UNILAG Faculty Model"""
    code = models.CharField(max_length=10, unique=True)  # e.g., 'FSCI'
    name = models.CharField(max_length=200)  # e.g., 'Faculty of Science'
    description = models.TextField(blank=True)
    dean = models.CharField(max_length=200, blank=True)
    established_year = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Faculties"

    def __str__(self):
        return f"{self.code} - {self.name}"


class Department(models.Model):
    """UNILAG Department Model"""
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name='departments')
    code = models.CharField(max_length=10, unique=True)  # e.g., 'CSC'
    name = models.CharField(max_length=200)  # e.g., 'Computer Science'
    description = models.TextField(blank=True)
    hod = models.CharField(max_length=200, blank=True)  # Head of Department
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} - {self.name}"


class AcademicSession(models.Model):
    """Academic Session Model (e.g., 2023/2024)"""
    name = models.CharField(max_length=20, unique=True)  # e.g., "2023/2024"
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_current:
            # Ensure only one current session
            AcademicSession.objects.filter(is_current=True).update(is_current=False)
        super().save(*args, **kwargs)


class Semester(models.Model):
    """Semester Model"""
    SEMESTER_CHOICES = [
        (1, 'First Semester'),
        (2, 'Second Semester'),
    ]

    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name='semesters')
    semester_number = models.IntegerField(choices=SEMESTER_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['session', 'semester_number']
        ordering = ['-session__start_date', 'semester_number']

    def __str__(self):
        return f"{self.session.name} - {self.get_semester_number_display()}"

    def save(self, *args, **kwargs):
        if self.is_current:
            # Ensure only one current semester
            Semester.objects.filter(is_current=True).update(is_current=False)
        super().save(*args, **kwargs)


class Course(models.Model):
    """Course Model"""
    COURSE_TYPES = [
        ('CORE', 'Core Course'),
        ('ELECTIVE', 'Elective Course'),
        ('GENERAL', 'General Studies'),
        ('PRACTICAL', 'Practical Course'),
    ]

    code = models.CharField(max_length=10, unique=True)  # e.g., 'CSC301'
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    credits = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(6)])
    level = models.IntegerField(choices=[(100, '100'), (200, '200'), (300, '300'), (400, '400'), (500, '500')])
    course_type = models.CharField(max_length=20, choices=COURSE_TYPES, default='CORE')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='courses')
    prerequisites = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='prerequisite_for')
    lecturer = models.CharField(max_length=200, blank=True)
    has_practical = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.title}"


class Student(models.Model):
    """Student Profile Model - Extends CustomUser"""
    LEVEL_CHOICES = [
        (100, '100 Level'),
        (200, '200 Level'),
        (300, '300 Level'),
        (400, '400 Level'),
        (500, '500 Level'),
    ]

    ENTRY_MODE_CHOICES = [
        ('DIRECT', 'Direct Entry'),
        ('UTME', 'UTME'),
        ('TRANSFER', 'Transfer'),
        ('PRE_DEGREE', 'Pre-Degree'),
    ]

    STUDENT_TYPE_CHOICES = [
        ('REGULAR', 'Regular'),
        ('PART_TIME', 'Part-Time'),
        ('SANDWICH', 'Sandwich'),
    ]

    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspended'),
        ('GRADUATED', 'Graduated'),
        ('WITHDRAWN', 'Withdrawn'),
        ('DEFERRED', 'Deferred'),
    ]

    GRADUATION_STATUS_CHOICES = [
        ('IN_PROGRESS', 'In Progress'),
        ('GRADUATED', 'Graduated'),
        ('WITHDRAWN', 'Withdrawn'),
    ]

    ACADEMIC_STANDING_CHOICES = [
        ('EXCELLENT', 'Excellent'),
        ('VERY_GOOD', 'Very Good'),
        ('GOOD', 'Good'),
        ('SATISFACTORY', 'Satisfactory'),
        ('PROBATION', 'Probation'),
        ('FIRST_CLASS', 'First Class'),
        ('SECOND_CLASS_UPPER', 'Second Class Upper'),
        ('SECOND_CLASS_LOWER', 'Second Class Lower'),
        ('THIRD_CLASS', 'Third Class'),
    ]

    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]

    # Primary Information
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.CharField(max_length=20, unique=True)  # e.g., 2020CSC001

    # Academic Information
    faculty = models.ForeignKey(Faculty, on_delete=models.PROTECT, related_name='students')
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='students')
    current_level = models.IntegerField(choices=LEVEL_CHOICES, default=100)
    entry_session = models.ForeignKey(AcademicSession, on_delete=models.PROTECT, related_name='entry_students')
    current_session = models.ForeignKey(AcademicSession, on_delete=models.PROTECT, related_name='current_students')
    mode_of_entry = models.CharField(max_length=20, choices=ENTRY_MODE_CHOICES, default='UTME')
    student_type = models.CharField(max_length=20, choices=STUDENT_TYPE_CHOICES, default='REGULAR')

    # Personal Information
    middle_name = models.CharField(max_length=150, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    state_of_origin = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    phone_number = models.CharField(max_length=20, blank=True)

    # Guardian Information
    guardian_name = models.CharField(max_length=200, blank=True)
    guardian_phone = models.CharField(max_length=20, blank=True)
    guardian_relationship = models.CharField(max_length=50, blank=True)

    # Academic Performance
    current_cgpa = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('0.00'))
    total_credits_earned = models.IntegerField(default=0)
    academic_standing = models.CharField(max_length=30, choices=ACADEMIC_STANDING_CHOICES, default='GOOD')

    # Status Information
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    graduation_status = models.CharField(max_length=20, choices=GRADUATION_STATUS_CHOICES, default='IN_PROGRESS')
    graduation_date = models.DateField(null=True, blank=True)
    class_of_degree = models.CharField(max_length=50, blank=True)

    # System fields
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['student_id']
        verbose_name = 'Student'
        verbose_name_plural = 'Students'

    def __str__(self):
        return f"{self.student_id} - {self.user.get_full_name()}"

    @property
    def full_name(self):
        full_name = f"{self.user.first_name}"
        if self.middle_name:
            full_name += f" {self.middle_name}"
        full_name += f" {self.user.last_name}"
        return full_name

    def calculate_cgpa(self):
        """Calculate student's current CGPA"""
        results = self.results.filter(is_final=True)

        if not results.exists():
            return Decimal('0.00')

        total_quality_points = Decimal('0.00')
        total_credits = 0

        for result in results:
            quality_points = result.grade_point * result.course.credits
            total_quality_points += quality_points
            total_credits += result.course.credits

        if total_credits > 0:
            cgpa = total_quality_points / Decimal(str(total_credits))
            self.current_cgpa = cgpa.quantize(Decimal('0.01'))
            self.total_credits_earned = total_credits
            self.save(update_fields=['current_cgpa', 'total_credits_earned'])
            return self.current_cgpa

        return Decimal('0.00')

    def get_semester_results(self, semester):
        """Get results for a specific semester"""
        return self.results.filter(semester=semester).select_related('course')

    def get_current_courses(self):
        """Get current semester enrolled courses"""
        current_semester = Semester.objects.filter(is_current=True).first()
        if current_semester:
            return self.enrollments.filter(
                semester=current_semester,
                status='ENROLLED'
            ).select_related('course')
        return []

    @staticmethod
    def get_grade_point(grade):
        """Convert letter grade to grade point"""
        grade_mapping = {
            'A': 5.0, 'B': 4.0, 'C': 3.0, 'D': 2.0, 'E': 1.0, 'F': 0.0
        }
        return grade_mapping.get(grade.upper())

    def save(self, *args, **kwargs):
        if not self.student_id:
            # Auto-generate student ID if not provided
            year = self.entry_session.name.split('/')[1] if self.entry_session else timezone.now().year
            dept_code = self.department.code if self.department else 'GEN'
            # Get next student number for this department and year
            last_student = Student.objects.filter(
                student_id__startswith=f"{year}{dept_code}"
            ).order_by('-student_id').first()

            if last_student:
                last_number = int(last_student.student_id[-3:])
                next_number = last_number + 1
            else:
                next_number = 1

            self.student_id = f"{year}{dept_code}{next_number:03d}"

        super().save(*args, **kwargs)


class Enrollment(models.Model):
    """Course Enrollment Model"""
    ENROLLMENT_STATUS_CHOICES = [
        ('ENROLLED', 'Enrolled'),
        ('DROPPED', 'Dropped'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='enrollments')
    enrollment_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=ENROLLMENT_STATUS_CHOICES, default='ENROLLED')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['student', 'course', 'semester']
        ordering = ['-semester__session__start_date', 'course__code']

    def __str__(self):
        return f"{self.student.student_id} - {self.course.code} ({self.semester})"


class Result(models.Model):
    """Academic Result Model"""
    GRADE_CHOICES = [
        ('A', 'A (Excellent)'),
        ('B', 'B (Very Good)'),
        ('C', 'C (Good)'),
        ('D', 'D (Satisfactory)'),
        ('E', 'E (Pass)'),
        ('F', 'F (Fail)'),
    ]

    STATUS_CHOICES = [
        ('PASSED', 'Passed'),
        ('FAILED', 'Failed'),
        ('PENDING', 'Pending'),
        ('RETAKE', 'Retake'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='results')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='results')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='results')

    # Scores and grades
    ca_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'),
                                   validators=[MinValueValidator(0), MaxValueValidator(30)])
    exam_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'),
                                     validators=[MinValueValidator(0), MaxValueValidator(70)])
    total_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'),
                                      validators=[MinValueValidator(0), MaxValueValidator(100)])
    grade = models.CharField(max_length=2, choices=GRADE_CHOICES, blank=True)
    grade_point = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal('0.0'))
    credit_earned = models.IntegerField(default=0)

    # Status and meta
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    is_final = models.BooleanField(default=False)
    date_recorded = models.DateTimeField(auto_now_add=True)
    recorded_by = models.CharField(max_length=200, blank=True)  # Staff who recorded result
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['student', 'course', 'semester']
        ordering = ['-semester__session__start_date', 'course__code']

    def __str__(self):
        return f"{self.student.student_id} - {self.course.code} - {self.grade}"

    def save(self, *args, **kwargs):
        # Calculate total score
        self.total_score = self.ca_score + self.exam_score

        # Determine grade and grade point
        total = float(self.total_score)
        if total >= 70:
            self.grade = 'A'
            self.grade_point = Decimal('5.0')
        elif total >= 60:
            self.grade = 'B'
            self.grade_point = Decimal('4.0')
        elif total >= 50:
            self.grade = 'C'
            self.grade_point = Decimal('3.0')
        elif total >= 45:
            self.grade = 'D'
            self.grade_point = Decimal('2.0')
        elif total >= 40:
            self.grade = 'E'
            self.grade_point = Decimal('1.0')
        else:
            self.grade = 'F'
            self.grade_point = Decimal('0.0')

        # Set credit earned and status
        if self.grade != 'F':
            self.credit_earned = self.course.credits
            self.status = 'PASSED'
        else:
            self.credit_earned = 0
            self.status = 'FAILED'

        super().save(*args, **kwargs)
