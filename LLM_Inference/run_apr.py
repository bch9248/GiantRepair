import argparse
import sys
import torch
import os
import json
import time
import random
import numpy as np
from openai import AzureOpenAI
from difflib import unified_diff
from dotenv import load_dotenv
from tqdm import tqdm

from Models.model import GPT2, starCoder, LLama2, CodeLLama
from utils.parse_d4j import clean_parse_d4j, clean_parse_d4j_main, clean_parse_d4j_topN, pick_smallest_example_fix, pick_smallest_example_fix_topN, clean_parse_d4j_expand, format_bug_info
from utils.my_prompt import get_naive_prompt, get_cot_prompt, get_react_prompt, get_pearl_prompt, get_sr_prompt, get_srwoa_prompt, get_srwoi_prompt, get_usc_prompt
from utils.api_request import request_engine, create_openai_config, create_gpt4_config, create_openai_config_suffix, create_openai_config_single

# Load environment variables from .env file
load_dotenv()

# Initialize Azure OpenAI client (global)
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def get_unified_diff(source, mutant):
    output = ""
    for line in unified_diff(source.split('\n'), mutant.split('\n'), lineterm=''):
        output += line + "\n"
    return output


def extract_text_output(ret, file_name):
    """
    Safely extract text output from Azure/OpenAI chat-completions style response.
    Returns (output_text, finish_reason). output_text is None if not usable.
    """
    try:
        choices = ret.get("choices", [])
        if not choices:
            print(f"[WARN] No choices in response for {file_name}")
            print(json.dumps(ret, indent=2, ensure_ascii=False))
            return None, ""

        choice = choices[0]
        finish_reason = choice.get("finish_reason", "")
        message = choice.get("message", {})
        content = message.get("content", None)

        if finish_reason != "stop":
            return None, finish_reason

        if content is None:
            print(f"[WARN] Empty content for {file_name}")
            print(json.dumps(ret, indent=2, ensure_ascii=False))
            return None, finish_reason

        if isinstance(content, str):
            output = content.strip()
        elif isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        text_value = part.get("text", "")
                        if isinstance(text_value, str):
                            text_parts.append(text_value)
                    elif "text" in part and isinstance(part["text"], str):
                        text_parts.append(part["text"])
            output = "\n".join(text_parts).strip()
        else:
            print(f"[WARN] Unsupported content type for {file_name}: {type(content)}")
            print(json.dumps(ret, indent=2, ensure_ascii=False))
            return None, finish_reason

        if not output:
            print(f"[WARN] Blank output for {file_name}")
            print(json.dumps(ret, indent=2, ensure_ascii=False))
            return None, finish_reason

        return output, finish_reason

    except Exception as e:
        print(f"[WARN] Failed to parse response for {file_name}: {e}")
        print(json.dumps(ret, indent=2, ensure_ascii=False))
        return None, ""


def repair_loop(args, model, prompt, file_name, folder, bug, t_chances, skip_val=True):
    start = time.time()
    repair_result = []
    p_diff = {}
    if not model.check_input(prompt, bug['buggy']):
        return 0, False, False, repair_result

    total_times = 0
    while t_chances > 0:
        total_times += 1
        torch.cuda.empty_cache()
        well, length, outputs, entropies = model.model_prediction(
            prompt,
            bug['buggy'],
            do_sample=True,
            num_samples=t_chances
        )
        t_chances -= args.batch_size
        if well:
            for index, output in enumerate(outputs):
                diff = get_unified_diff(bug['buggy'], output)
                if diff in p_diff:
                    repair_result[p_diff[diff]]['num'] += 1
                    continue
                p_diff[diff] = len(repair_result)
                repair_result.append({
                    'output': output,
                    'diff': diff,
                    'finish_reason': 'stop',
                    'entropy': entropies[index],
                    'num': 1
                })

    end = time.time()

    json_str = json.dumps(repair_result, indent=4)
    with open("{}/{}.json".format(folder, file_name.split(".")[0]), 'w') as f:
        f.write(json_str)

    return len(repair_result), False, False, repair_result


def repair(args, model, bugs, folder, used_prompt, chances, skip_val=True, only_same=True, redo=False):
    if not os.path.exists(folder):
        os.makedirs(folder)
    with open(folder + "/prompt.txt", "w") as f:
        f.write(used_prompt)
    with open(folder + "/args.txt", "w") as f:
        f.write(str(args))

    all_dataset = clean_parse_d4j_expand("../")
    result = {}
    t_generated = 0
    t_unique = 0
    start_t = time.time()

    for file_name, bug in bugs.items():
        rerun_list = [
            "Dosgi_common", "Tika_app", "JacksonDatatypeJsr310",
            "JacksonModuleAfterburner", "Switchyard_admin", "Switchyard_validate",
            "Qpidjms_client", "Tiles_api", "Wicket_spring", "Jcodemodel", "Xades4j"
        ]
        if not file_name.split(".java")[0].split("-")[0] in rerun_list:
            continue

        print(file_name)
        if not redo and os.path.exists("{}/{}.json".format(folder, file_name.split(".")[0])):
            print(f"SKIP: {file_name} already processed")
            continue

        if "Collections" in file_name:
            example_bug, example_fix = pick_smallest_example_fix(all_dataset, file_name, only_same=False)
        else:
            example_bug, example_fix = pick_smallest_example_fix(all_dataset, file_name, only_same=only_same)

        prompt = used_prompt.format(example_bug=example_bug, example_fix=example_fix, bug=bug['buggy'])
        n_generated, valid, first_try, result[file_name] = repair_loop(
            args, model, prompt, file_name, folder, bug, chances, skip_val
        )
        if n_generated >= 1:
            t_generated += chances
            t_unique += len(result[file_name])

    end_t = time.time()

    with open(folder + "/stats.txt", "w") as f:
        f.write("Total generated: {}\n".format(t_generated))
        f.write("Total unique: {}\n".format(t_unique))
        f.write("Total time: {}\n".format(end_t - start_t))

    with open(folder + "/lm_repair.json", "w") as f:
        json.dump(result, f)


def repair_codex_loop(prompt, file_name, folder, bug, t_chances,
                      stop="# Provide a fix for the buggy function",
                      skip_val=True) -> (bool, bool, list):
    start = time.time()
    repair_result = []
    p_diff = {}
    total_input_tokens = 0
    total_output_tokens = 0
    temperature = 0.8
    top_p = 0.95
    config = create_openai_config(message=prompt, stop=stop, temperature=temperature, top_p=top_p)
    total_times = 0

    while t_chances > 0:
        total_times += 1
        t_chances -= 1
        ret = request_engine(config)
        if ret is None:
            return False, False, [], 0, 0, 0

        if 'usage' in ret:
            total_input_tokens += ret['usage'].get('prompt_tokens', 0)
            total_output_tokens += ret['usage'].get('completion_tokens', 0)

        output, finish_reason = extract_text_output(ret, file_name)
        if output is None:
            continue

        diff = get_unified_diff(bug['buggy'], output)
        if diff in p_diff:
            repair_result[p_diff[diff]]['num'] += 1
            continue

        p_diff[diff] = len(repair_result)
        repair_result.append({
            'output': output,
            'diff': diff,
            'finish_reason': finish_reason,
            'num': 1
        })

    end = time.time()
    inference_time = end - start
    json_str = json.dumps(repair_result, indent=4)
    with open("{}/{}.json".format(folder, file_name.split(".")[0]), 'w') as f:
        f.write(json_str)

    return False, False, repair_result, inference_time, total_input_tokens, total_output_tokens


def repair_codex(args, bugs, folder, used_prompt, chances, stop, skip_val=True, only_same=False, redo=False):
    """
    Codex repair loop, write each patch to corresponding file
    :param args: arguments
    :param bugs: dict of bugs
    :param folder: folder to save the files
    :param used_prompt: prompt as input to codex
    :param chances: number of chances to try to repair
    :param stop: stop condition for codex
    :param skip_val: if True, skip validation
    :param redo: if True, redo existing results
    """
    if not os.path.exists(folder):
        os.makedirs(folder)

    with open(folder + "/prompt.txt", "w") as f:
        f.write(used_prompt)
    with open(folder + "/args.txt", "w") as f:
        f.write(str(args))

    result = {}
    t_generated = 0
    t_unique = 0
    start_t = time.time()
    inference_times = {}
    total_input_tokens = 0
    total_output_tokens = 0

    if args.dataset.startswith("defects4j-"):
        all_dataset = clean_parse_d4j_main("../", version="all")
    else:
        all_dataset = clean_parse_d4j("../")

    pbar = tqdm(bugs.items(), desc="Processing bugs", unit="bug")
    for file_name, bug in pbar:
        pbar.set_description(f"Processing {file_name.split('.')[0]}")
        if not redo and os.path.exists("{}/{}.json".format(folder, file_name.split(".")[0])):
            pbar.write(f"⏭️  SKIP: {file_name.split('.')[0]} (already processed)")
            continue

        if "Collections" in file_name:
            example_bug, example_fix = pick_smallest_example_fix_topN(all_dataset, file_name, only_same=False)
        else:
            example_bug, example_fix = pick_smallest_example_fix_topN(all_dataset, file_name, only_same=only_same)

        bug_info = format_bug_info(bug)
        prompt = used_prompt.format(
            example_bug=example_bug,
            example_fix=example_fix,
            bug=bug['buggy'],
            bug_info=bug_info
        )

        valid, first_try, result[file_name], inf_time, input_tokens, output_tokens = repair_codex_loop(
            prompt, file_name, folder, bug, t_chances=chances, stop=stop, skip_val=skip_val
        )

        inference_times[file_name.split('.')[0]] = inf_time
        total_input_tokens += input_tokens
        total_output_tokens += output_tokens

        if len(result[file_name]) != 0:
            t_generated += chances
            t_unique += len(result[file_name])

    end_t = time.time()

    times_list = list(inference_times.values())
    avg_inference_time = sum(times_list) / len(times_list) if times_list else 0

    input_cost = (total_input_tokens / 1_000_000) * 0.2
    output_cost = (total_output_tokens / 1_000_000) * 0.8
    total_cost = input_cost + output_cost
    avg_cost_per_bug = total_cost / len(inference_times) if len(inference_times) > 0 else 0

    inference_stats = {
        "total_bugs_processed": len(inference_times),
        "total_inference_time": sum(times_list),
        "average_inference_time": round(avg_inference_time, 2),
        "min_inference_time": round(min(times_list), 2) if times_list else 0,
        "max_inference_time": round(max(times_list), 2) if times_list else 0,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_tokens": total_input_tokens + total_output_tokens,
        "input_cost_usd": round(input_cost, 4),
        "output_cost_usd": round(output_cost, 4),
        "total_cost_usd": round(total_cost, 4),
        "average_cost_per_bug_usd": round(avg_cost_per_bug, 4),
        "per_bug_times": {k: round(v, 2) for k, v in inference_times.items()}
    }

    with open(folder + "/inference_stats.json", "w") as f:
        json.dump(inference_stats, f, indent=4)

    with open(folder + "/stats.txt", "w") as f:
        f.write("Total generated: {}\n".format(t_generated))
        f.write("Total unique: {}\n".format(t_unique))
        f.write("Total time: {}\n".format(end_t - start_t))
        f.write("Average inference time per bug: {:.2f}s\n".format(avg_inference_time))
        f.write("Total tokens: {} (input: {}, output: {})\n".format(
            total_input_tokens + total_output_tokens, total_input_tokens, total_output_tokens))
        f.write("Total cost: ${:.4f} (input: ${:.4f}, output: ${:.4f})\n".format(
            total_cost, input_cost, output_cost))
        f.write("Average cost per bug: ${:.4f}\n".format(avg_cost_per_bug))

    with open(folder + "/codex_repair.json", "w") as f:
        json.dump(result, f)


def repair_gpt4_loop(prompt, file_name, folder, bug, t_chances,
                     stop="# Provide a fix for the buggy function",
                     skip_val=True) -> (bool, bool, list):
    start = time.time()
    repair_result = []
    p_diff = {}
    total_input_tokens = 0
    total_output_tokens = 0
    temperature = 0.8
    top_p = 0.95
    config = create_gpt4_config(message=prompt, stop=stop, temperature=temperature, top_p=top_p)
    total_times = 0

    while t_chances > 0:
        total_times += 1
        t_chances -= 1
        ret = request_engine(config)
        if ret is None:
            return False, False, [], 0, 0, 0

        if 'usage' in ret:
            total_input_tokens += ret['usage'].get('prompt_tokens', 0)
            total_output_tokens += ret['usage'].get('completion_tokens', 0)

        output, finish_reason = extract_text_output(ret, file_name)
        if output is None:
            continue

        diff = get_unified_diff(bug['buggy'], output)
        if diff in p_diff:
            repair_result[p_diff[diff]]['num'] += 1
            continue

        p_diff[diff] = len(repair_result)
        repair_result.append({
            'output': output,
            'diff': diff,
            'finish_reason': finish_reason,
            'num': 1
        })

    end = time.time()
    inference_time = end - start
    json_str = json.dumps(repair_result, indent=4)
    with open("{}/{}.json".format(folder, file_name.split(".")[0]), 'w') as f:
        f.write(json_str)

    return False, False, repair_result, inference_time, total_input_tokens, total_output_tokens


def repair_gpt4(args, bugs, folder, used_prompt, chances, stop, skip_val=True, only_same=False, redo=False):
    if not os.path.exists(folder):
        os.makedirs(folder)

    with open(folder + "/prompt.txt", "w") as f:
        f.write(used_prompt)
    with open(folder + "/args.txt", "w") as f:
        f.write(str(args))

    if args.dataset.startswith("defects4j-"):
        all_dataset = clean_parse_d4j_main("../", version="all")
    else:
        all_dataset = clean_parse_d4j("../")

    result = {}
    t_generated = 0
    t_unique = 0
    start_t = time.time()
    inference_times = {}
    total_input_tokens = 0
    total_output_tokens = 0

    pbar = tqdm(bugs.items(), desc="Processing bugs", unit="bug")
    for file_name, bug in pbar:
        pbar.set_description(f"Processing {file_name.split('.')[0]}")
        if not redo and os.path.exists("{}/{}.json".format(folder, file_name.split(".")[0])):
            pbar.write(f"⏭️  SKIP: {file_name.split('.')[0]} (already processed)")
            continue

        if "Collections" in file_name:
            example_bug, example_fix = pick_smallest_example_fix_topN(all_dataset, file_name, only_same=False)
        else:
            example_bug, example_fix = pick_smallest_example_fix_topN(all_dataset, file_name, only_same=only_same)

        bug_info = format_bug_info(bug)
        prompt = used_prompt.format(
            example_bug=example_bug,
            example_fix=example_fix,
            bug=bug['buggy'],
            bug_info=bug_info
        )

        valid, first_try, result[file_name], inf_time, input_tokens, output_tokens = repair_gpt4_loop(
            prompt, file_name, folder, bug, t_chances=chances, stop=stop, skip_val=skip_val
        )

        inference_times[file_name.split('.')[0]] = inf_time
        total_input_tokens += input_tokens
        total_output_tokens += output_tokens

        if len(result[file_name]) != 0:
            t_generated += chances
            t_unique += len(result[file_name])

    end_t = time.time()

    times_list = list(inference_times.values())
    avg_inference_time = sum(times_list) / len(times_list) if times_list else 0

    input_cost = (total_input_tokens / 1_000_000) * 0.2
    output_cost = (total_output_tokens / 1_000_000) * 0.8
    total_cost = input_cost + output_cost
    avg_cost_per_bug = total_cost / len(inference_times) if len(inference_times) > 0 else 0

    inference_stats = {
        "total_bugs_processed": len(inference_times),
        "total_inference_time": sum(times_list),
        "average_inference_time": round(avg_inference_time, 2),
        "min_inference_time": round(min(times_list), 2) if times_list else 0,
        "max_inference_time": round(max(times_list), 2) if times_list else 0,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_tokens": total_input_tokens + total_output_tokens,
        "input_cost_usd": round(input_cost, 4),
        "output_cost_usd": round(output_cost, 4),
        "total_cost_usd": round(total_cost, 4),
        "average_cost_per_bug_usd": round(avg_cost_per_bug, 4),
        "per_bug_times": {k: round(v, 2) for k, v in inference_times.items()}
    }

    with open(folder + "/inference_stats.json", "w") as f:
        json.dump(inference_stats, f, indent=4)

    with open(folder + "/stats.txt", "w") as f:
        f.write("Total generated: {}\n".format(t_generated))
        f.write("Total unique: {}\n".format(t_unique))
        f.write("Total time: {}\n".format(end_t - start_t))
        f.write("Average inference time per bug: {:.2f}s\n".format(avg_inference_time))
        f.write("Total tokens: {} (input: {}, output: {})\n".format(
            total_input_tokens + total_output_tokens, total_input_tokens, total_output_tokens))
        f.write("Total cost: ${:.4f} (input: ${:.4f}, output: ${:.4f})\n".format(
            total_cost, input_cost, output_cost))
        f.write("Average cost per bug: ${:.4f}\n".format(avg_cost_per_bug))

    with open(folder + "/gpt4_repair.json", "w") as f:
        json.dump(result, f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parameter_path", type=str, help="Downloaded LLM's parameters")
    parser.add_argument("--model_name", type=str, default="EleutherAI/gpt-neo-1.3B")
    parser.add_argument("--batch_size", type=int, default=1)
    parser.add_argument(
        "--dataset", type=str, default="defects4j",
        help="Dataset to use: defects4j (GrowingBugs-57), defects4j-v1.2 (251), defects4j-v2.0 (232), defects4j-all (483)"
    )
    parser.add_argument("--chances", type=int, default=1)
    parser.add_argument("--skip_val", action="store_true", default=False)
    parser.add_argument("--folder", type=str, default="../results/test")
    parser.add_argument("--seed", type=int, default=420)
    parser.add_argument("--weight", type=str, default=None)
    parser.add_argument("--redo", action="store_true", help="Redo evaluation for bugs that already have results (default: skip existing)")
    parser.add_argument(
        "--mode", type=str, default="sr",
        choices=["naive", "cot", "react", "pearl", "sr", "srwoa", "srwoi", "usc", "all"],
        help="Prompt strategy to use: naive/cot/react/pearl/sr/srwoa/srwoi/usc, or 'all' to run all modes"
    )
    parser.add_argument(
        "--use_enriched", action="store_true",
        help="Use enriched dataset with test information (single_function_repair_enriched.json)"
    )
    args = parser.parse_args()

    prompt_strategies = {
        "naive": get_naive_prompt(),
        "cot": get_cot_prompt(),
        "react": get_react_prompt(),
        "pearl": get_pearl_prompt(),
        "sr": get_sr_prompt(),
        "srwoa": get_srwoa_prompt(),
        "srwoi": get_srwoi_prompt(),
        "usc": get_usc_prompt()
    }

    if args.dataset == "defects4j":
        print(f"{args.dataset} (GrowingBugs)")
        dataset = clean_parse_d4j(folder="../")
        stop = "// Provide a fix for the buggy function"
        args.language = "java"
    elif args.dataset == "defects4j-v1.2":
        print(f"{args.dataset} (Defects4J v1.2 - Chart, Closure, Lang, Math, Time)")
        if args.use_enriched:
            print("Using enriched dataset with test information")
        dataset = clean_parse_d4j_main(folder="../", version="v1.2", use_enriched=args.use_enriched)
        stop = "// Provide a fix for the buggy function"
        args.language = "java"
    elif args.dataset == "defects4j-v2.0":
        print(f"{args.dataset} (Defects4J v2.0 - All other projects)")
        if args.use_enriched:
            print("Using enriched dataset with test information")
        dataset = clean_parse_d4j_main(folder="../", version="v2.0", use_enriched=args.use_enriched)
        stop = "// Provide a fix for the buggy function"
        args.language = "java"
    elif args.dataset == "defects4j-all":
        print(f"{args.dataset} (Defects4J v1.2 + v2.0 - 483 bugs total)")
        if args.use_enriched:
            print("Using enriched dataset with test information")
        dataset = clean_parse_d4j_main(folder="../", version="all", use_enriched=args.use_enriched)
        stop = "// Provide a fix for the buggy function"
        args.language = "java"
    elif args.dataset == "defects4jTop":
        print(args.dataset)
        dataset = clean_parse_d4j_topN(folder="../")
        stop = "// Provide a fix for the buggy function"
        args.language = "java"
    else:
        print("Unsupported dataset!!!", file=sys.stderr)
        exit(-1)

    if args.mode == "all":
        modes_to_run = ["naive", "cot", "react", "pearl", "sr", "srwoa", "srwoi", "usc"]
        base_folder = args.folder.rstrip('/')
        total_bugs = len(dataset)

        for mode in modes_to_run:
            mode_folder = f"{base_folder}/{mode}"

            if not args.redo and os.path.exists(mode_folder):
                json_files = [f for f in os.listdir(mode_folder) if f.endswith('.json') and not f.endswith('_repair.json')]
                if len(json_files) >= total_bugs:
                    print(f"\n{'='*60}")
                    print(f"⏭️  SKIP MODE: {mode.upper()} (already complete: {len(json_files)}/{total_bugs} bugs)")
                    print(f"{'='*60}\n")
                    continue

            print(f"\n{'='*60}")
            print(f"🔧 RUNNING MODE: {mode.upper()}")
            print(f"{'='*60}\n")
            mode_args = argparse.Namespace(**vars(args))
            mode_args.mode = mode
            mode_args.folder = mode_folder
            prompt = prompt_strategies[mode]
            run_repair(mode_args, dataset, prompt, stop)
        return

    print(f"Using mode: {args.mode}")
    prompt = prompt_strategies[args.mode]
    args.folder = args.folder.rstrip('/') + f"/{args.mode}"
    run_repair(args, dataset, prompt, stop)


def run_repair(args, dataset, prompt, stop):
    set_seed(args.seed)
    model = None

    if args.model_name == "gpt-neo-1.3B":
        model = GPT2(batch_size=args.batch_size, pretrained=args.model_name, stop=stop, weight=args.weight)
    elif args.model_name == "starcoderbase":
        model = starCoder(batch_size=args.batch_size, pretrained=args.model_name, stop=stop, weight=args.weight)
    elif args.model_name == "Llama-2-7b-hf":
        model = LLama2(batch_size=args.batch_size, pretrained=args.model_name, stop=stop, weight=args.weight)
    elif args.model_name == "Llama-2-13b-hf":
        model = LLama2(batch_size=args.batch_size, pretrained=args.model_name, stop=stop, weight=args.weight)
    elif args.model_name == "CodeLlama-7b-hf":
        model = CodeLLama(batch_size=args.batch_size, pretrained=args.model_name, stop=stop, weight=args.weight)
    elif args.model_name == "gpt-3.5":
        repair_codex(
            args, dataset, args.folder, prompt, chances=args.chances,
            stop=stop, skip_val=args.skip_val,
            only_same=args.dataset.startswith("defects4j"),
            redo=args.redo
        )
    elif args.model_name == "gpt-4":
        repair_gpt4(
            args, dataset, args.folder, prompt, chances=args.chances,
            stop=stop, skip_val=args.skip_val,
            only_same=args.dataset.startswith("defects4j"),
            redo=args.redo
        )
    else:
        print("No processed model!!!", file=sys.stderr)
        exit(-1)

    if model is not None:
        repair(
            args, model, dataset, args.folder, prompt, args.chances, args.skip_val,
            only_same=args.dataset.startswith("defects4j"), redo=args.redo
        )


if __name__ == '__main__':
    main()

'''
python3 run_apr.py \
  --model_name gpt-4 \
  --batch_size 1 \
  --chances 5 \
  --dataset defects4j-v2.0 \
  --mode usc \
  --redo \
  --skip_val \
  --folder ../results/defects4j_v20
'''