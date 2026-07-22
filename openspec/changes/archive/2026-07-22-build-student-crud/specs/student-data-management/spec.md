## ADDED Requirements

### Requirement: SQLite connection and initialization
The system SHALL provide centralized SQLite connection management and explicit schema initialization for the student CRUD capability.

#### Scenario: Connection uses centralized database settings
- **WHEN** a database connection is opened for student CRUD
- **THEN** it SHALL use `app.config["DATABASE_PATH"]`
- **AND** it SHALL expose rows through `sqlite3.Row`
- **AND** it SHALL enable SQLite foreign-key enforcement for that connection

#### Scenario: Database initialization is explicit
- **WHEN** `flask --app run.py init-db` is invoked manually
- **THEN** the system SHALL create the required student CRUD schema if it does not already exist
- **AND** it MAY create the configured database parent directory during that command
- **AND** the system SHALL NOT initialize the database merely by importing a module or creating the Flask app

#### Scenario: Repository and service construction stays framework-independent
- **WHEN** the student CRUD components are constructed
- **THEN** `StudentRepository` SHALL receive a database path or connection factory explicitly
- **AND** `StudentService` SHALL receive a `StudentRepository` instance explicitly
- **AND** repository and service modules SHALL NOT require Flask request context or read `current_app` directly

### Requirement: Student schema
The system SHALL persist student records in a `students` table with fields `id`, `student_number`, `name`, `gender`, `age`, `major`, `year_level`, `score`, `phone`, `email`, `created_at`, and `updated_at`.

#### Scenario: Required and unique student number
- **WHEN** a student record is stored
- **THEN** `student_number` SHALL be required
- **AND** it SHALL be stored as text
- **AND** leading zeros SHALL be preserved
- **AND** the stored value SHALL be unique across the table

#### Scenario: Required name and bounded optional numerics
- **WHEN** a student record is created or updated
- **THEN** `name` SHALL be required for creates
- **AND** `score` SHALL be an integer between `0` and `100` when supplied
- **AND** `age` SHALL be an integer between `10` and `100` when supplied

#### Scenario: year_level uses a fixed allowed set
- **WHEN** a student record is created or updated
- **THEN** `year_level` SHALL be `NULL` or one of `大一`, `大二`, `大三`, or `大四`

#### Scenario: Database constraints and timestamps are enforced
- **WHEN** the `students` table is created
- **THEN** `id` SHALL be `INTEGER PRIMARY KEY AUTOINCREMENT`
- **AND** `year_level` SHALL be constrained to `NULL` or one of `大一`, `大二`, `大三`, or `大四`
- **AND** `score` SHALL be constrained to `NULL` or the range `0` through `100`
- **AND** `age` SHALL be constrained to `NULL` or the range `10` through `100`
- **AND** `created_at` and `updated_at` SHALL be stored as UTC ISO 8601 timestamps in the format `YYYY-MM-DDTHH:MM:SSZ`

#### Scenario: Insert and update timestamps behave consistently
- **WHEN** a student record is inserted
- **THEN** both `created_at` and `updated_at` SHALL be created

#### Scenario: updated_at changes while created_at is retained
- **WHEN** a student record is updated successfully
- **THEN** `updated_at` SHALL be refreshed
- **AND** `created_at` SHALL remain unchanged

### Requirement: Student repository operations
The system SHALL provide a `StudentRepository` that keeps SQL inside repository or database modules and exposes CRUD-focused data access methods.

#### Scenario: Repository reads return dictionaries
- **WHEN** the repository lists, searches, or fetches student records
- **THEN** it SHALL return dictionaries or lists of dictionaries
- **AND** it SHALL NOT return Flask `Response` objects

#### Scenario: Repository writes are transactional
- **WHEN** the repository adds, updates, or deletes a student
- **THEN** it SHALL use parameterized SQL
- **AND** it SHALL commit successful writes
- **AND** it SHALL roll back failed writes
- **AND** it SHALL close connections reliably

#### Scenario: Keyword search fields are fixed for this capability
- **WHEN** the repository performs the basic student keyword search
- **THEN** it SHALL use parameterized SQL
- **AND** it SHALL search across `student_number`, `name`, `major`, `phone`, and `email`
- **AND** it SHALL NOT add pagination or sorting behavior in this change

### Requirement: Student service validation and normalization
The system SHALL provide a `StudentService` that validates input, normalizes payloads, and translates storage-level failures into application exceptions.

#### Scenario: Blank optional strings are normalized consistently
- **WHEN** a create or update payload includes optional fields with blank-string values
- **THEN** the service SHALL normalize them consistently before persistence

#### Scenario: year_level and score blank strings normalize to null
- **WHEN** a create or update payload provides `year_level` or `score` as an empty string
- **THEN** the service SHALL normalize those values to `null` before validation and persistence

#### Scenario: Invalid create or update payload is rejected
- **WHEN** a payload omits required fields, provides an invalid `year_level`, provides an invalid `score`, provides an invalid `age`, or becomes empty after update normalization
- **THEN** the service SHALL raise `ValidationError`

#### Scenario: Unknown or protected update fields are rejected
- **WHEN** an update payload includes unknown fields or attempts to set `id`, `created_at`, or `updated_at`
- **THEN** the service SHALL raise `ValidationError`

#### Scenario: Duplicate or missing records are translated
- **WHEN** the repository reports a duplicate `student_number`
- **THEN** the service SHALL raise `DuplicateError`

#### Scenario: Missing student is translated
- **WHEN** a requested student record does not exist for read, update, or delete
- **THEN** the service SHALL raise `NotFoundError`

### Requirement: Student CRUD API
The system SHALL provide a REST API for listing, searching, creating, reading, updating, and deleting students.

#### Scenario: Editable request fields are fixed
- **WHEN** a client sends a create or update request
- **THEN** the allowed editable fields SHALL be `student_number`, `name`, `gender`, `age`, `major`, `year_level`, `score`, `phone`, and `email`

#### Scenario: List students with optional keyword search
- **WHEN** a client sends `GET /api/students`
- **THEN** the response SHALL return status `200`
- **AND** it SHALL use the unified JSON response structure
- **AND** it SHALL return the student collection in `data`

#### Scenario: Retrieve one student
- **WHEN** a client sends `GET /api/students/<student_id>` for an existing student
- **THEN** the response SHALL return status `200`
- **AND** it SHALL use the unified JSON response structure
- **AND** it SHALL return the requested student in `data`

#### Scenario: Keyword filters the student list
- **WHEN** a client sends `GET /api/students?keyword=<value>`
- **THEN** the response SHALL return only students matching the basic keyword search rules for this capability

#### Scenario: Create student preserves student number formatting
- **WHEN** a client sends `POST /api/students` with a valid payload whose `student_number` contains leading zeros
- **THEN** the response SHALL return status `201`
- **AND** it SHALL use the unified JSON response structure
- **AND** the stored and returned `student_number` SHALL preserve the leading zeros

#### Scenario: Partial update returns the updated student
- **WHEN** a client sends `PUT /api/students/<student_id>` with a valid partial JSON object containing at least one allowed editable field
- **THEN** the response SHALL return status `200`
- **AND** it SHALL use the unified JSON response structure
- **AND** it SHALL return the updated student in `data`

#### Scenario: Delete returns unified success
- **WHEN** a client sends `DELETE /api/students/<student_id>` for an existing student
- **THEN** the response SHALL return status `200`
- **AND** it SHALL use the unified JSON response structure

#### Scenario: Read, update, and delete use service-layer errors
- **WHEN** a client reads, updates, or deletes a missing student through `/api/students/<student_id>`
- **THEN** the response SHALL use the existing global error handling and unified JSON error structure

#### Scenario: Duplicate student number returns conflict
- **WHEN** a client submits a create or update request with a duplicate `student_number`
- **THEN** the response SHALL return status `409`
- **AND** the unified JSON error response SHALL use code `duplicate`

#### Scenario: Invalid payload returns validation error
- **WHEN** a client submits a create or update request with an invalid payload
- **THEN** the response SHALL return status `400`
- **AND** the unified JSON error response SHALL use code `validation_error`

#### Scenario: Missing student returns not found
- **WHEN** a client requests, updates, or deletes a student that does not exist
- **THEN** the response SHALL return status `404`
- **AND** the unified JSON error response SHALL use code `not_found`

### Requirement: Manual student CRUD verification
The system SHALL support manual verification of the student CRUD capability after the user initializes the database and starts the application.

#### Scenario: Manual list and search verification
- **WHEN** the user manually opens the student management page or calls `GET /api/students`
- **THEN** the student list and keyword search behavior SHALL be verifiable without automated tests

#### Scenario: Manual create, edit, and delete verification
- **WHEN** the user manually creates, edits, and deletes a student through the UI or API
- **THEN** each operation SHALL be verifiable through status codes, unified JSON responses, and visible list changes without running pytest

#### Scenario: Manual error and timestamp verification
- **WHEN** the user manually verifies duplicate student numbers, invalid `year_level`, invalid `score`, invalid `age`, missing students, retained `created_at`, and refreshed `updated_at`
- **THEN** the behavior SHALL be verifiable through API responses and returned student data without running pytest
