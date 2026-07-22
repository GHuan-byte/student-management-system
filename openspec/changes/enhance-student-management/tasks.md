## 1. Scope Guardrails

This Change enhances the current student-management application only.

Architecture guardrails:

- Browser UI -> Flask REST API -> StudentService -> StudentRepository -> SQLite
- Routes must not access SQLite directly
- StudentService must continue to depend on StudentRepository
- No new third-party dependency is expected

Out of scope for this Change:

- Excel import/export
- Authentication
- MCP
- AI Chat
- Legacy migration
- Automated tests
- Deployment
- Analytics charts
- User accounts

Execution guardrails:

- Do not install anything
- Do not run `pip`
- Do not run `pytest`
- Do not create or manage virtual environments
- If any new installation requirement is discovered, stop and report it
- Do not commit
- Do not start another OpenSpec Change automatically after this one

## 2. Repository Enhancements

- [x] 2.1 Extend `app/repositories/student_repository.py` with a paginated list method that supports `keyword`, `page`, `page_size`, `sort_by`, and `sort_order`
- [x] 2.2 Keep keyword filtering aligned with the current searchable fields: `student_number`, `name`, `major`, `phone`, and `email`
- [x] 2.3 Add an explicit sortable-field whitelist in the repository for `student_number`, `name`, `gender`, `age`, `major`, `year_level`, and `score`, and ensure the repository defensively rejects unsupported `sort_by` or `sort_order` values before building SQL
- [x] 2.4 Ensure repository list queries compute the matching-record total separately from the current page result
- [x] 2.5 Add `count_students` to return the current SQLite-backed total
- [x] 2.6 Add `batch_delete_students` using parameterized SQL and one transaction
- [x] 2.7 Ensure repository writes still commit successful changes, roll back failures, and close connections reliably

## 3. Service Enhancements

- [x] 3.1 Extend `app/services/student_service.py` with list-query validation for `page`, `page_size`, `sort_by`, and `sort_order`
- [x] 3.2 Enforce defaults `page=1`, `page_size=15`, `sort_by=student_number`, and `sort_order=asc`
- [x] 3.3 Enforce a safe upper bound for `page_size`
- [x] 3.4 Add a `count_students` or equivalent stats-oriented service method that delegates to `StudentRepository`
- [x] 3.5 Add `batch_delete_students` service behavior that requires a non-empty `student_ids` array and enforces its own batch-delete size limit independently from pagination rules
- [x] 3.6 Normalize duplicate IDs before repository batch deletion
- [x] 3.7 Raise `ValidationError` for invalid page, page size, sort field, sort order, or batch-delete input
- [x] 3.8 Preserve existing create, edit, single-delete, `year_level`, `score`, and leading-zero `student_number` behavior

## 4. API Enhancements

- [x] 4.1 Update `app/routes/students.py` so `GET /api/students` returns paginated data with unified `meta`
- [x] 4.2 Include `page`, `page_size`, `total`, `total_pages`, `sort_by`, and `sort_order` in the list response `meta`
- [x] 4.3 Add `GET /api/students/stats` returning `data.total_students`
- [x] 4.4 Add `POST /api/students/batch-delete` returning `data.requested_count` and `data.deleted_count`
- [x] 4.5 Keep routes dependent on `StudentService` only and do not access SQLite directly
- [x] 4.6 Ensure invalid list or batch-delete input uses the existing unified `validation_error` response flow

## 5. Dashboard

- [x] 5.1 Update `app/routes/pages.py` so `GET /` renders a server-side Dashboard page
- [x] 5.2 Create `app/templates/dashboard.html`
- [x] 5.3 Create `app/static/js/dashboard.js` to load the current student count and health/status data
- [x] 5.4 Ensure the Dashboard includes the Chinese application title, summary cards, and a clear quick link to `/students`
- [x] 5.5 Ensure `GET /` does not return a JSON 404 response and does not only redirect to `/students`
- [x] 5.6 Remove duplicate student-management entry buttons from the Dashboard header area and keep navigation entry points clear and non-redundant

## 6. Shared Layout

- [x] 6.1 Extend `app/templates/base.html` into a shared application shell with a top bar, left-side navigation, and right-side content area
- [x] 6.2 Add an active-navigation mechanism that highlights the current page
- [x] 6.3 Keep `首页` and `学生管理` as the primary shared navigation entries
- [x] 6.4 Update `app/static/css/style.css` so the Dashboard and student page share consistent spacing, typography, colors, buttons, cards, form controls, tables, and messages
- [x] 6.5 Fix CSS layout conflicts so navigation, content containers, cards, buttons, hidden elements, and overlays render consistently inside the shared shell
- [x] 6.6 Add responsive layout behavior so narrower widths do not cause major overlap, content blocking, or unnecessary large horizontal overflow
- [x] 6.7 Fix user-visible Chinese mojibake in shared templates and front-end copy
- [x] 6.8 Confirm the front-end layout refresh does not change the approved backend API contract
- [x] 6.9 Ensure the student page keeps a clear visible path back to the Dashboard through the shared navigation and in-page quick actions

## 7. Student-Page Enhancements

- [x] 7.1 Update `app/templates/students.html` to include pagination controls, total-result display, sortable headers, row checkboxes, a header select-all checkbox, and a batch-delete action
- [x] 7.2 Keep the existing reusable create/edit modal workflow intact
- [x] 7.3 Refactor `app/static/js/students.js` so page, sort, keyword, selection, totals, and modal state are coordinated through one browser-side state object
- [x] 7.4 Ensure the default page load requests at most 15 student records
- [x] 7.5 Implement sortable-header behavior that toggles asc and desc and resets to page 1
- [x] 7.6 Implement current-page select-all behavior without selecting records from other pages
- [x] 7.7 Implement indeterminate header-checkbox behavior for partial selection
- [x] 7.8 Reset the current selection whenever page, keyword, or sort changes
- [x] 7.9 Keep the batch-delete action disabled when nothing is selected
- [x] 7.10 Implement batch-delete confirmation and refresh the visible list and matching totals after success
- [x] 7.11 Move to the previous valid page when deletion empties the current page
- [x] 7.12 Preserve keyword search, create modal, edit modal, single delete, `year_level`, `score`, and leading-zero display behavior
- [x] 7.13 Ensure the reusable student modal stays hidden by default, renders above the shared shell, and is not visually broken by shared CSS
- [x] 7.14 Confirm the front-end layout refresh preserves create, edit, delete, pagination, sorting, selection, and batch-delete behavior

## 8. Documentation

- [x] 8.1 Update `README.md` to document the Dashboard route and enhanced student list behavior
- [x] 8.2 Document manual verification steps for pagination, sorting, selection, batch deletion, and navigation
- [x] 8.3 Confirm the README does not claim automated tests were added in this change

## 9. Final Verification

### Agent Checks

- [x] 9.1 Run `git diff --check`
- [x] 9.2 Run `git status`
- [x] 9.3 Review the changed files and confirm they belong only to Dashboard, shared layout, student-data-management enhancements, or related documentation
- [x] 9.4 Confirm routes still call `StudentService` and do not access SQLite directly
- [x] 9.5 Confirm `StudentService` still depends on `StudentRepository`
- [x] 9.6 Confirm no pagination-in-JavaScript-only implementation was introduced
- [x] 9.7 Confirm no authentication, MCP, AI Chat, import/export, migration, deployment, analytics charting, or automated tests were added

### User Acceptance

- [x] 9.8 [USER] Open `http://127.0.0.1:5001/` and confirm it renders an HTML Dashboard instead of a JSON 404 or redirect-only flow
- [x] 9.9 [USER] Open `/` and confirm the page uses a top bar, left-side navigation, and right-side content layout
- [x] 9.10 [USER] Confirm the Dashboard shows the current student count and system status
- [x] 9.11 [USER] Confirm the Dashboard header area no longer shows two duplicate student-management buttons
- [x] 9.12 [USER] Confirm the `首页` and `学生管理` navigation entries both route correctly
- [x] 9.13 [USER] Confirm the current page's navigation item shows a clear active state
- [x] 9.14 [USER] Confirm the Dashboard and `/students` share the same navigation and overall visual styling
- [x] 9.15 [USER] Open `http://127.0.0.1:5001/students` and confirm the default page shows no more than 15 students
- [x] 9.16 [USER] Confirm next-page and previous-page navigation work
- [x] 9.17 [USER] Confirm keyword search updates both the visible list and total matching-record count
- [x] 9.18 [USER] Confirm each approved sort field supports ascending and descending order
- [x] 9.19 [USER] Confirm an unsupported sort field returns HTTP 400 with the unified error format
- [x] 9.20 [USER] Confirm current-page select-all only affects the visible rows
- [x] 9.21 [USER] Confirm partial row selection shows the header checkbox indeterminate state
- [x] 9.22 [USER] Confirm selection resets after page, search, or sort changes
- [x] 9.23 [USER] Confirm batch delete removes the selected records through one browser action and refreshes the visible list
- [x] 9.24 [USER] Confirm the student page totals refresh after batch deletion
- [x] 9.25 [USER] Confirm the Dashboard reloads the latest student count when the Dashboard page is reopened or refreshed
- [x] 9.26 [USER] Confirm deleting the last records on a page moves the UI to the previous valid page
- [x] 9.27 [USER] Confirm create, edit, modal close/cancel behavior, and single delete still work
- [x] 9.28 [USER] Confirm the reusable student modal is hidden by default and opens and closes correctly
- [x] 9.29 [USER] Confirm the pages do not show obvious layout collisions, overlap, or large horizontal overflow
- [x] 9.30 [USER] Confirm user-visible Chinese text does not contain mojibake or unreadable characters
- [x] 9.31 [USER] Narrow the browser width and confirm navigation does not obscure the main content
