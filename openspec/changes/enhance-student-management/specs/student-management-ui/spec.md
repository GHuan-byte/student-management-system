## MODIFIED Requirements

### Requirement: Student management page
The system SHALL provide browser-accessible student-management screens rendered
with Flask templates, including a shared layout and an enhanced `/students`
page.

#### Scenario: Student page is server-rendered
- **WHEN** a browser requests `GET /students`
- **THEN** the system SHALL return an HTML page for student management
- **AND** the page SHALL be rendered through Flask templates rather than a
  separate SPA framework

#### Scenario: Initial page render shows the complete page before any modal workflow
- **WHEN** a browser initially loads or refreshes `GET /students`
- **THEN** the system SHALL first display the complete student management page
- **AND** the visible page SHALL include shared navigation, the toolbar/search
  area, and the student list or empty state
- **AND** it SHALL NOT automatically open a modal during that initial render

#### Scenario: UI labels are Chinese while code keys remain English
- **WHEN** the student management page is rendered and used
- **THEN** visible labels, actions, and feedback messages SHALL be presented in
  Chinese
- **AND** API payload keys and JavaScript field names SHALL remain English

#### Scenario: Student table and reusable modal use the approved fields
- **WHEN** the student management page renders the table or the reusable
  create/edit modal
- **THEN** they SHALL use the fields `student_number`, `name`, `gender`, `age`,
  `major`, `year_level`, `score`, `phone`, and `email`
- **AND** the visible Chinese labels SHALL show `year_level` as `年级` and
  `score` as `成绩`

#### Scenario: Student page includes list-enhancement controls
- **WHEN** the student management page renders successfully
- **THEN** it SHALL include pagination controls, matching-record totals,
  sortable headers, row checkboxes, a current-page select-all checkbox, and a
  batch-delete action
- **AND** the default page SHALL show no more than 15 student records

#### Scenario: Modal and backdrop are hidden by default
- **WHEN** the student management page is initially rendered, refreshed,
  loading the student list, or showing the empty state
- **THEN** the reusable modal and its backdrop SHALL remain hidden by default
- **AND** the page SHALL NOT automatically enter create mode or edit mode

#### Scenario: Create workflow opens the reusable modal
- **WHEN** the user activates the `新增学生` control from the student management
  page
- **THEN** the page SHALL open the reusable modal in create mode instead of
  showing a permanently expanded inline create form

#### Scenario: Edit workflow opens the reusable modal with current values
- **WHEN** the user activates the `编辑` control for an existing student
- **THEN** the page SHALL open the reusable modal in edit mode
- **AND** the modal SHALL be prefilled with the current student data

### Requirement: Browser-side CRUD interactions
The system SHALL provide browser-side student-management behavior through
vanilla JavaScript ES modules that consume the REST API.

#### Scenario: Initial load shows data or empty state
- **WHEN** the student management page loads
- **THEN** the browser SHALL request the student list from the REST API using
  default page `1`, default `page_size` `15`, default `sort_by`
  `student_number`, and default `sort_order` `asc`
- **AND** it SHALL show either the student data or an explicit empty state
- **AND** it SHALL present a visible loading state while the request is in
  progress

#### Scenario: Search uses the REST API and resets to page 1
- **WHEN** the user searches for students from the page
- **THEN** the browser SHALL request filtered results from `GET /api/students`
- **AND** the list display SHALL update from the API response
- **AND** the UI SHALL reset to page 1 for the new keyword

#### Scenario: Sort uses the REST API and resets to page 1
- **WHEN** the user changes the sort field or sort direction from a sortable
  table header
- **THEN** the browser SHALL request the sorted list from `GET /api/students`
- **AND** the UI SHALL reset to page 1
- **AND** the page SHALL visibly indicate ascending or descending order

#### Scenario: Pagination controls request the corresponding page
- **WHEN** the user moves to the next page, previous page, or another available
  page
- **THEN** the browser SHALL request that page from `GET /api/students`
- **AND** it SHALL update the visible list and pagination display from the API
  response metadata

#### Scenario: Current-page select-all affects only visible rows
- **WHEN** the user toggles the header checkbox on the student table
- **THEN** the page SHALL select or clear only the student rows visible on the
  current page
- **AND** it SHALL NOT select records from other pages

#### Scenario: Partial selection uses an indeterminate header state
- **WHEN** the user selects some but not all visible student rows
- **THEN** the header checkbox SHALL display the partial or indeterminate state

#### Scenario: Selection resets when the list basis changes
- **WHEN** the current page, keyword, or sort changes
- **THEN** the current selection SHALL be cleared

#### Scenario: Batch delete uses one API request
- **WHEN** the user confirms batch deletion for one or more selected students
- **THEN** the browser SHALL send one `POST /api/students/batch-delete`
  request
- **AND** after success it SHALL refresh the visible list and Dashboard count
- **AND** if the current page becomes empty it SHALL move to the previous valid
  page

#### Scenario: List loading and empty-state rendering do not open the modal automatically
- **WHEN** the browser loads the list, refreshes the list, or renders the empty
  state after a search result
- **THEN** the reusable create/edit modal SHALL remain closed unless the user
  explicitly opened it through a supported action

#### Scenario: Add, edit, and single delete continue to use the REST API
- **WHEN** the user adds, edits, or deletes a single student from the page
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

### Requirement: UI feedback states
The system SHALL provide clear loading, empty, disabled, and error states for
the Dashboard and student-management page.

#### Scenario: Loading state is visible during requests
- **WHEN** the browser is waiting for Dashboard data, a student list response,
  or a mutation response
- **THEN** the page SHALL present a visible loading state

#### Scenario: Batch delete action is disabled with no selection
- **WHEN** no student rows are selected on the current page
- **THEN** the batch-delete action SHALL be visibly disabled

#### Scenario: Error message is shown on failed request
- **WHEN** an API request fails
- **THEN** the page SHALL present an error message to the user
- **AND** it SHALL NOT silently pretend the operation succeeded

## ADDED Requirements

### Requirement: Dashboard page
The system SHALL provide a server-rendered Dashboard at the root route `/`.

#### Scenario: Root route returns HTML Dashboard
- **WHEN** a browser requests `GET /`
- **THEN** the system SHALL return an HTML Dashboard page
- **AND** it SHALL NOT return a JSON 404 response
- **AND** it SHALL NOT only redirect to `/students`

#### Scenario: Dashboard shows shared navigation and quick access
- **WHEN** the Dashboard is rendered
- **THEN** it SHALL show the shared top navigation
- **AND** the `首页` navigation item SHALL be active
- **AND** it SHALL provide a clear quick link to `/students`

#### Scenario: Dashboard shows student total and system status
- **WHEN** the Dashboard loads
- **THEN** it SHALL display a student total-count card using
  `GET /api/students/stats`
- **AND** it SHALL display a health or status card using the approved
  application health information

#### Scenario: Dashboard and student page share visual style
- **WHEN** the user navigates between `/` and `/students`
- **THEN** both pages SHALL use consistent spacing, typography, colors,
  buttons, cards, and message styles

### Requirement: Shared layout and navigation
The system SHALL provide shared navigation between the Dashboard and student
management page.

#### Scenario: Navigation works in both directions
- **WHEN** the user uses the page navigation
- **THEN** `首页` SHALL navigate to `/`
- **AND** `学生管理` SHALL navigate to `/students`

#### Scenario: Active navigation state reflects the current page
- **WHEN** either the Dashboard or the student page is rendered
- **THEN** the current page's navigation item SHALL display an active state

#### Scenario: Student page provides a clear return path
- **WHEN** the user is on `/students`
- **THEN** the page SHALL provide a clear and visible way to return to the
  Dashboard
