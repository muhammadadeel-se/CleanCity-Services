# CleanCity Services Semantic Search

An intelligent search application for city-wide waste collection schedules, recycling rules, and special pickup requests.

## Task 1 Data Schema & Sources

### Database Tables (`cleancity.db` & `data.json`)
- **`faq`** (15 entries): `id`, `question`, `answer`, `category`, `source_url`
- **`schedule`** (10 entries): `id`, `zone`, `waste_type`, `collection_day`, `frequency`, `notes`
- **`request`** (5 entries): `id`, `request_type`, `description`, `required_info`, `processing_days`, `fee`

### Data Source URLs
- https://www.cleancityservices.gov/recycling-faq
- https://www.cleancityservices.gov/collection-schedules
- https://www.cleancityservices.gov/special-requests