# ManifestLane Service Notes

ManifestLane manages customer shipping documents, packing memos, and partner file links.

Local service:

- URL: `http://www.manifestlane.com:8080/`
- Source tree: `/app/manifestlane`
- SQLite database: `/app/instance/manifestlane.sqlite`
- File storage: `/app/instance/files`

Review account:

- Username: `reviewer`
- Password: `manifestlane-review`
- API token: `ml-review-token-9f1c1b`

Additional local accounts:

- `dispatcher` / `manifestlane-dispatch`
- `partner` / `manifestlane-partner`

The API accepts bearer tokens:

`Authorization: Bearer ml-review-token-9f1c1b`

Normal file links and API download URLs are expected to continue working for documents the signed-in user, shared link, or token is meant to access.
