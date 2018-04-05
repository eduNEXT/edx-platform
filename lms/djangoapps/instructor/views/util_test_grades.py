# -*- coding: utf-8 -*-
from django.conf import settings
from django.contrib.auth.models import User

from student.models import CourseEnrollment
from lms.djangoapps.grades.new.course_grade_factory import CourseGradeFactory
from courseware import courses
from opaque_keys.edx.keys import CourseKey


class ServiceGrades(object):

    def __init__(self, course_id):
        course_key = CourseKey.from_string(course_id)
        self.course = courses.get_course_by_id(course_key)
        self.students = CourseEnrollment.objects.users_enrolled_in(course_key)

    def get_grades(self):
        course_grades = []
        for student in self.students:
            course_grade = CourseGradeFactory().create(student, self.course)
            gradeset = course_grade.summary
            gradeset["username"] = student.username
            gradeset["fullname"] = "{} {}".format(student.first_name, student.last_name)
            course_grades.append(gradeset)
        return course_grades

    def by_section(self):
        gradeset = self.get_grades()
        by_section = {}
        for grade in gradeset:
            by_section[grade["username"]] = {
                "username": grade["username"],
                "grade": grade["percent"]
            }
            for section in grade["section_breakdown"]:
                by_section[grade["username"]].update({section["label"]: section["percent"] })
        return by_section
