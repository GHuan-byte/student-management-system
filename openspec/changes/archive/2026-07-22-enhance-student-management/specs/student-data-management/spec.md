## MODIFIED Requirements

### Requirement: Student repository operations
The system SHALL provide a `StudentRepository` that keeps SQL inside repository
or database modules and exposes CRUD-focused data access methods, including
counting, paginated listing, safe sorting, and batch deletion.

#### Scenario: Repository reads return dictionaries
- **WHEN** the repository lists, searches, counts, or fetches student records
- **THEN** it SHALL return dictionaries, lists of dictionaries, or numeric
  counts as appropriate
- **AND** it SHALL NOT return Flask `Response` objects

#### Scenario: Paginated list uses keyword, page, and page_size together
- **WHEN** the repository lists students for `GET /api/students`
- **THEN** it SHALL support `keyword`, `page`, and `page_size` together
- **AND** it SHALL return only the rows for the requested page
- **AND** it SHALL compute `total` from the number of records matching the
  current keyword filter
- **AND** it SHALL NOT load all rows and paginate only in JavaScript

#### Scenario: Sorting uses a repository-side whitelist
- **WHEN** the repository applies sorting for the student list
- **THEN** it SHALL use parameterized SQL for values and an explicit whitelist
  for sortable columns
- **AND** it SHALL allow sorting only by `student_number`, `name`, `gender`,
  `age`, `major`, `year_level`, and `score`
- **AND** it SHALL allow only `asc` and `desc` sort order values
- **AND** SQL column names SHALL NOT come directly from unchecked user input

#### Scenario: Repository provides student count
- **WHEN** the repository is asked to count students
- **THEN** it SHALL return the current total number of student records from
  SQLite

#### Scenario: Repository batch delete is transactional
- **WHEN** the repository deletes multiple students
- **THEN** it SHALL use parameterized SQL
- **AND** it SHALL execute the deletion in one transaction
- **AND** it SHALL return the number of deleted rows
- **AND** it SHALL commit successful writes, roll back failed writes, and close
  connections reliably

### Requirement: Student service validation and normalization
The system SHALL provide a `StudentService` that validates input, normalizes
payloads, validates list-query parameters, and translates storage-level
failures into application exceptions.

#### Scenario: Blank optional strings are normalized consistently
- **WHEN** a create or update payload includes optional fields with blank-string
  values
- **THEN** the service SHALL normalize them consistently before persistence

#### Scenario: year_level and score blank strings normalize to null
- **WHEN** a create or update payload provides `year_level` or `score` as an
  empty string
- **THEN** the service SHALL normalize those values to `null` before validation
  and persistence

#### Scenario: Invalid create or update payload is rejected
- **WHEN** a payload omits required fields, provides an invalid `year_level`,
  provides an invalid `score`, provides an invalid `age`, or becomes empty
  after update normalization
- **THEN** the service SHALL raise `ValidationError`

#### Scenario: Unknown or protected update fields are rejected
- **WHEN** an update payload includes unknown fields or attempts to set `id`,
  `created_at`, or `updated_at`
- **THEN** the service SHALL raise `ValidationError`

#### Scenario: Invalid list-query parameters are rejected
- **WHEN** the student list is requested with `page < 1`, `page_size < 1`,
  `page_size > 50`, an unsupported `sort_by`, or an unsupported `sort_order`
- **THEN** the service SHALL raise `ValidationError`

#### Scenario: Student count passes through the service layer
- **WHEN** the application requests student statistics
- **THEN** the service SHALL obtain the count from `StudentRepository`
- **AND** routes SHALL NOT count SQLite rows directly

#### Scenario: Batch delete input is normalized and validated
- **WHEN** the application requests batch deletion
- **THEN** the service SHALL require `student_ids` to be a non-empty JSON array
- **AND** it SHALL validate every ID as a positive integer
- **AND** it SHALL normalize duplicate IDs before calling the repository
- **AND** it SHALL raise `ValidationError` for empty or invalid input

#### Scenario: Duplicate or missing records are translated
- **WHEN** the repository reports a duplicate `student_number`
- **THEN** the service SHALL raise `DuplicateError`

#### Scenario: Missing student is translated
- **WHEN** a requested student record does not exist for read, update, or
  delete
- **THEN** the service SHALL raise `NotFoundError`

### Requirement: Student CRUD API
The system SHALL provide a REST API for listing, searching, creating, reading,
updating, deleting, counting, and batch-deleting students.

#### Scenario: Editable request fields are fixed
- **WHEN** a client sends a create or update request
- **THEN** the allowed editable fields SHALL be `student_number`, `name`,
  `gender`, `age`, `major`, `year_level`, `score`, `phone`, and `email`

#### Scenario: List students with pagination and sorting
- **WHEN** a client sends `GET /api/students`
- **THEN** the response SHALL return status `200`
- **AND** it SHALL use the unified JSON response structure
- **AND** it SHALL return the student collection in `data`
- **AND** it SHALL include `page`, `page_size`, `total`, `total_pages`,
  `sort_by`, and `sort_order` in `meta`

#### Scenario: Keyword filtering composes with pagination and sorting
- **WHEN** a client sends `GET /api/students?keyword=<value>&page=<n>&page_size=<m>&sort_by=<field>&sort_order=<dir>`
- **THEN** the response SHALL contain only students matching the keyword filter
- **AND** `total` SHALL represent the number of records matching that keyword
- **AND** pagination and sorting SHALL apply to the filtered set

#### Scenario: Invalid list parameters return validation error
- **WHEN** a client sends `GET /api/students` with an invalid `page`,
  `page_size`, `sort_by`, or `sort_order`
- **THEN** the response SHALL return status `400`
- **AND** the unified JSON error response SHALL use code `validation_error`

#### Scenario: Student stats endpoint returns total count
- **WHEN** a client sends `GET /api/students/stats`
- **THEN** the response SHALL return status `200`
- **AND** it SHALL use the unified JSON response structure
- **AND** `data.total_students` SHALL equal the current SQLite-backed student
  count

#### Scenario: Retrieve one student
- **WHEN** a client sends `GET /api/students/<student_id>` for an existing
  student
- **THEN** the response SHALL return status `200`
- **AND** it SHALL use the unified JSON response structure
- **AND** it SHALL return the requested student in `data`

#### Scenario: Create student preserves student number formatting
- **WHEN** a client sends `POST /api/students` with a valid payload whose
  `student_number` contains leading zeros
- **THEN** the response SHALL return status `201`
- **AND** it SHALL use the unified JSON response structure
- **AND** the stored and returned `student_number` SHALL preserve the leading
  zeros

#### Scenario: Partial update returns the updated student
- **WHEN** a client sends `PUT /api/students/<student_id>` with a valid partial
  JSON object containing at least one allowed editable field
- **THEN** the response SHALL return status `200`
- **AND** it SHALL use the unified JSON response structure
- **AND** it SHALL return the updated student in `data`

#### Scenario: Delete returns unified success
- **WHEN** a client sends `DELETE /api/students/<student_id>` for an existing
  student
- **THEN** the response SHALL return status `200`
- **AND** it SHALL use the unified JSON response structure

#### Scenario: Batch delete returns requested and deleted counts
- **WHEN** a client sends `POST /api/students/batch-delete` with a valid
  `student_ids` array
- **THEN** the response SHALL return status `200`
- **AND** it SHALL use the unified JSON response structure
- **AND** `data.requested_count` SHALL reflect the normalized number of
  requested IDs
- **AND** `data.deleted_count` SHALL reflect the number of deleted rows

#### Scenario: Invalid batch delete payload returns validation error
- **WHEN** a client sends `POST /api/students/batch-delete` with an empty
  array, invalid IDs, or a non-array `student_ids` value
- **THEN** the response SHALL return status `400`
- **AND** the unified JSON error response SHALL use code `validation_error`

#### Scenario: Read, update, and delete use service-layer errors
- **WHEN** a client reads, updates, or deletes a missing student through
  `/api/students/<student_id>`
- **THEN** the response SHALL use the existing global error handling and
  unified JSON error structure

#### Scenario: Duplicate student number returns conflict
- **WHEN** a client submits a create or update request with a duplicate
  `student_number`
- **THEN** the response SHALL return status `409`
- **AND** the unified JSON error response SHALL use code `duplicate`

#### Scenario: Missing student returns not found
- **WHEN** a client requests, updates, or deletes a student that does not
  exist
- **THEN** the response SHALL return status `404`
- **AND** the unified JSON error response SHALL use code `not_found`

### Requirement: Manual student CRUD verification
The system SHALL support manual verification of the enhanced student-management
capability after the user initializes the database and starts the application.

#### Scenario: Manual pagination and sorting verification
- **WHEN** the user manually opens `/students` or calls `GET /api/students`
- **THEN** page size, page navigation, keyword-aware totals, and approved
  sorting behavior SHALL be verifiable without automated tests

#### Scenario: Manual stats and batch delete verification
- **WHEN** the user manually calls `GET /api/students/stats` and performs batch
  deletion from the UI
- **THEN** the total student count and requested-versus-deleted counts SHALL be
  verifiable without automated tests

#### Scenario: Manual CRUD and validation verification remains available
- **WHEN** the user manually creates, edits, deletes, and validates student
  records through the UI or API
- **THEN** duplicate handling, validation errors, timestamp behavior, and
  leading-zero preservation SHALL remain verifiable without running pytest
