import json

d4j_bug_lists = '''
| Chart           | jfreechart                 |       26       | 1-26                | None                    |
| Cli             | commons-cli                |       39       | 1-5,7-40            | 6                       |
| Closure         | closure-compiler           |      174       | 1-62,64-92,94-176   | 63,93                   |
| Codec           | commons-codec              |       18       | 1-18                | None                    |
| Collections     | commons-collections        |        4       | 25-28               | 1-24                    |
| Compress        | commons-compress           |       47       | 1-47                | None                    |
| Csv             | commons-csv                |       16       | 1-16                | None                    |
| Gson            | gson                       |       18       | 1-18                | None                    |
| JacksonCore     | jackson-core               |       26       | 1-26                | None                    |
| JacksonDatabind | jackson-databind           |      112       | 1-112               | None                    |
| JacksonXml      | jackson-dataformat-xml     |        6       | 1-6                 | None                    |
| Jsoup           | jsoup                      |       93       | 1-93                | None                    |
| JxPath          | commons-jxpath             |       22       | 1-22                | None                    |
| Lang            | commons-lang               |       64       | 1,3-65              | 2                       |
| Math            | commons-math               |      106       | 1-106               | None                    |
| Mockito         | mockito                    |       38       | 1-38                | None                    |
| Time            | joda-time                  |       26       | 1-20,22-27          | 21                      |'''

def _get_relevant_bugs(bugs, current_bug, only_same):
    potential_pairs = []
    # items = current_bug.split("-")
    # current_bug = items[0] + "-" + items[1] + ".java"
    project = current_bug.split("-")[0]
    for file_name, bug in bugs.items():
        if file_name == current_bug:
            continue
        if file_name.startswith(project + "-") and only_same:
            potential_pairs.append((len(bug['buggy']) + len(bug['fix']), file_name))
        elif not only_same:
            potential_pairs.append((len(bug['buggy']) + len(bug['fix']), file_name))
    # sort from smallest to largest
    potential_pairs.sort(key=lambda x: x[0])
    return potential_pairs


# picking an example fix pairs from a project
def pick_smallest_example_fix(bugs, current_bug, only_same=False):
    potential_pairs = _get_relevant_bugs(bugs, current_bug, only_same)
    return bugs[potential_pairs[0][1]]['buggy'], bugs[potential_pairs[0][1]]['fix']

def _get_relevant_bugs_topN(bugs, current_bug, only_same):
    potential_pairs = []
    items = current_bug.split("-") # Lang-34-1.java
    current_bug = items[0] + "-" + items[1] + ".java" 
    project = current_bug.split("-")[0]
    for file_name, bug in bugs.items():
        if file_name == current_bug:
            continue
        if file_name.startswith(project + "-") and only_same:
            potential_pairs.append((len(bug['buggy']) + len(bug['fix']), file_name))
        elif not only_same:
            potential_pairs.append((len(bug['buggy']) + len(bug['fix']), file_name))
    # sort from smallest to largest
    potential_pairs.sort(key=lambda x: x[0])
    return potential_pairs

def pick_smallest_example_fix_topN(bugs, current_bug, only_same=False):
    potential_pairs = _get_relevant_bugs_topN(bugs, current_bug, only_same)
    return bugs[potential_pairs[0][1]]['buggy'], bugs[potential_pairs[0][1]]['fix'] 

def clean_parse_d4j_single_hunk(folder):
    with open(folder + "/single_function_single_hunk_repair.json", "r") as f:
        result = json.load(f)
    cleaned_result = {}
    for k, v in result.items():
        lines = v['buggy'].splitlines()
        leading_white_space = len(lines[0]) - len(lines[0].lstrip())
        cleaned_result[k + ".java"] = {"buggy": "\n".join([line[leading_white_space:] for line in lines])}
        lines = v["prefix"].splitlines()
        cleaned_result[k + ".java"]["prefix"] = "\n".join([line[leading_white_space:] for line in lines])
        lines = v["suffix"].splitlines()
        cleaned_result[k + ".java"]["suffix"] = "\n".join([line[leading_white_space:] for line in lines])
        lines = v['fix'].splitlines()
        leading_white_space = len(lines[0]) - len(lines[0].lstrip())
        cleaned_result[k + ".java"]["fix"] = "\n".join([line[leading_white_space:] for line in lines])
    return cleaned_result

def clean_parse_d4j_expand(folder):
    with open(folder + "d4j-info/growing_bugs_single_function_expand.json", "r") as f:
        result = json.load(f)
    cleaned_result = {}
    # defects4j_v1_0 = ["Chart", "Closure", "Lang", "Math", "Time"]
    # defects4j_v2_0 = ["Cli", "Codec", "Collections", "Compress", "Csv", "Gson", "JacksonCore", "JacksonDatabind", "JacksonXml", "Jsoup", "JxPath", "Mockito"]
    for k, v in result.items():
        # if(k.split("-")[0] not in defects4j_v2_0):
        #     continue
        lines = v['buggy'].splitlines()
        leading_white_space = len(lines[0]) - len(lines[0].lstrip())
        cleaned_result[k + ".java"] = {"buggy": "\n".join([line[leading_white_space:] for line in lines])}
        lines = v['fix'].splitlines()
        leading_white_space = len(lines[0]) - len(lines[0].lstrip())
        cleaned_result[k + ".java"]["fix"] = "\n".join([line[leading_white_space:] for line in lines])
    # print(cleaned_result['JacksonDatabind-17.java']['buggy'])
    return cleaned_result

def clean_parse_d4j(folder):
    """Load GrowingBugs dataset (57 bugs)"""
    with open(folder + "d4j-info/growing_bugs_single_function.json", "r") as f:
        result = json.load(f)
    cleaned_result = {}
    # defects4j_v1_0 = ["Chart", "Closure", "Lang", "Math", "Time"]
    # defects4j_v2_0 = ["Cli", "Codec", "Collections", "Compress", "Csv", "Gson", "JacksonCore", "JacksonDatabind", "JacksonXml", "Jsoup", "JxPath", "Mockito"]
    for k, v in result.items():
        # if(k.split("-")[0] not in defects4j_v2_0):
        #     continue
        lines = v['buggy'].splitlines()
        leading_white_space = len(lines[0]) - len(lines[0].lstrip())
        cleaned_result[k + ".java"] = {"buggy": "\n".join([line[leading_white_space:] for line in lines])}
        lines = v['fix'].splitlines()
        leading_white_space = len(lines[0]) - len(lines[0].lstrip())
        cleaned_result[k + ".java"]["fix"] = "\n".join([line[leading_white_space:] for line in lines])
    # print(cleaned_result['JacksonDatabind-17.java']['buggy'])
    return cleaned_result

def clean_parse_d4j_main(folder, version="all", use_enriched=False):
    """Load main Defects4J dataset (483 bugs total)
    
    Args:
        folder: Path to project root
        version: 'v1.2' (251 bugs), 'v2.0' (232 bugs), or 'all' (483 bugs)
        use_enriched: If True, load from single_function_repair_enriched.json with test metadata
    """
    json_file = "d4j-info/single_function_repair_enriched.json" if use_enriched else "d4j-info/single_function_repair.json"
    with open(folder + json_file, "r") as f:
        result = json.load(f)
    cleaned_result = {}
    
    # Define project versions
    v1_projects = ["Chart", "Closure", "Lang", "Math", "Time"]
    v2_projects = ["Cli", "Codec", "Collections", "Compress", "Csv", "Gson", 
                   "JacksonCore", "JacksonDatabind", "JacksonXml", "Jsoup", "JxPath", "Mockito"]
    
    for k, v in result.items():
        project = k.split("-")[0]
        
        # Filter by version if specified
        if version == "v1.2" and project not in v1_projects:
            continue
        elif version == "v2.0" and project not in v2_projects:
            continue
        
        lines = v['buggy'].splitlines()
        leading_white_space = len(lines[0]) - len(lines[0].lstrip())
        bug_entry = {"buggy": "\n".join([line[leading_white_space:] for line in lines])}
        lines = v['fix'].splitlines()
        leading_white_space = len(lines[0]) - len(lines[0].lstrip())
        bug_entry["fix"] = "\n".join([line[leading_white_space:] for line in lines])
        
        # Include enriched metadata if available
        if use_enriched:
            bug_entry["test_patch"] = v.get("test_patch")
            bug_entry["relevant_tests"] = v.get("relevant_tests", [])
            bug_entry["trigger_tests"] = v.get("trigger_tests", [])
            bug_entry["bug_report_id"] = v.get("bug_report_id")
            bug_entry["bug_report_url"] = v.get("bug_report_url")
        
        cleaned_result[k + ".java"] = bug_entry
    
    return cleaned_result


def format_bug_info(bug_data):
    """Format bug metadata into a readable string for prompts
    
    Args:
        bug_data: Dictionary containing bug information with optional enriched fields
    
    Returns:
        Formatted string with bug information
    """
    if not any(key in bug_data for key in ['trigger_tests', 'relevant_tests', 'bug_report_url', 'test_patch']):
        return "No additional bug information available."
    
    info_parts = []
    
    # Add trigger tests (failing tests that expose the bug)
    if bug_data.get('trigger_tests'):
        trigger_list = bug_data['trigger_tests']
        if len(trigger_list) > 5:
            trigger_list = trigger_list[:5]
            info_parts.append(f"Trigger Tests (failing tests): {', '.join(trigger_list)} ... ({len(bug_data['trigger_tests'])} total)")
        else:
            info_parts.append(f"Trigger Tests (failing tests): {', '.join(trigger_list)}")
    
    # Add relevant tests count
    if bug_data.get('relevant_tests'):
        info_parts.append(f"Total Relevant Tests: {len(bug_data['relevant_tests'])}")
    
    # Add bug report link
    if bug_data.get('bug_report_url') and bug_data['bug_report_url']:
        info_parts.append(f"Bug Report: {bug_data['bug_report_url']}")
    
    # Add test patch summary if available
    if bug_data.get('test_patch'):
        test_lines = bug_data['test_patch'].count('\n')
        info_parts.append(f"Test Patch Available: Yes ({test_lines} lines)")
    
    return "\n".join(info_parts) if info_parts else "No additional bug information available."


def clean_parse_d4j_topN(folder):
    with open(folder + "d4j-info/top_n_function.json", "r") as f:
        result = json.load(f)
    cleaned_result = {}
    for k, v in result.items():
        for index, method in enumerate(v):
            lines = method['buggy'].splitlines()
            leading_white_space = len(lines[0]) - len(lines[0].lstrip())
            key = k + "-" + str(index) +".java"
            cleaned_result[key] = {"buggy": "\n".join([line[leading_white_space:] for line in lines])}
    return cleaned_result



def clean_parse_d4j_single_line(folder):
    with open(folder + "Defects4j/single_function_single_line_repair.json", "r") as f:
        result = json.load(f)
    cleaned_result = {}
    for k, v in result.items():
        lines = v['buggy'].splitlines()
        leading_white_space = len(lines[0]) - len(lines[0].lstrip())
        cleaned_result[k + ".java"] = {"buggy": "\n".join([line[leading_white_space:] for line in lines])}
        lines = v["prefix"].splitlines()
        cleaned_result[k + ".java"]["prefix"] = "\n".join([line[leading_white_space:] for line in lines])
        lines = v["suffix"].splitlines()
        cleaned_result[k + ".java"]["suffix"] = "\n".join([line[leading_white_space:] for line in lines])
        lines = v['fix'].splitlines()
        leading_white_space = len(lines[0]) - len(lines[0].lstrip())
        cleaned_result[k + ".java"]["fix"] = "\n".join([line[leading_white_space:] for line in lines])

        buggy_line = cleaned_result[k + ".java"]["buggy"] \
            .removeprefix(cleaned_result[k + ".java"]["prefix"]).removesuffix(
            cleaned_result[k + ".java"]["suffix"]).replace("\n", "")
        cleaned_result[k + ".java"]["buggy_line"] = buggy_line
    return cleaned_result