# This file evaluates LLM patches on GrowingBugs dataset
import os
import json
import subprocess
import javalang
import time
import re
import signal
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.DataSet import DataSet

# Use GrowingBugs dataset
bugs = DataSet('../d4j-info/growing_bugs_single_function.json', '../d4j-info/growing_bugs_filelist.json')

# Path to GrowingBugRepository defects4j
GROWINGBUGS_D4J = '/home/azureuser/GrowingBugRepository/framework/bin/defects4j'

def get_available_growingbugs_projects():
    """Get list of projects available in GrowingBugRepository"""
    try:
        result = subprocess.run([GROWINGBUGS_D4J, 'pids'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            projects = set(line.strip() for line in result.stdout.strip().split('\n') if line.strip())
            print(f"Found {len(projects)} GrowingBugs projects")
            return projects
        else:
            print(f"Error getting GrowingBugs projects: {result.stderr}")
            return set()
    except Exception as e:
        print(f"Exception getting GrowingBugs projects: {e}")
        return set()

AVAILABLE_GROWINGBUGS_PROJECTS = get_available_growingbugs_projects()

def run_d4j_test(source, testmethods, bug_id, workingdir):
    buggy = False
    compile_fail = False
    time_out = False
    entire_buggy = False
    error_string = ""
    
    # check syntax error
    try:
        tokens = javalang.tokenizer.tokenize(source)
        parser = javalang.parser.Parser(tokens)
        parser.parse()
    except:
        return compile_fail, time_out, buggy, entire_buggy, True
    
    for t in testmethods:
        cmd = f"{GROWINGBUGS_D4J} test -w {workingdir} -t {t.strip()}"
        returncode = ""
        error_file = open("stderr.txt", "wb")
        child = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=error_file, bufsize=-1,
                                 start_new_session=True)
        while_begin = time.time()
        while True:
            Flag = child.poll()
            if Flag == 0:
                returncode = child.stdout.readlines()
                print(b"".join(returncode).decode('utf-8'))
                error_file.close()
                break
            elif Flag != 0 and Flag is not None:
                compile_fail = True
                error_file.close()
                with open("stderr.txt", "rb") as f:
                    r = f.readlines()
                for line in r:
                    if re.search(':\serror:\s', line.decode('utf-8')):
                        error_string = line.decode('utf-8')
                        break
                print(error_string)
                break
            elif time.time() - while_begin > 15:
                error_file.close()
                os.killpg(os.getpgid(child.pid), signal.SIGTERM)
                time_out = True
                break
            else:
                time.sleep(0.01)
        log = returncode
        if len(log) > 0 and log[-1].decode('utf-8') == "Failing tests: 0\n":
            continue
        else:
            buggy = True
            break
        
    if not buggy:
        print('Checking all tests including regression tests...')
        cmd = f"{GROWINGBUGS_D4J} test -w {workingdir}"
        returncode = ""
        child = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=-1,
                                 start_new_session=True)
        while_begin = time.time()
        while True:
            Flag = child.poll()
            if Flag == 0:
                returncode = child.stdout.readlines()
                break
            elif Flag != 0 and Flag is not None:
                buggy = True
                break
            elif time.time() - while_begin > 180:
                os.killpg(os.getpgid(child.pid), signal.SIGTERM)
                buggy = True
                break
            else:
                time.sleep(0.01)
        log = returncode
        if len(log) > 0 and log[-1].decode('utf-8') == "Failing tests: 0\n":
            print('SUCCESS: All tests passed!')
        else:
            entire_buggy = True

    return compile_fail, time_out, buggy, entire_buggy, False


def test_all_patches():
    plausible = 0
    correct = 0
    outcome = '../results/growing_bugs_test_results/'
    rootpath = '../results/growing_bugs/'
    
    if not os.path.exists(outcome):
        os.makedirs(outcome)
    
    info = bugs.getBugList()
    
    # Print available projects info
    print(f"GrowingBugs defects4j: {GROWINGBUGS_D4J}")
    print(f"Available GrowingBugs projects: {sorted(AVAILABLE_GROWINGBUGS_PROJECTS)}")
    print(f"Total bugs to process: {sum(len(ids) for ids in info.values())}")
    print("="*60)
    
    skipped_projects = set()
    processed = 0
    
    for key in info:
        # Check if project is supported
        if key not in AVAILABLE_GROWINGBUGS_PROJECTS:
            if key not in skipped_projects:
                skipped_projects.add(key)
                print(f"SKIP: Project '{key}' not in GrowingBugs")
            continue
        
        ids = info[key]
        for idnum in ids:
            if os.path.exists(f"{outcome}/{key}_{idnum}.txt"):
                print(f"SKIP: {key}_{idnum} already processed")
                continue
            if not os.path.exists(f"{rootpath}/{key}-{idnum}.json"):
                print(f"SKIP: No patches for {key}-{idnum}")
                continue
            
            print(f"\n{'='*60}")
            print(f"Processing {key}_{idnum}")
            print(f"{'='*60}")

            working_dir_path = os.path.abspath(f"./tmp/growingbugs/{key.lower()}/{key.lower()}_{idnum}_buggy")
            subprocess.run(f"rm -rf {working_dir_path}", shell=True)
            
            # Create parent directory
            os.makedirs(os.path.dirname(working_dir_path), exist_ok=True)
            
            # Checkout using GrowingBugRepository defects4j
            checkout_cmd = f'{GROWINGBUGS_D4J} checkout -p {key} -v {idnum}b -w {working_dir_path}'
            print(f"Checking out: {checkout_cmd}")
            checkout_result = subprocess.run(checkout_cmd, shell=True, capture_output=True, text=True)
            
            if checkout_result.returncode != 0:
                print(f"ERROR: Failed to checkout {key}-{idnum}")
                print(f"Error: {checkout_result.stderr}")
                with open("./error.txt", 'a') as f:
                    f.write(f"Checkout failed for {key}-{idnum}: {checkout_result.stderr}\n")
                continue
            
            working_dir = working_dir_path
            testmethods = os.popen(f"{GROWINGBUGS_D4J} export -w {working_dir} -p tests.trigger").readlines()
            
            if not testmethods:
                print(f"ERROR: No trigger tests found for {key}-{idnum}")
                continue
            
            print(f"Trigger tests: {testmethods}")
            
            modifyfile = bugs.getOneBugFile(f"{key}_{idnum}")
            beginline, endline = bugs.getOneBugLine(f"{key}-{idnum}")
            
            # Load LLM patches
            LLMoutputfile = f"{rootpath}/{key}-{idnum}.json"
            outputdict = json.load(open(LLMoutputfile, 'r'))
            outputlist = []
            
            for item in outputdict:
                output = item["output"]
                # Remove markdown code blocks if present
                if output.strip().startswith("```"):
                    lines = output.strip().split('\n')
                    lines = lines[1:]  # Remove first line (```java or ```)
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    code_lines = []
                    for line in lines:
                        if line.strip() == "```":
                            break
                        code_lines.append(line)
                    output = '\n'.join(code_lines)
                outputlist.append(output)
            
            tries = len(outputlist)
            print(f"Testing {tries} patches...")
            
            originalfile = f'{working_dir}/{modifyfile}'
            
            try:
                with open(originalfile, 'r') as f:
                    sourcelines = f.readlines()
            except:
                with open(originalfile, 'r', encoding="ISO-8859-1") as f:
                    sourcelines = f.readlines()
            
            originalcontent = "".join(sourcelines)
            
            try:
                with open(originalfile, 'r') as f:
                    prior = f.readlines()[0:beginline-1]
            except:
                with open(originalfile, 'r', encoding='ISO-8859-1') as f:
                    prior = f.readlines()[0:beginline-1]
            prior = "".join(prior)

            try:
                with open(originalfile, 'r') as f:
                    after = f.readlines()[endline:]
            except:
                with open(originalfile, 'r', encoding='ISO-8859-1') as f:
                    after = f.readlines()[endline:]
            after = "".join(after)
            
            correctpatches = []
            for i in range(tries):
                print(f"\n--- Testing patch {i+1}/{tries} ---")
                newfile = prior + "\n" + outputlist[i] + "\n" + after
                with open(originalfile, 'w', encoding='utf-8') as f:
                    f.write(newfile)
                
                compile_fail, timed_out, buggy, entire_buggy, syntax_error = run_d4j_test(
                    newfile, testmethods, f"{key}_{idnum}", working_dir)
                print(f"Result: compile_fail={compile_fail}, timeout={timed_out}, "
                      f"buggy={buggy}, entire_buggy={entire_buggy}, syntax_error={syntax_error}")

                if not compile_fail and not timed_out and not buggy and not entire_buggy and not syntax_error:
                    plausible += 1
                    correct += 1
                    print(f"✓ CORRECT PATCH FOUND at position {i}!")
                    
                    if outputlist[i] not in correctpatches:
                        with open(f"{outcome}/{key}_{idnum}.txt", 'a', encoding='utf-8') as f:
                            f.write(f"No.{i} Patch (CORRECT)\n")
                            f.write(outputlist[i]+"\n")
                            f.write("\n" + "="*60 + "\n\n")
                        correctpatches.append(outputlist[i])
                
                # Restore original
                with open(originalfile, 'w', encoding='utf-8') as f:
                    f.write(originalcontent)
            
            processed += 1
            print(f"\nCompleted {key}_{idnum}: Found {len(correctpatches)} unique correct patches")
    
    print("\n" + "="*60)
    print(f"EVALUATION COMPLETE!")
    print(f"="*60)
    print(f"Processed: {processed} bugs")
    print(f"Plausible patches: {plausible}")
    print(f"Correct patches: {correct}")
    if skipped_projects:
        print(f"Skipped projects: {sorted(skipped_projects)}")
        print(f"Total skipped bugs: {sum(len(info[p]) for p in skipped_projects if p in info)}")
    print("="*60)


if __name__ == "__main__":
    test_all_patches()
