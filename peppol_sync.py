#!/usr/bin/env python3
"""
PEPPOL Business Cards Synchronization Script
Streams through large XML export and splits by country/month
"""

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import xml.etree.ElementTree as ET
from typing import Dict, TextIO, Optional
from urllib.request import urlopen
from urllib.error import URLError
import subprocess


class PeppolSync:
    """Main class for PEPPOL export synchronization"""

    def __init__(self, tmp_dir: str = "tmp", log_dir: str = "log", verbose: bool = False, max_bytes: int = 1000000, keep_tmp: bool = False):
        self.tmp_dir = Path(tmp_dir)
        self.log_dir = Path(log_dir)
        self.verbose = verbose
        self.extracts_dir = Path("extracts")
        self.file_stats = {}
        self.max_bytes = max_bytes
        self.keep_tmp = keep_tmp

        # Create directories
        self.tmp_dir.mkdir(exist_ok=True)
        self.log_dir.mkdir(exist_ok=True)
        self.extracts_dir.mkdir(exist_ok=True)



        # Statistics
        self.stats = defaultdict(int)
        self.file_count = 0  # Track number of output files created

        # Setup logging
        log_file = self.log_dir / f"peppol_sync.{datetime.now().strftime('%Y-%m-%d')}.log"
        self.log_handle = open(log_file, "a")

    def log(self, message: str):
        """Write to log file"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_handle.write(f"{timestamp} | {message}\n")
        self.log_handle.flush()

    def progress(self, message: str):
        """Print progress message"""
        if not self.verbose:
            print(f"\r... {message}", end="", flush=True)
        else:
            print(f"... {message}")

    def success(self, message: str):
        """Print success message"""
        print(f"\n✅  {message}")

    def announce(self, message: str):
        """Print announcement"""
        print(f"⏳  {message}")

    def download_xml(self, force: bool = False) -> Path:
        """Download PEPPOL XML export if needed"""
        url = "https://directory.peppol.eu/export/businesscards"
        output_file = self.tmp_dir / "directory-export-business-cards.xml"

        # Skip if file exists and not forcing
        if output_file.exists() and not force:
            file_size_mb = output_file.stat().st_size / (1024 * 1024)
            self.log(f"Using existing file: {output_file} ({file_size_mb:.1f} MB)")
            return output_file

        self.announce(f"Downloading PEPPOL export from {url}")
        self.log(f"download_xml: {url}")

        try:
            # Open URL connection
            with urlopen(url) as response:
                total_size = int(response.headers.get('content-length', 0))
                total_mb = total_size / (1024 * 1024)

                self.log(f"Download size: {total_mb:.1f} MB")
                self.progress(f"Downloading {total_mb:.1f} MB...")

                # Download in chunks
                chunk_size = 8192  # 8KB chunks
                downloaded = 0

                with open(output_file, 'wb') as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded += len(chunk)

                        # Update progress every MB
                        if downloaded % (1024 * 1024) == 0 or not chunk:
                            downloaded_mb = downloaded / (1024 * 1024)
                            if total_size > 0:
                                percent = (downloaded / total_size) * 100
                                self.progress(f"Downloading {downloaded_mb:.1f}/{total_mb:.1f} MB ({percent:.1f}%)")
                            else:
                                self.progress(f"Downloading {downloaded_mb:.1f} MB")

            # Verify file was created
            if output_file.exists():
                file_size_mb = output_file.stat().st_size / (1024 * 1024)
                self.success(f"Downloaded to {output_file.name} ({file_size_mb:.1f} MB)")
                self.log(f"download_xml: {file_size_mb:.1f} MB downloaded")
                return output_file
            else:
                raise FileNotFoundError(f"Download completed but file not found: {output_file}")

        except URLError as e:
            error_msg = f"Failed to download from {url}: {e}"
            self.log(f"download_xml error: {error_msg}")
            raise Exception(error_msg)



    def extract_country(self, element: ET.Element) -> Optional[str]:
        """Extract country code from businesscard element"""
        # Find entity element with countrycode attribute
        entity = element.find(".//{http://www.peppol.eu/schema/pd/businesscard-generic/201907/}entity")
        if entity is None:
            # Try without namespace
            entity = element.find(".//entity")

        if entity is not None:
            return entity.get("countrycode")

        return None

    def extract_date(self, element: ET.Element) -> Optional[str]:
        """Extract registration date from businesscard element"""
        # Find regdate element
        regdate = element.find(".//{http://www.peppol.eu/schema/pd/businesscard-generic/201907/}regdate")
        if regdate is None:
            # Try without namespace
            regdate = element.find(".//regdate")

        if regdate is not None and regdate.text:
            # Extract YYYY-MM-DD from date
            date_str = regdate.text.strip()
            if len(date_str) >= 10:
                return date_str[:10]  # Return YYYY-MM-DD

        return None

    def extract_entity_name(self, element: ET.Element) -> Optional[str]:
        """Extract entity name from businesscard element"""
        entity = element.find(".//{http://www.peppol.eu/schema/pd/businesscard-generic/201907/}entity")
        if entity is None:
            entity = element.find(".//entity")

        if entity is not None:
            name_element = entity.find("{http://www.peppol.eu/schema/pd/businesscard-generic/201907/}name")
            if name_element is None:
                name_element = entity.find("name")

            if name_element is not None:
                return name_element.get("name")

        return None

    def element_to_string(self, element: ET.Element) -> str:
        """Convert element to XML string without namespace prefixes"""
        # Convert to string
        xml_str = ET.tostring(element, encoding="unicode", method="xml")

        # Remove namespace declarations from the businesscard tag
        # This keeps the content clean
        xml_str = xml_str.replace(' xmlns:ns0="http://www.peppol.eu/schema/pd/businesscard-generic/201907/"', '')
        xml_str = xml_str.replace(' xmlns="http://www.peppol.eu/schema/pd/businesscard-generic/201907/"', '')
        xml_str = xml_str.replace('ns0:', '')

        return xml_str

    def process_xml(self, input_file: Path):
        """Process XML file in streaming mode - single pass"""
        self.announce(f"Processing {input_file.name} in single pass")
        self.log(f"Starting XML processing: {input_file}")

        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        # Use iterparse for streaming
        context = ET.iterparse(str(input_file), events=("end",))

        processed_cards = 0

        # Track the currently open file
        current_file_handle = None
        current_file_path = None

        try:
            for event, elem in context:
                if elem.tag.endswith("businesscard"):
                    processed_cards += 1

                    country = self.extract_country(elem)
                    date = self.extract_date(elem)

                    if country:
                        self.stats[f"country_{country}"] += 1

                        if not date:
                            entity_name = self.extract_entity_name(elem)
                            safe_name = ""
                            if entity_name:
                                # Filter for alphanumeric characters only
                                filtered_name = "".join(filter(str.isalnum, entity_name))
                                safe_name = filtered_name[:5].upper()

                            if safe_name:
                                date = f"2000-{safe_name}"
                            else:
                                date = "2000-UNKNOWN"

                        self.stats[f"date_{date}"] += 1

                        # Get stats for this country
                        stats = self.file_stats.setdefault(country, {'sequence': 1})

                        # Determine output path
                        output_path = self.extracts_dir / country / f"business-cards.{stats['sequence']:06d}.xml"

                        # Check if we need to roll over to a new file
                        if output_path.exists() and output_path.stat().st_size > self.max_bytes:
                            stats['sequence'] += 1
                            output_path = self.extracts_dir / country / f"business-cards.{stats['sequence']:06d}.xml"

                        # If the file we need to write to is different from the currently open one
                        if output_path != current_file_path:
                            # Close the previously open file
                            if current_file_handle:
                                current_file_handle.write('</root>\n')
                                current_file_handle.close()

                            # Check if file exists to decide on writing header
                            file_exists = output_path.exists()

                            if not file_exists:
                                output_path.parent.mkdir(parents=True, exist_ok=True)
                                current_file_handle = open(output_path, "w", encoding="utf-8")
                                current_file_handle.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                                current_file_handle.write('<root xmlns="http://www.peppol.eu/schema/pd/businesscard-generic/201907/" version="2">\n')
                                self.log(f"Created output file: {output_path}")
                                self.file_count += 1
                            else:
                                # File exists, open in r+ mode to remove </root>
                                current_file_handle = open(output_path, "r+", encoding="utf-8")
                                current_file_handle.seek(0, os.SEEK_END)
                                position = current_file_handle.tell() - len('</root>\n')
                                current_file_handle.seek(position, os.SEEK_SET)
                                current_file_handle.truncate()

                            current_file_path = output_path

                        # Write businesscard element
                        xml_str = self.element_to_string(elem)
                        for line in xml_str.split('\n'):
                            if line.strip():
                                current_file_handle.write(f"  {line}\n")



                    if processed_cards % 10000 == 0:
                        self.progress(f"Processed {processed_cards:,} business cards, {self.file_count} files opened...")

                    elem.clear()

        finally:
            # Close the last open file
            if current_file_handle:
                current_file_handle.write('</root>\n')
                current_file_handle.close()

        self.success(f"Processed {processed_cards:,} business cards")
        self.log(f"Processing complete: {processed_cards} cards processed")

        # Print statistics
        countries = [k.replace("country_", "") for k in self.stats.keys() if k.startswith("country_")]
        self.log(f"Found {len(countries)} countries")
        self.log(f"Created {self.file_count} output files")

        return processed_cards

    def sync(self, force_download: bool = False):
        """Main sync operation"""
        self.log("Starting sync operation")
        self.announce(f"Max bytes per file: {self.max_bytes:,}")

        # Download XML file if needed
        try:
            input_file = self.download_xml(force=force_download)
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return 1

        # Show file size
        file_size_mb = input_file.stat().st_size / (1024 * 1024)
        self.announce(f"Processing file: {input_file.name} ({file_size_mb:.1f} MB)")

        # Process XML
        try:
            cards_processed = self.process_xml(input_file)

            # Show summary
            print("\n📊 Summary:")
            print(f"   Total business cards: {cards_processed:,}")
            print(f"   Output files created: {self.file_count}")
            print(f"   Output directory: {self.extracts_dir}/")

            self.success("Sync complete!")
            return 0

        except Exception as e:
            print(f"\n❌ Error: {e}")
            self.log(f"Error: {e}")
            return 1

        finally:
            self.log_handle.close()

    def cleanup(self):
        """Close any open resources and clean up temp files"""
        # Close log file
        if self.log_handle and not self.log_handle.closed:
            self.log_handle.close()

        # Clean up tmp files unless keep_tmp is set
        if not self.keep_tmp and self.tmp_dir.exists():
            import shutil
            try:
                files_removed = 0
                for file_path in self.tmp_dir.glob("*"):
                    if file_path.is_file():
                        file_path.unlink()
                        files_removed += 1

                if files_removed > 0:
                    print(f"\n🧹 Cleaned up {files_removed} temporary file(s) from {self.tmp_dir}/")
            except Exception as e:
                print(f"\n⚠️  Warning: Could not clean up tmp files: {e}")

    def show_huge_files(self, number: int = 10) -> int:
        """Show the N largest XML files under extracts/"""
        self.announce(f"Finding the {number} largest XML files under {self.extracts_dir}/")
        command = f"find {self.extracts_dir} -name \"*.xml\" -type f -exec du -h {{}} + | sort -rh | head -n {number}"
        
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
            print(result.stdout)
            self.success(f"Displayed {number} largest files.")
            return 0
        except subprocess.CalledProcessError as e:
            print(f"❌ Error executing command: {e}")
            print(f"Stderr: {e.stderr}")
            self.log(f"Error in show_huge_files: {e.stderr}")
            return 1


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Synchronize PEPPOL export into git-managed files",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "action",
        choices=["sync", "check", "download", "huge"],
        help="Action to perform"
    )

    parser.add_argument(
        "-T", "--tmp-dir",
        default="tmp",
        help="Temporary directory (default: tmp)"
    )

    parser.add_argument(
        "-L", "--log-dir",
        default="log",
        help="Log directory (default: log)"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force re-download of XML file even if it exists"
    )

    parser.add_argument(
        "-n", "--number",
        type=int,
        default=10,
        help="Number of largest files to show (default: 10)"
    )

    parser.add_argument(
        "--max-bytes",
        type=int,
        default=1000000,
        help="Maximum number of bytes per output file (default: 1000000)"
    )

    parser.add_argument(
        "--keep-tmp",
        action="store_true",
        help="Keep temporary files after processing (default: delete)"
    )

    args = parser.parse_args()

    # Create sync instance
    syncer = PeppolSync(
        tmp_dir=args.tmp_dir,
        log_dir=args.log_dir,
        verbose=args.verbose,
        max_bytes=args.max_bytes,
        keep_tmp=args.keep_tmp
    )

    try:
        if args.action == "sync":
            return syncer.sync(force_download=args.force)
        elif args.action == "download":
            try:
                input_file = syncer.download_xml(force=args.force)
                file_size_mb = input_file.stat().st_size / (1024 * 1024)
                print(f"\n📁 Downloaded file:")
                print(f"   Location: {input_file}")
                print(f"   Size: {file_size_mb:.1f} MB")
                return 0
            except Exception as e:
                print(f"\n❌ Download failed: {e}")
                return 1
        elif args.action == "check":
            print("✅ Configuration OK")
            print(f"   Temp directory: {syncer.tmp_dir}")
            print(f"   Log directory: {syncer.log_dir}")
            print(f"   Extracts directory: {syncer.extracts_dir}")
            return 0
        elif args.action == "huge":
            return syncer.show_huge_files(args.number)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        return 1
    finally:
        syncer.cleanup()


if __name__ == "__main__":
    sys.exit(main())
