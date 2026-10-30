# Backup
Use sqlite3 online backup API, not raw WAL copy during writes. Back up config and state to owner-only location; cache is reconstructible and excluded by default. Restore validates schema version and integrity_check, permissions and checksums. Test restore in disposable environment.
