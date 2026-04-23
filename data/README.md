# Local Data

Use this folder for local-only inputs such as:

- `profile.txt`
- `email.env`

The repo ignores those two files so credentials and personal profile data do not get committed.

The default helper scripts now assume:

- all sources
- `10` checked jobs per source
- `5` emailed links
- one script for LLM/profile match ranking
- one script for newest-job ranking
