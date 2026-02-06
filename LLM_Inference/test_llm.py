# this file trying to test how many bugs only depend on LLM's output 
import os
import json
import subprocess
import pandas as pd
import javalang
import time
import re
import signal
from utils.DataSet import DataSet

# Use Defects4J v2.0 dataset
bugs = DataSet('../d4j-info/single_function_repair.json', '../d4j-info/filelist.json')

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


def test_all_patches():
    plausible = 0
    outcome = '../results/defects4j_v20_test_results/'
    rootpath = '../results/defects4j_v20/'
    info = bugs.getBugList()
    
    # Print available projects info
    print(f"Available defects4j projects: {sorted(AVAILABLE_D4J_PROJECTS)}")
    print(f"Total bugs to process: {sum(len(ids) for ids in info.values())}")
    
    skipped_projects = set()
    processed = 0
    
    for key in info:
        # Check if project is supported
        if key not in AVAILABLE_D4J_PROJECTS:
            if key not in skipped_projects:
                skipped_projects.add(key)
                print(f"SKIP: Project '{key}' not available in defects4j")
            continue
        
        ids = info[key]
        for idnum in ids:
            # if key not in projs:
                # continue
            if os.path.exists("{}/{}_{}.txt".format(outcome, key, idnum)):
                continue
            if not os.path.exists("{}/{}-{}.json".format(rootpath, key, idnum)):
                continue
            print("{}_{}".format(key, idnum))

            subprocess.run("rm -rf ./tmp/defects4j_buggy/{repol}/{repol}_{id}_buggy".format(repol=key.lower(), id=idnum), shell=True)
            
            # Defects4J v2.0 doesn't use sub-projects
            has_subproject = False
            
            if not has_subproject: 
                checkout_result = subprocess.run('defects4j checkout -p {repo} -v {id}b -w ./tmp/defects4j_buggy/{repol}/{repol}_{id}_buggy'\
                            .format(repo=key, id=idnum, repol=key.lower()), shell=True, capture_output=True, text=True)
                if checkout_result.returncode != 0:
                    print(f"ERROR: Failed to checkout {key}-{idnum}")
                    print(f"defects4j may not support GrowingBugs project: {key}")
                    print(f"Error: {checkout_result.stderr}")
                    with open("./error.txt" ,'a') as f:
                        f.write(f"Checkout failed for {key}-{idnum}: {checkout_result.stderr}\n")
                    continue
                testmethods = os.popen("defects4j export "
                                   "-w ./tmp/defects4j_buggy/{repol}/{repol}_{id}_buggy "
                                   "-p tests.trigger".format(repol=key.lower(), id=idnum)).readlines()
            else:
                checkout_result = subprocess.run('defects4j checkout -p {repo} -v {id}b -w ./tmp/defects4j_buggy/{repol}/{repol}_{id}_buggy -s {sub}'\
                            .format(repo=key, id=idnum, repol=key.lower(), sub=growing_bugs_dataset[key]["sub_project"]), shell=True, capture_output=True, text=True)
                if checkout_result.returncode != 0:
                    print(f"ERROR: Failed to checkout {key}-{idnum}")
                    print(f"defects4j may not support GrowingBugs project: {key}")
                    print(f"Error: {checkout_result.stderr}")
                    with open("./error.txt" ,'a') as f:
                        f.write(f"Checkout failed for {key}-{idnum}: {checkout_result.stderr}\n")
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
                print("testoutcome: {}, {}, {}, {}, {}".format(
                    compile_fail, timed_out, buggy, entire_buggy, syntax_error))

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
            
            processed += 1
    
    print("\n" + "="*60)
    print(f"Processing complete!")
    print(f"Processed: {processed} bugs")
    print(f"Plausible patches: {plausible}")
    if skipped_projects:
        print(f"Skipped projects (not in defects4j): {sorted(skipped_projects)}")
        print(f"Total skipped bugs: {sum(len(info[p]) for p in skipped_projects if p in info)}")
    print("="*60)


if __name__ == "__main__":
    # getDefects4jLines()
    # getDefects4jFiles()
    test_all_patches()
