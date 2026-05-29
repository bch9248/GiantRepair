"""
Custom prompts for different repair strategies
Each function returns a prompt template with placeholders: {example_bug}, {example_fix}, {bug}
"""

def get_naive_prompt():
    """
    Strategy A: Standard example-based repair with clear separation
    """
    return """// Provide a fix for the buggy function

// Buggy Function
int binarySearch(int arr[], int l, int r, int x)
{{
    if (r >= l) {{
        int mid = l + (r + l) / 2;
        if (arr[mid] == x)
            return mid;
        if (arr[mid] > x)
            return binarySearch(arr, l, mid - 1, x);
        return binarySearch(arr, mid + 1, r, x);
    }}
    return -1;
}}

// Fixed Function
int binarySearch(int arr[], int l, int r, int x)
{{
    if (r >= l) {{
        int mid = l + (r - l) / 2;
        if (arr[mid] == x)
            return mid;
        if (arr[mid] > x)
            return binarySearch(arr, l, mid - 1, x);
        return binarySearch(arr, mid + 1, r, x);
    }}
    return -1;
}}

// Provide a fix for the buggy function

// Buggy Function
{example_bug}

// Fixed Function
{example_fix}

// Provide a fix for the buggy function

// Buggy Function
{bug}

// Fixed Function
"""


def get_cot_prompt():
    """
    Strategy B: chain-of-thought style with detailed reasoning and step-by-step explanation
    """
    return """// Task: Fix the buggy Java function below step by step, providing reasoning for each change.

// Example:
// Buggy Function
{example_bug}

// Fixed Function
{example_fix}

// Now fix this buggy function step by step:
// Buggy Function
{bug}

// Fixed Function
"""


def get_pearl_prompt():
    """
    Strategy C: PEARL-style prompt first plan the actions, then execute
    """
    return """Fix the following buggy Java function following the PEARL approach:

Approach:
1. design several candidate actions to fix the bug
2. plan the order of actions to fix this bug
3. execute the plan to generate the fixed code

// Example buggy:
{example_bug}

// Example fixed:
{example_fix}

// Now fix this buggy function using the PEARL approach:
{bug}

// Fixed function:
"""

def get_react_prompt():
    """
    Strategy D: ReAct style reasoning
    """
    return """// Let's fix the buggy Java function following the ReAct approach.

Approach:
1. Thought: Analyze the buggy code and identify how to fix it.
2. Action: Fix based on previous thought.
3. Observation: Check if the fix is correct and if it compiles.
... Repeat until the function is fixed.


// Example Buggy code:
{example_bug}

// Example Fixed code:
{example_fix}

// Now fix this buggy function using the ReAct approach:
// Buggy Function
{bug}

// Fixed Function
"""


def get_sr_prompt():
    """
    Strategy E: Our Anchor Reasoning approach
    """
    return """// Task: Fix the buggy Java function below following this anchor reasoning approach:

// Bug_information:
{bug_info}   

// Approach: 
// Step 1. Read the Bug_information and regenerate the buggy function that meet the global intent and pass all the tests in the Bug_information.
// Step 2. Now look at the buggy code and apply ReAct reasoning approach to fix the code.
// ReAct Approach:
// 1. Thought: Analyze the buggy code and identify how to fix it.
// 2. Action: Fix based on previous thought.
// 3. Observation: Check if the fix is correct and if it compiles.
// ... Repeat until the function is fixed.

// Step 3. Consider the code regenerated in step 1 as an global anchor, integrate the global anchor and the fixed code generated in step 2 to generate the final fixed code.

// Reference Example:
// Before (buggy):
{example_bug}

// After (fixed):
{example_fix}

// Now fix this buggy function following the anchor reasoning approach, only output the final fixed code without any explanation, markdown (ex. ```java), and reasoning process:
// Buggy Function:
{bug}

// Fixed Function:
"""

def get_srwoa_prompt():
    """
    Strategy E: Our Anchor Reasoning approach
    """
    return """// Task: Fix the buggy Java function below following this anchor reasoning approach:

// Bug_information:
{bug_info}   

// Approach: 
Read the Bug_information and regenerate the buggy function that meet the global intent and pass all the tests in the Bug_information.

// Reference Example:
// Before (buggy):
{example_bug}

// After (fixed):
{example_fix}

// Now fix this buggy function following the anchor reasoning approach, only output the final fixed code without any explanation, markdown (ex. ```java), and reasoning process:
// Buggy Function:
{bug}

// Fixed Function:
"""

def get_srwoi_prompt():
    """
    Strategy E: Our Anchor Reasoning approach
    """
    return """// Task: Fix the buggy Java function below following this anchor reasoning approach:

// Bug_information:
{bug_info}   

// Approach: 
// Step 1. Read the Bug_information and regenerate the buggy function that meet the global intent and pass all the tests in the Bug_information.
// Step 2. Now look at the buggy code and apply ReAct reasoning approach to fix the code.
// ReAct Approach:
// 1. Thought: Analyze the buggy code and identify how to fix it.
// 2. Action: Fix based on previous thought.
// 3. Observation: Check if the fix is correct and if it compiles.
// ... Repeat until the function is fixed.

// Step 3. Consider the code regenerated in step 1 as an global anchor, integrate the global anchor and the fixed code generated in step 2 to generate the final fixed code.

// Reference Example:
// Before (buggy):
{example_bug}

// After (fixed):
{example_fix}

// Now fix this buggy function following the anchor reasoning approach, only output the final fixed code without any explanation, markdown (ex. ```java), and reasoning process:
// Buggy Function:
{bug}

// Fixed Function:
"""

def get_usc_prompt():
    """
    Strategy F: Unified Self-Consistency approach
    """
    return """// Task: Fix the buggy Java function below following this anchor reasoning approach:

// Bug_information:
{bug_info}   

// Approach: 
// Step 1. Read the Bug_information and provide three version of fix that meet the global intent and pass all the tests in the Bug_information.
// Step 2. Choos the most consistency one among the three versions as the final fix.

// Reference Example:
// Before (buggy):
{example_bug}

// After (fixed):
{example_fix}

// Now fix this buggy function following the anchor reasoning approach, only output the final fixed code without any explanation, markdown (ex. ```java), and reasoning process:
// Buggy Function:
{bug}

// Fixed Function:
"""