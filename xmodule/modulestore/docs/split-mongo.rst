.. _Split Mongo Modulestore:

#######################
Split Mongo Modulestore
#######################

See:

* `Overview`_
* `Split Mongo Data Model`_
* `Split Mongo Capabilities`_


********
Overview
********

*Split Mongo* is the term used for the new edX modulestore. Split Mongo is
built on mongoDB. For information about mongoDB, see the `mongoDB website`_. 

The "split" in Split Mongo refers to how a course is split into three types of
information:

* The course identity, referred to as the course index
* The course structure
* The course content, referred to as XBlock definitions.

This separation of identity, structure, and content enables course authors to
use more advanced capabilities when developing and managing courses.

.. _mongoDB website: http://www.mongodb.org

**********************
Split Mongo Data Model
**********************

In the Split Mongo data model, edX courses are split into three collections:

* `Course Index`_
* :ref:`Structures`
* `XBlock Definitions`_

.. Structures link is a workaround; "Course Structures" as label is already taken 

============
Course Index
============

The course index is a dictionary that stores course IDs. Each course ID points
to a course structure.

The course index supports multiple branches of a course.  The index can store
multiple entries for a course ID, with each entry pointing to a different
course structure that corresponds to a different branch.

As currently implemented, for each course, there is a branch for both the
published and draft versions of the course. The published and draft branches of
the course point to different structures.

In the edX Platform:

*  Students using the LMS see and interact with the published version of the
   course.

*  Course team members using edX Studio make changes to the draft version of
   the course.

   *  When the user changes the course outline, display names, the course
      about page, course updates, other course pages, sections or subsections,
      the draft branch is automatically published; that is, it becomes the
      published branch.

   *  For units and components, changes are saved in the draft branch. The user
      must publish the unit to change the draft branch to the published branch.
      When the user begins another set of changes, the draft branch is updated.

Course Reruns
*************

The edX Platform enables you to rerun a course.  When you rerun a course, a new
course index is created. The new course index points to the same course
structure as the original course index.

.. _Structures:

=================
Course Structures
=================

The course structure defines, or outlines, the content of a course.

A course structure is made up of blocks in a tree data structure. Blocks are
objects in a course, such as the course itself, sections, subsections, and
units.  A block can reference other blocks; for example, a section references
one or more subsections. Each block has a unique ID that is generated by the
edX Platform.

Each block in the course structure points to an XBlock definition. Different
blocks, in the same or in different structures, can point to the same
definition.

Course structures, and each block within a structure, are versioned. That is,
when a course author changes a course, or a block in the course, a new course
structure is saved; the previous course structure, and previous versions of
blocks within the structure, remain in the database and are not modified. 

==================
XBlock Definitions
==================

XBlock definitions contain the content of each block. For some blocks, such as
sections and subsections, the definition consists of the block's display name.
For components, such as HTML or problem components, the definition also
contains the content of the object. A definition can be referenced by multiple
blocks.

XBlock definitions are versioned. That is, when a course author changes
content, a new XBlock definition for that object is saved; the previous
definition remains in the database and is not modified.

************************
Split Mongo Capabilities
************************

The Split Mongo data model enables the edX Platform to implement advanced
content management functionality. Specifically, Split Mongo is designed to
enable:

* `Multiple Course Branches`_
* `Versioning`_
* `Content Reuse`_

While these capabilities are not fully implemented in the edX Platform, Split
Mongo is designed to allow future enhancements that enable these content
management capabilities.

========================
Multiple Course Branches
========================

Split Mongo enables multiple branches of a course. The `course index <Course
Index`>_ can have multiple entries for a course ID, each of which points to a
different structure.

The edX Platform currently uses a draft and a published branch for a course.
Future enhancements may use other branches.

==========
Versioning
==========

In Split Mongo, every change to a course or a block within the course is saved,
with the time and user recorded.

Versioning enables future enhancements such as allowing course authors to
revert a course or block to a previous version.

=============
Content Reuse
=============

By using pointers to reference XBlock definitions from :ref:`course structures
<Structures>`, Split Mongo enables content reuse. A single `XBlock
definition <XBlock Definition>`_ can be referenced from multiple course
structures.

Future enhancements to the edX Platform can allow course authors to reuse an
XBlock in multiple contexts, streamlining course development and maintenance.