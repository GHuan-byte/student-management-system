### Requirement: Student management page
The system SHALL provide a browser-accessible student management page rendered with Flask templates.

#### Scenario: Student page is server-rendered
- **WHEN** a browser requests `GET /students`
- **THEN** the system SHALL return an HTML page for student management
- **AND** the page SHALL be rendered through Flask templates rather than a separate SPA framework

#### Scenario: Initial page render shows the complete page before any modal workflow
- **WHEN** a browser initially loads or refreshes `GET /students`
- **THEN** the system SHALL first display the complete student management page
- **AND** the visible page SHALL include the toolbar/search area and the student list or empty state
- **AND** it SHALL NOT automatically open a modal during that initial render

#### Scenario: UI labels are Chinese while code keys remain English
- **WHEN** the student management page is rendered and used
- **THEN** visible labels, actions, and feedback messages SHALL be presented in Chinese
- **AND** API payload keys and JavaScript field names SHALL remain English

#### Scenario: Student table and reusable modal use the approved fields
- **WHEN** the student management page renders the table or the reusable create/edit modal
- **THEN** they SHALL use the fields `student_number`, `name`, `gender`, `age`, `major`, `year_level`, `score`, `phone`, and `email`
- **AND** the visible Chinese labels SHALL show `year_level` as “年级” and `score` as “成绩”

#### Scenario: Modal and backdrop are hidden by default
- **WHEN** the student management page is initially rendered, refreshed, loading the student list, or showing the empty state
- **THEN** the reusable modal and its backdrop SHALL remain hidden by default
- **AND** the page SHALL NOT automatically enter create mode or edit mode

#### Scenario: Create workflow opens the reusable modal
- **WHEN** the user activates the `新增学生` control from the student management page
- **THEN** the page SHALL open the reusable modal in create mode instead of showing a permanently expanded inline create form

#### Scenario: Edit workflow opens the reusable modal with current values
- **WHEN** the user activates the `编辑` control for an existing student
- **THEN** the page SHALL open the reusable modal in edit mode
- **AND** the modal SHALL be prefilled with the current student data

---

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

#### Scenario: List loading and empty-state rendering do not open the modal automatically
- **WHEN** the browser loads the list, refreshes the list, or renders the empty state after a search result
- **THEN** the reusable modal SHALL remain closed unless the user explicitly opened it through a supported action

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
- **AND** the user SHALL return to the visible student management page

---

### Requirement: UI feedback states
The system SHALL provide clear loading, empty, and error states for the student management page.

#### Scenario: Loading state is visible during requests
- **WHEN** the browser is waiting for a student list or mutation response
- **THEN** the page SHALL present a visible loading state

#### Scenario: Error message is shown on failed request
- **WHEN** an API request fails
- **THEN** the page SHALL present an error message to the user
- **AND** it SHALL NOT silently pretend the operation succeeded
