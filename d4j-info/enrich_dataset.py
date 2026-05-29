#!/usr/bin/env python3
"""
Enrich single_function_repair.json with Defects4J metadata:
- test_patch: The test patch content
- relevant_tests: List of all relevant test classes
- trigger_tests: List of tests that trigger the bug (failing tests)
- bug_report_id: Bug report ID from issue tracker
- bug_report_url: URL to the bug report
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Path to Defects4J framework
DEFECTS4J_HOME = os.path.expanduser("~/defects4j")
DEFECTS4J_BIN = os.path.join(DEFECTS4J_HOME, "framework", "bin", "defects4j")

def run_defects4j_export(project, bug_id, property_name):
    """
    Run defects4j export command to get bug metadata
    """
    try:
        result = subprocess.run(
            [DEFECTS4J_BIN, "export", "-p", project, "-b", str(bug_id), "-o", property_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            print(f"Warning: Failed to export {property_name} for {project}-{bug_id}: {result.stderr}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"Error exporting {property_name} for {project}-{bug_id}: {e}", file=sys.stderr)
        return None

def get_test_patch(project, bug_id):
    """
    Read the test patch file from Defects4J framework
    """
    patch_path = os.path.join(DEFECTS4J_HOME, "framework", "projects", project, "patches", bug_id, "test.patch")
    
    if os.path.exists(patch_path):
        try:
            with open(patch_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading test patch for {project}-{bug_id}: {e}", file=sys.stderr)
            return None
    else:
        print(f"Warning: Test patch not found: {patch_path}", file=sys.stderr)
        return None

def get_relevant_tests(project, bug_id):
    """
    Get list of all relevant test classes
    """
    tests_path = os.path.join(DEFECTS4J_HOME, "framework", "projects", project, "relevant_tests", bug_id)
    
    if os.path.exists(tests_path):
        try:
            with open(tests_path, 'r', encoding='utf-8') as f:
                # Split by newlines and filter empty lines
                tests = [line.strip() for line in f if line.strip()]
                return tests
        except Exception as e:
            print(f"Error reading relevant tests for {project}-{bug_id}: {e}", file=sys.stderr)
            return []
    else:
        print(f"Warning: Relevant tests not found: {tests_path}", file=sys.stderr)
        return []

def get_trigger_tests(project, bug_id):
    """
    Get list of tests that trigger (fail on) the bug
    """
    tests_path = os.path.join(DEFECTS4J_HOME, "framework", "projects", project, "trigger_tests", bug_id)
    
    if os.path.exists(tests_path):
        try:
            with open(tests_path, 'r', encoding='utf-8') as f:
                # Format: --- test.class::method or --- test.class
                tests = []
                for line in f:
                    line = line.strip()
                    if line.startswith('---'):
                        test = line[3:].strip()
                        if test:
                            tests.append(test)
                return tests
        except Exception as e:
            print(f"Error reading trigger tests for {project}-{bug_id}: {e}", file=sys.stderr)
            return []
    else:
        print(f"Warning: Trigger tests not found: {tests_path}", file=sys.stderr)
        return []

def get_bug_report_info(project, bug_id):
    """
    Get bug report ID and URL from commit-db file
    """
    commit_db_path = os.path.join(DEFECTS4J_HOME, "framework", "projects", project, "commit-db")
    
    if os.path.exists(commit_db_path):
        try:
            with open(commit_db_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    # Format: bug_id,buggy_commit,fixed_commit,report_id,report_url
                    parts = line.split(',')
                    if len(parts) >= 5 and parts[0] == bug_id:
                        return {
                            "bug_report_id": parts[3],
                            "bug_report_url": parts[4]
                        }
        except Exception as e:
            print(f"Error reading commit-db for {project}-{bug_id}: {e}", file=sys.stderr)
    
    return {
        "bug_report_id": None,
        "bug_report_url": None
    }

def enrich_bug_entry(bug_key, bug_data):
    """
    Enrich a single bug entry with Defects4J metadata
    """
    # Parse bug key (format: "Project-BugId", e.g., "Chart-1")
    if '-' not in bug_key:
        print(f"Warning: Invalid bug key format: {bug_key}", file=sys.stderr)
        return bug_data
    
    # Split on the last hyphen to handle project names with hyphens
    parts = bug_key.rsplit('-', 1)
    project = parts[0]
    bug_id = parts[1]
    
    print(f"Processing {project}-{bug_id}...", end=' ')
    
    # Get test patch
    test_patch = get_test_patch(project, bug_id)
    
    # Get relevant tests
    relevant_tests = get_relevant_tests(project, bug_id)
    
    # Get trigger tests
    trigger_tests = get_trigger_tests(project, bug_id)
    
    # Get bug report info
    bug_report = get_bug_report_info(project, bug_id)
    
    # Add to bug data
    enriched_data = bug_data.copy()
    enriched_data["test_patch"] = test_patch
    enriched_data["relevant_tests"] = relevant_tests
    enriched_data["trigger_tests"] = trigger_tests
    enriched_data["bug_report_id"] = bug_report["bug_report_id"]
    enriched_data["bug_report_url"] = bug_report["bug_report_url"]
    
    print(f"✓ (test_patch: {'Yes' if test_patch else 'No'}, "
          f"relevant_tests: {len(relevant_tests)}, "
          f"trigger_tests: {len(trigger_tests)})")
    
    return enriched_data

def main():
    # Check if Defects4J exists
    if not os.path.exists(DEFECTS4J_BIN):
        print(f"Error: Defects4J not found at {DEFECTS4J_BIN}", file=sys.stderr)
        print(f"Please ensure Defects4J is installed at {DEFECTS4J_HOME}", file=sys.stderr)
        sys.exit(1)
    
    # Load the original JSON file
    input_file = "single_function_repair.json"
    output_file = "single_function_repair_enriched.json"
    
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found", file=sys.stderr)
        sys.exit(1)
    
    print(f"Loading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Found {len(data)} bugs to process\n")
    
    # Enrich each bug entry
    enriched_data = {}
    processed = 0
    skipped = 0
    
    for bug_key, bug_data in data.items():
        try:
            enriched_data[bug_key] = enrich_bug_entry(bug_key, bug_data)
            processed += 1
        except Exception as e:
            print(f"Error processing {bug_key}: {e}", file=sys.stderr)
            enriched_data[bug_key] = bug_data  # Keep original data
            skipped += 1
    
    # Save enriched data
    print(f"\nSaving enriched data to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(enriched_data, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print("\n" + "="*60)
    print("ENRICHMENT COMPLETE")
    print("="*60)
    print(f"Total bugs: {len(data)}")
    print(f"Successfully processed: {processed}")
    print(f"Skipped (errors): {skipped}")
    print(f"Output file: {output_file}")
    print("="*60)
    
    # Show sample of enriched entry
    if enriched_data:
        sample_key = list(enriched_data.keys())[0]
        sample = enriched_data[sample_key]
        print("\nSample enriched entry:")
        print(f"Bug: {sample_key}")
        print(f"  - test_patch: {'Present' if sample.get('test_patch') else 'None'} "
              f"({len(sample.get('test_patch', '')) if sample.get('test_patch') else 0} chars)")
        print(f"  - relevant_tests: {len(sample.get('relevant_tests', []))} tests")
        print(f"  - trigger_tests: {len(sample.get('trigger_tests', []))} tests")
        if sample.get('trigger_tests'):
            print(f"    Examples: {', '.join(sample['trigger_tests'][:3])}")
        print(f"  - bug_report_id: {sample.get('bug_report_id', 'N/A')}")
        print(f"  - bug_report_url: {sample.get('bug_report_url', 'N/A')}")

if __name__ == "__main__":
    main()
