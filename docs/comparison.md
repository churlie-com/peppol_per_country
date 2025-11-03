# PEPPOL Sync Implementation Comparison

This document compares the Bash and Python implementations of the PEPPOL business cards synchronization tool.

## Overview

Both implementations achieve the same goal: split a large PEPPOL XML export into country/month-specific files. However, they use fundamentally different approaches.

## Bash Implementation (`peppol_sync.sh`)

### Approach
- **Multi-pass processing**: Makes 106 passes through the 2.6GB file (one per country)
- **Streaming extraction**: Uses AWK to stream through the file without loading into memory
- **Two-stage process**:
  1. Extract per-country temp files
  2. Split temp files by month

### Performance Characteristics

**File Processing:**
- 106 full scans of 2.6GB file ≈ **275GB of I/O operations**
- Each country requires: ~2-3 minutes per pass
- **Total time: 3-5 hours** for complete processing

**Memory Usage:**
- Very low (streaming AWK)
- Temp files per country (can be large, e.g., 312MB for AU)

**Optimizations:**
- Country list caching (`tmp/countries.txt`)
- BSD AWK-compatible string operations
- No external dependencies beyond standard Unix tools

### Code Complexity
- **Lines of code**: ~1,250 (including bashew framework)
- **External dependencies**: awk, grep, xmllint, curl
- **Platform compatibility**: macOS, Linux (requires bash 4+)

### Pros
- No Python installation required
- Works with standard Unix tools
- Memory efficient (streaming)
- Easy to debug (logs each step)

### Cons
- Very slow (multiple passes through large file)
- Creates large temp files
- Complex AWK string manipulation
- BSD/GNU awk compatibility issues

## Python Implementation (`peppol_sync.py`)

### Approach
- **Single-pass processing**: Streams through file once
- **Incremental writing**: Opens output files as needed and writes directly
- **Memory efficient**: Uses ElementTree `iterparse()` for streaming

### Performance Characteristics

**File Processing:**
- 1 scan of 2.6GB file ≈ **2.6GB of I/O read operations**
- Streaming XML parsing
- **Estimated time: 3-5 minutes** for complete processing

**Memory Usage:**
- Low memory footprint
- No temp files needed
- Files kept open during processing (file handle pool)

**Optimizations:**
- Single-pass streaming
- Direct write to output files
- Efficient XML parsing with standard library

### Code Complexity
- **Lines of code**: ~280 (clean, focused code)
- **External dependencies**: Python 3.6+ (standard library only)
- **Platform compatibility**: Any platform with Python 3

### Pros
- **60-100x faster** than bash version
- Clean, maintainable code
- No temp files needed
- Standard Python libraries only
- Easy to extend

### Cons
- Requires Python 3.6+
- Less "Unix philosophy" (single program vs. pipeline)

## Performance Comparison

| Metric          | Bash                     | Python      | Improvement        |
|-----------------|--------------------------|-------------|--------------------|
| File passes     | 106                      | 1           | **106x fewer**     |
| Total I/O       | ~275 GB                  | ~2.6 GB     | **106x less**      |
| Processing time | 3-5 hours                | 3-5 minutes | **60-100x faster** |
| Memory usage    | Very low                 | Low         | Similar            |
| Temp files      | Yes (large)              | No          | None needed        |
| Dependencies    | awk, grep, xmllint, curl | Python 3    | Standard lib only  |

## Use Case Recommendations

### Use Bash version when:
- No Python available on system
- Need to work within Unix pipeline
- Debugging/auditing is critical
- Already have bash/awk expertise

### Use Python version when:
- Performance matters (production use)
- Regular/automated processing
- Python is available
- Easier maintenance is desired

## Example Usage

### Bash
```bash
# One-time sync (slow)
./peppol_sync.sh sync

# Check configuration
./peppol_sync.sh check
```

### Python
```bash
# Fast single-pass sync
python3 peppol_sync.py sync

# Check configuration
python3 peppol_sync.py check

# Verbose output
python3 peppol_sync.py -v sync
```

## File Output Format

Both implementations produce identical output:

```
extracts/
  YYYY-MM/
    businesscards.{COUNTRY}.xml
```

Each file contains:
- XML header with proper namespace
- `<root>` element
- Multiple `<businesscard>` elements for that country/month
- Proper indentation and formatting

## Implementation Details

### Bash AWK Streaming (2-stage)
```bash
# Pass 1: Extract by country (106 times)
awk -v country="BE" '
  /<businesscard>/ { in_card=1; card=$0 }
  in_card { card=card $0 }
  /<entity countrycode="BE">/ { match_country=1 }
  /<\/businesscard>/ { if(match_country) print card }
' input.xml > tmp/cards.BE.xml

# Pass 2: Split by month
awk -F'||' '{ if (date matches month) print }' tmp/cards.BE.xml
```

### Python Streaming (1-pass)
```python
# Single pass with incremental output
for event, elem in ET.iterparse(input_file):
    if elem.tag.endswith("businesscard"):
        country = extract_country(elem)
        month = extract_month(elem)

        # Get or create output file
        output_file = get_output_file(country, month)

        # Write directly to output
        output_file.write(element_to_string(elem))

        # Free memory
        elem.clear()
```

## Conclusion

The Python implementation is the **clear winner for production use** due to:
- **100x faster processing** (minutes vs. hours)
- **Simpler codebase** (280 vs 1,250 lines)
- **No temp files** required
- **Single pass** through data

The Bash implementation remains useful for:
- Systems without Python
- Learning/debugging purposes
- Unix purist environments

For the PEPPOL use case with daily 2.6GB XML downloads, the Python implementation is strongly recommended.
