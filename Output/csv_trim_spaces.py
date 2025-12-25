#!/usr/bin/env python3
"""
CSV Space Trimmer - Remove extra spaces from CSV entries
"""

import argparse
import csv
import sys
import re
import zipfile
import tempfile
import shutil
from pathlib import Path
from io import StringIO, BytesIO

__version__ = "1.1.0"


def trim_spaces(text):
    """
    Remove leading/trailing spaces and reduce multiple spaces to single space.
    
    Args:
        text: String to trim
        
    Returns:
        Trimmed string with single spaces between words
    """
    if not isinstance(text, str):
        return text
    # Replace multiple spaces with single space, then strip
    return re.sub(r'\s+', ' ', text).strip()


def process_csv(input_file, delimiter='|'):
    """
    Process CSV file to trim spaces from all entries.
    
    Args:
        input_file: Path to input CSV file or file-like object
        delimiter: CSV delimiter character
        
    Returns:
        List of processed rows
    """
    rows = []
    
    try:
        # Handle both file paths and file-like objects
        if isinstance(input_file, (str, Path)):
            with open(input_file, 'r', encoding='utf-8', newline='') as f:
                reader = csv.reader(f, delimiter=delimiter)
                for row in reader:
                    trimmed_row = [trim_spaces(cell) for cell in row]
                    rows.append(trimmed_row)
        else:
            reader = csv.reader(input_file, delimiter=delimiter)
            for row in reader:
                trimmed_row = [trim_spaces(cell) for cell in row]
                rows.append(trimmed_row)
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)
    
    return rows


def write_csv(output_file, rows, delimiter='|'):
    """
    Write processed rows to CSV file or file-like object.
    
    Args:
        output_file: Path to output CSV file or file-like object
        rows: List of rows to write
        delimiter: CSV delimiter character
    """
    try:
        # Handle both file paths and file-like objects
        if isinstance(output_file, (str, Path)):
            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f, delimiter=delimiter)
                writer.writerows(rows)
        else:
            writer = csv.writer(output_file, delimiter=delimiter)
            writer.writerows(rows)
    except Exception as e:
        print(f"Error writing file: {e}", file=sys.stderr)
        sys.exit(1)


def process_zip(zip_path, delimiter='|'):
    """
    Process all CSV files in a ZIP archive.
    
    Args:
        zip_path: Path to ZIP file
        delimiter: CSV delimiter character
    """
    try:
        # Create a temporary file for the updated zip
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        temp_zip.close()
        
        csv_count = 0
        total_rows = 0
        
        with zipfile.ZipFile(zip_path, 'r') as zip_read:
            with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zip_write:
                # Process each file in the archive
                for file_info in zip_read.filelist:
                    file_data = zip_read.read(file_info.filename)
                    
                    # Check if file is a CSV
                    if file_info.filename.lower().endswith('.csv'):
                        print(f"  Processing: {file_info.filename}")
                        
                        # Decode and process CSV
                        csv_text = file_data.decode('utf-8')
                        csv_file = StringIO(csv_text)
                        
                        rows = process_csv(csv_file, delimiter)
                        total_rows += len(rows)
                        
                        # Write processed CSV to string
                        output = StringIO()
                        write_csv(output, rows, delimiter)
                        processed_data = output.getvalue().encode('utf-8')
                        
                        # Write to new zip
                        zip_write.writestr(file_info, processed_data)
                        csv_count += 1
                    else:
                        # Copy non-CSV files as-is
                        zip_write.writestr(file_info, file_data)
        
        # Replace original zip with processed version
        shutil.move(temp_zip.name, zip_path)
        
        print(f"\nSuccessfully processed {csv_count} CSV file(s) with {total_rows} total rows.")
        
    except zipfile.BadZipFile:
        print(f"Error: '{zip_path}' is not a valid ZIP file.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error processing ZIP file: {e}", file=sys.stderr)
        # Clean up temp file if it exists
        try:
            Path(temp_zip.name).unlink(missing_ok=True)
        except:
            pass
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Trim extra spaces from CSV entries. Removes leading/trailing '
                    'spaces and reduces multiple spaces to single space between words.\n\n'
                    'Supports both individual CSV files and ZIP archives containing CSV files.',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        'filename',
        help='CSV or ZIP file to process (will be overwritten with trimmed version)'
    )
    
    parser.add_argument(
        '-d', '--delimiter',
        default='|',
        help='CSV delimiter character (default: "|")'
    )
    
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )
    
    args = parser.parse_args()
    
    # Validate file exists
    input_path = Path(args.filename)
    if not input_path.exists():
        print(f"Error: File '{args.filename}' does not exist.", file=sys.stderr)
        sys.exit(1)
    
    # Determine file type and process accordingly
    if args.filename.lower().endswith('.zip'):
        # Process ZIP file
        print(f"Processing ZIP archive '{args.filename}' with delimiter '{args.delimiter}'...")
        process_zip(args.filename, args.delimiter)
        print(f"ZIP file '{args.filename}' has been updated.")
    else:
        # Process single CSV file
        print(f"Processing '{args.filename}' with delimiter '{args.delimiter}'...")
        rows = process_csv(args.filename, args.delimiter)
        
        # Write back to same file
        write_csv(args.filename, rows, args.delimiter)
        
        print(f"Successfully trimmed spaces in {len(rows)} rows.")
        print(f"File '{args.filename}' has been updated.")


if __name__ == '__main__':
    main()
