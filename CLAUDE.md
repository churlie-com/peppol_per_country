# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a bash-based automation tool that synchronizes PEPPOL business directory exports into git-managed files. The project downloads a large XML export from directory.peppol.eu, splits it into country/month-specific extracts, and commits the changes to git.

## Key Commands

### Main Script Operations
```bash
# Full sync operation (download, split, commit & push)
./peppol_sync.sh sync

# Check script configuration and requirements
./peppol_sync.sh check

# Generate example .env file
./peppol_sync.sh env > .env

# Update script to latest version
./peppol_sync.sh update
```

### Script Flags
- `-h, --help`: Show usage information
- `-V, --VERBOSE`: Enable debug output
- `-Q, --QUIET`: Suppress all output
- `-f, --FORCE`: Skip confirmations (auto-yes)
- `-L, --LOG_DIR <dir>`: Set log folder (default: log)
- `-T, --TMP_DIR <dir>`: Set temp folder (default: tmp)

## Architecture

### Main Script: peppol_sync.sh

This is a bashew-based script (https://github.com/pforret/bashew) with the following structure:

**Core Functions** (lines 58-95):
- `Script:main()`: Main entry point that routes to sync/check/update actions

**Custom Helper Functions** (lines 101-131):
- `download_huge_xml()`: Downloads export from https://directory.peppol.eu/export/businesscards
- `split_into_extracts()`: Splits XML into per-country/per-month files in extracts/
- `commit_and_push()`: Handles git operations; uses `setver auto` locally or `Gha:finish` in GitHub Actions

**Bashew Framework** (lines 134-1098):
- Complete bash framework with option parsing, logging, error handling, etc.
- Do not modify code below line 134 unless updating bashew version

### Automation

**GitHub Actions** (.github/workflows/):
- Daily cron job at 09:15 UTC
- Runs `./peppol_sync.sh sync`
- Automatically commits and pushes changes if XML export has updates

### Data Structure

**Output Files**:
- `extracts/`: Contains split XML files organized as `YYYY-MM/business.{COUNTRY_CODE}.xml`
- `tmp/`: Temporary files (gitignored)
- `log/`: Log files (gitignored)

## Development Notes

### Bashew Framework
This script is built on bashew 1.22.0. Key features:
- Automatic option/flag parsing via `Option:config()`
- Colored output with IO:print/debug/success/alert/die functions
- Requirement checking with `Os:require`
- GitHub Actions integration via `Gha:finish()`

### Git Workflow
- The script detects if running in GitHub Actions via `RUNNER_OS` environment variable
- Local runs: uses `setver auto` for versioning
- GitHub Actions: uses `Gha:finish()` which sets git config and commits with timestamp

### Required Tools
- `awk`: Used throughout the bashew framework and for text processing
- Additional requirements should be added via `Os:require` calls in helper functions

## Implementation Status

**Incomplete Functions**:
- `download_huge_xml()`: Function stub exists but needs implementation (line 101)
- `split_into_extracts()`: Function stub exists but needs implementation (line 112)

These functions need to be implemented to:
1. Download from https://directory.peppol.eu/export/businesscards to tmp/directory-export-business-cards.xml
2. Parse and split the XML by country and month into extracts/ folder