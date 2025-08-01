"""
Instructor tasks related to enrollments.
"""

import logging
from datetime import datetime
from time import time

from opaque_keys.edx.keys import CourseKey
from pytz import UTC

from common.djangoapps.student.models import CourseEnrollment  # lint-amnesty, pylint: disable=unused-import
from lms.djangoapps.instructor.utils.enrollment_utils import process_student_enrollment_batch as process_batch
from lms.djangoapps.instructor_analytics.basic import enrolled_students_features, list_may_enroll
from lms.djangoapps.instructor_analytics.csvs import format_dictlist

from .runner import TaskProgress
from .utils import upload_csv_to_report_store  # lint-amnesty, pylint: disable=unused-import

TASK_LOG = logging.getLogger('edx.celery.task')
FILTERED_OUT_ROLES = ['staff', 'instructor', 'finance_admin', 'sales_admin']


def upload_may_enroll_csv(_xblock_instance_args, _entry_id, course_id, task_input, action_name):
    """
    For a given `course_id`, generate a CSV file containing
    information about students who may enroll but have not done so
    yet, and store using a `ReportStore`.
    """
    start_time = time()
    start_date = datetime.now(UTC)
    num_reports = 1
    task_progress = TaskProgress(action_name, num_reports, start_time)
    current_step = {'step': 'Calculating info about students who may enroll'}
    task_progress.update_task_state(extra_meta=current_step)

    # Compute result table and format it
    query_features = task_input.get('features')
    student_data = list_may_enroll(course_id, query_features)
    header, rows = format_dictlist(student_data, query_features)

    task_progress.attempted = task_progress.succeeded = len(rows)
    task_progress.skipped = task_progress.total - task_progress.attempted

    rows.insert(0, header)

    current_step = {'step': 'Uploading CSV'}
    task_progress.update_task_state(extra_meta=current_step)

    # Perform the upload
    upload_csv_to_report_store(rows, 'may_enroll_info', course_id, start_date)

    return task_progress.update_task_state(extra_meta=current_step)


def upload_students_csv(_xblock_instance_args, _entry_id, course_id, task_input, action_name):
    """
    For a given `course_id`, generate a CSV file containing profile
    information for all students that are enrolled, and store using a
    `ReportStore`.
    """
    start_time = time()
    start_date = datetime.now(UTC)
    enrolled_students = CourseEnrollment.objects.users_enrolled_in(course_id)
    task_progress = TaskProgress(action_name, enrolled_students.count(), start_time)

    current_step = {'step': 'Calculating Profile Info'}
    task_progress.update_task_state(extra_meta=current_step)

    # compute the student features table and format it
    query_features = task_input.get('features')
    student_data = enrolled_students_features(course_id, query_features)
    header, rows = format_dictlist(student_data, query_features)

    task_progress.attempted = task_progress.succeeded = len(rows)
    task_progress.skipped = task_progress.total - task_progress.attempted

    rows.insert(0, header)

    current_step = {'step': 'Uploading CSV'}
    task_progress.update_task_state(extra_meta=current_step)

    # Perform the upload
    upload_parent_dir = task_input.get('upload_parent_dir', '')
    upload_filename = task_input.get('filename', 'student_profile_info')
    upload_csv_to_report_store(rows, upload_filename, course_id, start_date, parent_dir=upload_parent_dir)

    return task_progress.update_task_state(extra_meta=current_step)


def process_student_enrollment_batch(_xblock_instance_args, _entry_id, course_id, task_input, action_name):
    """
    Process a batch of student enrollment/unenrollment operations asynchronously.

    Args:
        course_id: The course identifier
        task_input: Dictionary containing:
            - action: 'enroll' or 'unenroll'
            - identifiers: list of student identifiers (emails or usernames)
            - auto_enroll: boolean for auto-enrollment
            - email_students: boolean to send enrollment emails
            - reason: optional reason for enrollment change
            - secure: boolean indicating if request was secure (HTTPS)
        action_name: Name of the action being performed

    Returns:
        Task progress with results of enrollment operations
    """
    start_time = time()

    # Extract parameters from task_input
    action = task_input.get("action")
    identifiers = task_input.get("identifiers", [])
    auto_enroll = task_input.get("auto_enroll", False)
    email_students = task_input.get("email_students", False)
    reason = task_input.get("reason")
    secure = task_input.get("secure", False)

    # Convert course_id string to CourseKey if needed
    if isinstance(course_id, str):
        course_key = CourseKey.from_string(course_id)
    else:
        course_key = course_id

    # Initialize task progress
    total_students = len(identifiers)
    task_progress = TaskProgress(action_name, total_students, start_time)

    current_step = {"step": f"Processing {action} operations for {total_students} students"}
    task_progress.update_task_state(extra_meta=current_step)

    # Define progress callback function
    def progress_callback(current, total, results):
        task_progress.attempted = current
        task_progress.succeeded = sum(1 for r in results if r.get("success", False))
        task_progress.failed = current - task_progress.succeeded

        # Update progress every 10 operations or at the end
        if current % 10 == 0 or current == total:
            current_step = {
                "step": f"Processed {current}/{total} {action} operations",
                "succeeded": task_progress.succeeded,
                "failed": task_progress.failed,
            }
            task_progress.update_task_state(extra_meta=current_step)

    # Use the utility function to process the batch
    batch_result = process_batch(
        course_key=course_key,
        action=action,
        identifiers=identifiers,
        auto_enroll=auto_enroll,
        email_students=email_students,
        reason=reason,
        secure=secure,
        progress_callback=progress_callback
    )

    # Final update
    task_progress.attempted = batch_result["total_students"]
    task_progress.succeeded = batch_result["successful_operations"]
    task_progress.failed = batch_result["failed_operations"]
    task_progress.skipped = 0

    final_step = {
        "step": f"Completed {action} batch processing",
        "total_processed": batch_result["total_students"],
        "successful": batch_result["successful_operations"],
        "failed": batch_result["failed_operations"],
        "results": batch_result["results"],
    }

    return task_progress.update_task_state(extra_meta=final_step)
