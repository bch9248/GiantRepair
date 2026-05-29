# this file trying to test how many bugs only depend on LLM's output 
import os
import json
import subprocess
import pandas as pd
import javalang
import time
import re
import signal
import argparse
from tqdm import tqdm
from utils.DataSet import DataSet

# Use Defects4J v2.0 dataset
bugs = DataSet('../d4j-info/single_function_repair.json', '../d4j-info/filelist.json')

def generate_summary(rootpath, outcome):
    """
    Generate summary statistics for the evaluation results
    :param rootpath: Path to the folder containing generated patches (JSON files)
    :param outcome: Path to the folder containing test results (TXT files)
    """
    import glob
    
    # Count total bugs (JSON files in rootpath)
    json_files = glob.glob(os.path.join(rootpath, "*.json"))
    total_bugs = len(json_files)
    
    # Count fixed bugs (TXT files in outcome)
    txt_files = glob.glob(os.path.join(outcome, "*.txt"))
    fixed_bugs = len(txt_files)
    
    # Calculate pass rate
    pass_rate = (fixed_bugs / total_bugs * 100) if total_bugs > 0 else 0.0
    
    # Create summary dictionary
    summary = {
        "total_bugs": total_bugs,
        "fixed_bugs": fixed_bugs,
        "pass_rate": round(pass_rate, 2)
    }
    
    # Ensure outcome directory exists
    os.makedirs(outcome, exist_ok=True)
    
    # Write summary to JSON file
    summary_file = os.path.join(outcome, "summary.json")
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=4)
    
    print("\n" + "="*60)
    print("SUMMARY STATISTICS")
    print("="*60)
    print(f"Total bugs: {total_bugs}")
    print(f"Fixed bugs: {fixed_bugs}")
    print(f"Pass rate: {pass_rate:.2f}%")
    print(f"Summary saved to: {summary_file}")
    print("="*60)

# Get available defects4j projects
def get_available_d4j_projects():
    """Get list of projects available in the current defects4j installation"""
    try:
        result = subprocess.run(['defects4j', 'pids'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return set(line.strip() for line in result.stdout.strip().split('\n') if line.strip())
    except:
        pass
    return set()

AVAILABLE_D4J_PROJECTS = get_available_d4j_projects()

def growing_bugs():
    """
    Get GrowingBugs dataset's buglists as dict:
    {
        project_id :{
            sub_project: "...",
            project_name: "...",
            bug_ids: [...]
        },
        ...
    }"""
    bugs_info_file = "./growingBugsList.xlsx"
    if not os.path.exists(bugs_info_file):
        # Return empty dict if Excel file doesn't exist - will load from JSON instead
        return {}
    df = pd.read_excel(bugs_info_file)
    df = df.iloc[:, 1:]
    # print(df.columns.tolist())
    bugs_dict = {}
    for index, row in df.iterrows():
        row = list(row)
        # print(row)
        project_id, project_name, sub_project, _, bug_ids = row
        info_dict = {}
        info_dict["sub_project"] = "" if pd.isna(sub_project) else sub_project
        info_dict["project_name"] = project_name
        def parse_ids(ids):
            intervals = ids.split(",")
            ret_ids = []
            for interval in intervals:
                if "-" not in interval:
                    ret_ids.append(int(interval))
                else:
                    begin, end = interval.split("-")
                    for i in range(int(begin), int(end) + 1):
                        ret_ids.append(i)
            return ret_ids
        info_dict["bug_ids"] = parse_ids(bug_ids)
        # print(info_dict)

        bugs_dict[project_id] = info_dict
    # print(bugs_dict)
    return bugs_dict

growing_bugs_dataset = growing_bugs()

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
        cmd = "defects4j test -w {workingdir} -t {testmethod}".format(workingdir=workingdir, testmethod=t.strip())
        returncode = ""
        error_file = open("stderr.txt", "wb")
        child = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=error_file, bufsize=-1,
                                 start_new_session=True)
        while_begin = time.time()
        while True:
            Flag = child.poll()
            if Flag == 0:
                # if child.stdout is not None:
                returncode = child.stdout.readlines()  # child.stdout.read()
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
        # print("log {}".format(log))
        if len(log) > 0 and log[-1].decode('utf-8') == "Failing tests: 0\n":
            continue
        else:
            buggy = True
            break
        
    if not buggy:
        print('So you pass the basic tests, Check if it passes all the test, include the previously passing tests')
        cmd = "defects4j test -w {workingdir}".format(workingdir= workingdir)
        returncode = ""
        child = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=-1,
                                 start_new_session=True)
        while_begin = time.time()
        while True:
            Flag = child.poll()
            if Flag == 0:
                # if child.stdout is not None:
                returncode = child.stdout.readlines()  # child.stdout.read()
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
            print('success')
        else:
            entire_buggy = True

    return compile_fail, time_out, buggy, entire_buggy, False


def test_all_patches(rootpath='../results/defects4j_v20/', outcome='../results/defects4j_v20_test_results/', redo=False):
    plausible = 0
    # Ensure paths end with slash
    rootpath = rootpath.rstrip('/') + '/'
    outcome = outcome.rstrip('/') + '/'
    info = bugs.getBugList()
    
    # Load or initialize detail.json for tracking evaluated bugs
    detail_file = os.path.join(outcome, 'detail.json')
    if os.path.exists(detail_file) and not redo:
        with open(detail_file, 'r') as f:
            evaluated_bugs = json.load(f)
    else:
        evaluated_bugs = {}
    
    skipped_projects = set()
    processed = 0
    
    # Calculate total bugs to process
    total_bugs = sum(len(ids) for p, ids in info.items() if p in AVAILABLE_D4J_PROJECTS)
    
    # Create progress bar
    pbar = tqdm(total=total_bugs, desc="Evaluating patches", unit="bug")
    
    for key in info:
        # Check if project is supported
        if key not in AVAILABLE_D4J_PROJECTS:
            if key not in skipped_projects:
                skipped_projects.add(key)
                pbar.write(f"⚠️  SKIP: Project '{key}' not available in defects4j")
            continue
        
        ids = info[key]
        for idnum in ids:
            # if key not in projs:
                # continue
            bug_id = f"{key}_{idnum}"
            pbar.set_description(f"Evaluating {key}-{idnum}")
            
            if not redo and bug_id in evaluated_bugs:
                pbar.write(f"⏭️  SKIP: {bug_id} (already evaluated)")
                pbar.update(1)
                continue
            if not os.path.exists("{}/{}-{}.json".format(rootpath, key, idnum)):
                pbar.update(1)
                continue

            subprocess.run("rm -rf ./tmp/defects4j_buggy/{repol}/{repol}_{id}_buggy".format(repol=key.lower(), id=idnum), shell=True)
            
            # Defects4J v2.0 doesn't use sub-projects
            has_subproject = False
            
            if not has_subproject: 
                checkout_result = subprocess.run('defects4j checkout -p {repo} -v {id}b -w ./tmp/defects4j_buggy/{repol}/{repol}_{id}_buggy'\
                            .format(repo=key, id=idnum, repol=key.lower()), shell=True, capture_output=True, text=True)
                if checkout_result.returncode != 0:
                    pbar.write(f"❌ ERROR: Failed to checkout {key}-{idnum}")
                    with open("./error.txt" ,'a') as f:
                        f.write(f"Checkout failed for {key}-{idnum}: {checkout_result.stderr}\n")
                    pbar.update(1)
                    continue
                testmethods = os.popen("defects4j export "
                                   "-w ./tmp/defects4j_buggy/{repol}/{repol}_{id}_buggy "
                                   "-p tests.trigger".format(repol=key.lower(), id=idnum)).readlines()
            else:
                checkout_result = subprocess.run('defects4j checkout -p {repo} -v {id}b -w ./tmp/defects4j_buggy/{repol}/{repol}_{id}_buggy -s {sub}'\
                            .format(repo=key, id=idnum, repol=key.lower(), sub=growing_bugs_dataset[key]["sub_project"]), shell=True, capture_output=True, text=True)
                if checkout_result.returncode != 0:
                    pbar.write(f"❌ ERROR: Failed to checkout {key}-{idnum}")
                    with open("./error.txt" ,'a') as f:
                        f.write(f"Checkout failed for {key}-{idnum}: {checkout_result.stderr}\n")
                    pbar.update(1)
                    continue
                testmethods = os.popen("defects4j export "
                                   "-w ./tmp/defects4j_buggy/{repol}/{repol}_{id}_buggy/{sub} "
                                   "-p tests.trigger".format(repol=key.lower(), id=idnum, sub=growing_bugs_dataset[key]["sub_project"])).readlines()
            
            
            
            modifyfile = bugs.getOneBugFile("{}_{}".format(key, idnum))
            
            beginline, endline = bugs.getOneBugLine("{}-{}".format(key, idnum))
            # then check 50 output
            LLMoutputfile = rootpath+"{}-{}.json".format(key, idnum)
            if not os.path.exists(LLMoutputfile):
                with open("./error.txt" ,'a') as f:
                    f.write("No generated patches"+LLMoutputfile+"\n")
                continue
            outputdict = json.load(open(LLMoutputfile, 'r'))
            outputlist = []
            # Original file format
            # for num in outputdict.keys():
            #     if num.isdigit():
            #         outputlist.append(outputdict[num])
            # new file format
            for item in outputdict:
                output = item["output"]
                # Remove markdown code blocks if present
                if output.strip().startswith("```"):
                    lines = output.strip().split('\n')
                    # Remove first line (```java or ```)
                    lines = lines[1:]
                    # Remove last line if it's ```
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    # Remove explanation text after closing ```
                    code_lines = []
                    for line in lines:
                        if line.strip() == "```":
                            break
                        code_lines.append(line)
                    output = '\n'.join(code_lines)
                outputlist.append(output)
            # outputlist = list(set(outputlist))
            tries = len(outputlist)
            originalfile = './tmp/defects4j_buggy/{repo}/{repo}_{id}_buggy/{file}'.format(repo=key.lower(), id=idnum, file=modifyfile)
            
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
            
            correctpathes = []
            for i in range(0, tries):
                newfile = prior + "\n" + outputlist[i] + "\n" + after
                with open(originalfile, 'w', encoding='utf-8') as f:
                    f.write(newfile)
                # Begin Testing
                has_subproject = key in growing_bugs_dataset and len(growing_bugs_dataset[key].get("sub_project", "")) > 0
                if not has_subproject:
                    working_dir = "./tmp/defects4j_buggy/{repo}/{repo}_{id}_buggy/".format(repo=key.lower(), id=idnum)
                else:
                    working_dir = "./tmp/defects4j_buggy/{repo}/{repo}_{id}_buggy/{sub}/".format(repo=key.lower(), id=idnum, sub=growing_bugs_dataset[key]["sub_project"])
                compile_fail, timed_out, buggy, entire_buggy, syntax_error = run_d4j_test(newfile, testmethods, "{}_{}".format(key, idnum), working_dir)

                if not compile_fail and not timed_out and not buggy and not entire_buggy and not syntax_error:
                    plausible += 1
                    if outputlist[i] in correctpathes:
                        javaf = open(originalfile, 'w', encoding='utf-8')
                        javaf.write(originalcontent)
                        continue
                    if not os.path.exists("{}/{}_{}.txt".format(outcome, key, idnum)):
                        with open("{}/{}_{}.txt".format(outcome, key, idnum), 'w', encoding='utf-8') as f:
                            f.write("No.{} Patch\n".format(i))
                            f.write(outputlist[i]+"\n")
                    else:
                        with open("{}/{}_{}.txt".format(outcome, key, idnum), 'a', encoding='utf-8') as f:
                            f.write("No.{} Patch\n".format(i))
                            f.write(outputlist[i]+"\n")
                    correctpathes.append(outputlist[i])
                javaf = open(originalfile, 'w', encoding='utf-8')
                javaf.write(originalcontent)
            
            # Record this bug as evaluated in detail.json
            evaluated_bugs[bug_id] = {
                "json_file": f"{key}-{idnum}.json",
                "total_patches": len(outputlist),
                "plausible_patches": len(correctpathes),
                "evaluated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Save detail.json after each bug evaluation
            os.makedirs(outcome, exist_ok=True)
            with open(detail_file, 'w') as f:
                json.dump(evaluated_bugs, f, indent=4)
            
            processed += 1
            pbar.update(1)
    
    pbar.close()
    
    print("\n" + "="*60)
    print(f"Processing complete!")
    print(f"Processed: {processed} bugs")
    print(f"Plausible patches: {plausible}")
    if skipped_projects:
        print(f"Skipped projects (not in defects4j): {sorted(skipped_projects)}")
        print(f"Total skipped bugs: {sum(len(info[p]) for p in skipped_projects if p in info)}")
    print("="*60)
    
    # Generate summary statistics
    generate_summary(rootpath, outcome)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test LLM-generated patches')
    parser.add_argument('--rootpath', type=str, default='../results/test/',
                        help='Path to folder containing generated patches')
    parser.add_argument('--outcome', type=str, default='../results/test_results/',
                        help='Path to folder for test results')
    parser.add_argument('--redo', action='store_true',
                        help='Redo testing for bugs that already have results')
    parser.add_argument('--mode', type=str, default='naive',
                        choices=['naive', 'cot', 'react', 'pearl', 'sr', 'srwoa', 'srwoi', 'usc', 'all'],
                        help='Specific mode to test (naive, cot, react, pearl, sr, srwoa, srwoi, usc), or "all" to test all modes')
    args = parser.parse_args()
    
    if args.mode == 'all':
        # Test all modes
        modes_to_test = ['naive', 'cot', 'react', 'pearl', 'sr', 'srwoa', 'srwoi', 'usc']
        for mode in modes_to_test:
            # Check if paths already include the mode (called from main.py)
            # If rootpath already ends with a mode name, don't add it again
            if args.rootpath.rstrip('/').endswith(mode):
                rootpath = args.rootpath.rstrip('/') + '/'
                outcome = args.outcome.rstrip('/') + '/'
            else:
                # Paths don't include mode, so add it
                rootpath = args.rootpath.rstrip('/') + f'/{mode}/'
                outcome = args.outcome.rstrip('/') + f'/{mode}/'
            
            # Check if this mode is already complete (skip if not using --redo)
            if not args.redo and os.path.exists(rootpath):
                # Get all JSON files in rootpath (inference results)
                json_files = [f for f in os.listdir(rootpath) if f.endswith('.json')]
                total_bugs = len(json_files)
                
                # Check how many have been evaluated by reading detail.json
                detail_file = os.path.join(outcome, 'detail.json')
                if os.path.exists(detail_file):
                    with open(detail_file, 'r') as f:
                        evaluated_bugs = json.load(f)
                    evaluated_count = len(evaluated_bugs)
                    
                    # If all bugs have been evaluated, skip this mode
                    if evaluated_count >= total_bugs and total_bugs > 0:
                        print(f"\n{'='*60}")
                        print(f"⏭️  SKIP MODE: {mode.upper()} (already complete: {evaluated_count}/{total_bugs} bugs)")
                        print(f"{'='*60}\n")
                        continue
            
            print(f"\n{'='*60}")
            print(f"🧪 TESTING MODE: {mode.upper()}")
            print(f"{'='*60}\n")
            test_all_patches(rootpath=rootpath, outcome=outcome, redo=args.redo)
    else:
        # Test specific mode
        # Check if path already includes the mode
        if args.rootpath.rstrip('/').endswith(args.mode):
            rootpath = args.rootpath.rstrip('/') + '/'
            outcome = args.outcome.rstrip('/') + '/'
        else:
            rootpath = args.rootpath.rstrip('/') + f'/{args.mode}/'
            outcome = args.outcome.rstrip('/') + f'/{args.mode}/'
        test_all_patches(rootpath=rootpath, outcome=outcome, redo=args.redo)
