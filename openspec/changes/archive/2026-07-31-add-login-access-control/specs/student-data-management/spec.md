## ADDED Requirements

### Requirement: Student API authentication and role authorization
The student REST API SHALL require an authenticated current user and SHALL enforce the role matrix from `login-access-control` before executing student service operations.

#### Scenario: Read APIs allow all roles
- **WHEN** an authenticated Viewer, Staff, or Admin requests `GET /api/students`, `GET /api/students/<student_id>`, or `GET /api/students/stats`
- **THEN** the request SHALL be allowed to reach the existing student service behavior
- **AND** the response contract for successful permitted requests SHALL remain the unified JSON structure

#### Scenario: Create and update APIs allow Staff and Admin
- **WHEN** an authenticated Staff or Admin user requests `POST /api/students` or `PUT /api/students/<student_id>`
- **THEN** the request SHALL be allowed to reach the existing student service behavior

#### Scenario: Create and update APIs reject Viewer
- **WHEN** an authenticated Viewer requests `POST /api/students` or `PUT /api/students/<student_id>`
- **THEN** the system SHALL return unified JSON status `403`
- **AND** it SHALL NOT call the student service write operation

#### Scenario: Delete APIs allow only Admin
- **WHEN** an authenticated Admin requests `DELETE /api/students/<student_id>` or `POST /api/students/batch-delete`
- **THEN** the request SHALL be allowed to reach the existing student service behavior

#### Scenario: Delete APIs reject Viewer and Staff
- **WHEN** an authenticated Viewer or Staff user requests `DELETE /api/students/<student_id>` or `POST /api/students/batch-delete`
- **THEN** the system SHALL return unified JSON status `403`
- **AND** it SHALL NOT call the student service delete operation

#### Scenario: Unauthenticated student API is JSON 401
- **WHEN** an unauthenticated client requests any student API endpoint
- **THEN** the system SHALL return unified JSON status `401`
- **AND** it SHALL NOT redirect to `/login`

### Requirement: Student API CSRF enforcement
Student REST API requests that use unsafe HTTP methods SHALL require a valid CSRF token before the student service is called.

#### Scenario: Unsafe student API requires CSRF
- **WHEN** an authenticated user sends `POST`, `PUT`, `PATCH`, or `DELETE` to a student API endpoint without a valid CSRF token
- **THEN** the system SHALL return status `403`
- **AND** it SHALL NOT call the student service operation

#### Scenario: Read student API does not require CSRF
- **WHEN** an authenticated user sends `GET /api/students`, `GET /api/students/<student_id>`, or `GET /api/students/stats`
- **THEN** the system SHALL NOT require a CSRF token for that request
