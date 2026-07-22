## ADDED Requirements

### Requirement: Student management page
The system SHALL provide a browser-accessible student management page rendered with Flask templates.

#### Scenario: Student page is server-rendered
- **WHEN** a browser requests `GET /students`
- **THEN** the system SHALL return an HTML page for student management
- **AND** the page SHALL be rendered through Flask templates rather than a separate SPA framework

#### Scenario: UI labels are Chinese while code keys remain English
- **WHEN** the student management page is rendered and used
- **THEN** visible labels, actions, and feedback messages SHALL be presented in Chinese
- **AND** API payload keys and JavaScript field names SHALL remain English

#### Scenario: Student table and modal forms use the approved fields
- **WHEN** the student management page renders the table, create modal, or edit modal
- **THEN** they SHALL use the fields `student_number`, `name`, `gender`, `age`, `major`, `year_level`, `score`, `phone`, and `email`
- **AND** the visible Chinese labels SHALL show `year_level` as “年级” and `score` as “成绩”

#### Scenario: Create workflow opens a modal
- **WHEN** the user activates the `新增学生` control from the student management page
- **THEN** the page SHALL open a create modal instead of showing a permanently expanded inline create form

#### Scenario: Edit workflow opens a prefilled modal
- **WHEN** the user activates the `编辑` control for an existing student
- **THEN** the page SHALL open an edit modal
- **AND** the modal SHALL be prefilled with the current student data

### Requirement: Browser-side CRUD interactions
The system SHALL provide browser-side student CRUD behavior through a vanilla JavaScript ES module that consumes the REST API.

#### Scenario: Initial load shows data or empty state
- **WHEN** the student management page loads
- **THEN** the browser SHALL request the student list from the REST API
- **AND** it SHALL show either the student data or an explicit empty state
- **AND** it SHALL present a visible loading state while the request is in progress

#### Scenario: Search uses the REST API
- **WHEN** the user searches for students from the page
- **THEN** the browser SHALL request filtered results from `GET /api/students`
- **AND** the list display SHALL update from the API response

#### Scenario: Add, edit, and delete use the REST API
- **WHEN** the user adds, edits, or deletes a student from the page
- **THEN** the browser SHALL call the corresponding REST API endpoint
- **AND** it SHALL update the visible list from the resulting response flow

#### Scenario: Modal submission closes and refreshes
- **WHEN** a create or edit request succeeds from a modal workflow
- **THEN** the page SHALL close the modal
- **AND** it SHALL refresh the visible student list

#### Scenario: Modal can be cancelled or closed
- **WHEN** the user cancels or closes the create or edit modal
- **THEN** the modal SHALL close without submitting a mutation request

### Requirement: UI feedback states
The system SHALL provide clear loading, empty, and error states for the student management page.

#### Scenario: Loading state is visible during requests
- **WHEN** the browser is waiting for a student list or mutation response
- **THEN** the page SHALL present a visible loading state

#### Scenario: Error message is shown on failed request
- **WHEN** an API request fails
- **THEN** the page SHALL present an error message to the user
- **AND** it SHALL NOT silently pretend the operation succeeded
