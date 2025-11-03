# PEPPOL SYNC

* download https://directory.peppol.eu/export/businesscards export file => tmp/directory-export-business-cards.xml
* split the massive xml file up in extract files per month and per country => extracts/2025-10/business.NO.xml
* do `git add`, `git commit`, `git push`
* daily GitHub job: `peppol_sync.sh sync`

