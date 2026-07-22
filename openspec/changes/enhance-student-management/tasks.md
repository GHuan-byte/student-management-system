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

- [ ] 2.1 Extend `app/repositories/student_repository.py` with a paginated list method that supports `keyword`, `page`, `page_size`, `sort_by`, and `sort_order`
- [ ] 2.2 Keep keyword filtering aligned with the current searchable fields: `student_number`, `name`, `major`, `phone`, and `email`
- [ ] 2.3 Add an explicit sortable-field whitelist in the repository for `student_number`, `name`, `gender`, `age`, `major`, `year_level`, and `score`
- [ ] 2.4 Ensure repository list queries compute the matching-record total separately from the current page result
- [ ] 2.5 Add `count_students` to return the current SQLite-backed total
- [ ] 2.6 Add `batch_delete_students` using parameterized SQL and one transaction
- [ ] 2.7 Ensure repository writes still commit successful changes, roll back failures, and close connections reliably

## 3. Service Enhancements

- [ ] 3.1 Extend `app/services/student_service.py` with list-query validation for `page`, `page_size`, `sort_by`, and `sort_order`
- [ ] 3.2 Enforce defaults `page=1`, `page_size=15`, `sort_by=student_number`, and `sort_order=asc`
- [ ] 3.3 Enforce a safe upper bound for `page_size`
- [ ] 3.4 Add a `count_students` or equivalent stats-oriented service method that delegates to `StudentRepository`
- [ ] 3.5 Add `batch_delete_students` service behavior that requires a non-empty `student_ids` array
- [ ] 3.6 Normalize duplicate IDs before repository batch deletion
- [ ] 3.7 Raise `ValidationError` for invalid page, page size, sort field, sort order, or batch-delete input
- [ ] 3.8 Preserve existing create, edit, single-delete, `year_level`, `score`, and leading-zero `student_number` behavior

## 4. API Enhancements

- [ ] 4.1 Update `app/routes/students.py` so `GET /api/students` returns paginated data with unified `meta`
- [ ] 4.2 Include `page`, `page_size`, `total`, `total_pages`, `sort_by`, and `sort_order` in the list response `meta`
- [ ] 4.3 Add `GET /api/students/stats` returning `data.total_students`
- [ ] 4.4 Add `POST /api/students/batch-delete` returning `data.requested_count` and `data.deleted_count`
- [ ] 4.5 Keep routes dependent on `StudentService` only and do not access SQLite directly
- [ ] 4.6 Ensure invalid list or batch-delete input uses the existing unified `validation_error` response flow

## 5. Dashboard

- [ ] 5.1 Update `app/routes/pages.py` so `GET /` renders a server-side Dashboard page
- [ ] 5.2 Create `app/templates/dashboard.html`
- [ ] 5.3 Create `app/static/js/dashboard.js` to load the current student count and health/status data
- [ ] 5.4 Ensure the Dashboard includes the Chinese application title, summary cards, and a clear quick link to `/students`
- [ ] 5.5 Ensure `GET /` does not return a JSON 404 response and does not only redirect to `/students`

## 6. Shared Layout

- [ ] 6.1 Extend `app/templates/base.html` with the shared header and navigation for `首页` and `学生管理`
- [ ] 6.2 Add an active-navigation mechanism that highlights the current page
- [ ] 6.3 Update `app/static/css/style.css` so the Dashboard and student page share consistent spacing, typography, colors, buttons, cards, and messages
- [ ] 6.4 Ensure the student page keeps a clear visible path back to the Dashboard

## 7. Student-Page Enhancements

- [ ] 7.1 Update `app/templates/students.html` to include pagination controls, total-result display, sortable headers, row checkboxes, a header select-all checkbox, and a batch-delete action
- [ ] 7.2 Keep the existing reusable create/edit modal workflow intact
- [ ] 7.3 Refactor `app/static/js/students.js` so page, sort, keyword, selection, totals, and modal state are coordinated through one browser-side state object
- [ ] 7.4 Ensure the default page load requests at most 15 student records
- [ ] 7.5 Implement sortable-header behavior that toggles asc and desc and resets to page 1
- [ ] 7.6 Implement current-page select-all behavior without selecting records from other pages
- [ ] 7.7 Implement indeterminate header-checkbox behavior for partial selection
- [ ] 7.8 Reset the current selection whenever page, keyword, or sort changes
- [ ] 7.9 Keep the batch-delete action disabled when nothing is selected
- [ ] 7.10 Implement batch-delete confirmation and refresh the list and Dashboard count after success
- [ ] 7.11 Move to the previous valid page when deletion empties the current page
- [ ] 7.12 Preserve keyword search, create modal, edit modal, single delete, `year_level`, `score`, and leading-zero display behavior

## 8. Documentation

- [ ] 8.1 Update `README.md` to document the Dashboard route and enhanced student list behavior
- [ ] 8.2 Document manual verification steps for pagination, sorting, selection, batch deletion, and navigation
- [ ] 8.3 Confirm the README does not claim automated tests were added in this change

## 9. Final Verification

### Agent Checks

- [ ] 9.1 Run `git diff --check`
- [ ] 9.2 Run `git status`
- [ ] 9.3 Review the changed files and confirm they belong only to Dashboard, shared layout, student-data-management enhancements, or related documentation
- [ ] 9.4 Confirm routes still call `StudentService` and do not access SQLite directly
- [ ] 9.5 Confirm `StudentService` still depends on `StudentRepository`
- [ ] 9.6 Confirm no pagination-in-JavaScript-only implementation was introduced
- [ ] 9.7 Confirm no authentication, MCP, AI Chat, import/export, migration, deployment, analytics charting, or automated tests were added

### User Acceptance

- [ ] 9.8 [USER] Open `http://127.0.0.1:5001/` and confirm it renders an HTML Dashboard instead of a JSON 404 or redirect-only flow
- [ ] 9.9 [USER] Confirm the Dashboard and `/students` share the same navigation and active-page styling
- [ ] 9.10 [USER] Confirm the Dashboard shows the current student count and system status
- [ ] 9.11 [USER] Open `http://127.0.0.1:5001/students` and confirm the default page shows no more than 15 students
- [ ] 9.12 [USER] Confirm next-page and previous-page navigation work
- [ ] 9.13 [USER] Confirm keyword search updates both the visible list and total matching-record count
- [ ] 9.14 [USER] Confirm each approved sort field supports ascending and descending order
- [ ] 9.15 [USER] Confirm an unsupported sort field returns HTTP 400 with the unified error format
- [ ] 9.16 [USER] Confirm current-page select-all only affects the visible rows
- [ ] 9.17 [USER] Confirm partial row selection shows the header checkbox indeterminate state
- [ ] 9.18 [USER] Confirm selection resets after page, search, or sort changes
- [ ] 9.19 [USER] Confirm batch delete removes the selected records through one browser action and refreshes the visible list
- [ ] 9.20 [USER] Confirm the displayed student count refreshes after batch deletion
- [ ] 9.21 [USER] Confirm deleting the last records on a page moves the UI to the previous valid page
- [ ] 9.22 [USER] Confirm create, edit, modal close/cancel behavior, and single delete still work
- [ ] 9.23 [USER] Confirm the Dashboard and student page remain visually consistent
