#!/usr/bin/env python3
"""
Main pipeline for GrowingBugs automated program repair
Combines inference (patch generation) and evaluation (patch testing)
"""

import argparse
import sys
import os
import subprocess
import time

def run_inference(args):
    """Run patch generation using run_apr.py"""
    print("\n" + "="*60)
    print("STEP 1: PATCH GENERATION")
    print("="*60)
    
    cmd = [
        "python3", "run_apr.py",
        "--model_name", args.model_name,
        "--batch_size", str(args.batch_size),
        "--chances", str(args.chances),
        "--dataset", args.dataset,
        "--folder", args.results_folder,
        "--seed", str(args.seed),
        "--mode", args.mode
    ]
    
    if args.skip_val:
        cmd.append("--skip_val")
    
    if args.redo:
        cmd.append("--redo")
    
    if args.weight:
        cmd.extend(["--weight", args.weight])
    
    print(f"Running: {' '.join(cmd)}")
    print()
    
    start_time = time.time()
    result = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
    elapsed = time.time() - start_time
    
    if result.returncode != 0:
        print(f"\n❌ Inference failed with exit code {result.returncode}")
        return False
    
    print(f"\n✅ Inference completed in {elapsed:.2f}s")
    return True


def run_evaluation(args):
    """Run patch evaluation using test_llm.py"""
    print("\n" + "="*60)
    print("STEP 2: PATCH EVALUATION")
    print("="*60)
    
    # Determine paths based on mode
    if args.mode == "all":
        # When mode is 'all', test_llm will be called for each mode separately
        modes_to_test = ["naive", "cot", "react", "pearl", "sr"]
        all_success = True
        for mode in modes_to_test:
            print(f"\nEvaluating mode: {mode}")
            rootpath = f"{args.results_folder}/{mode}"
            outcome = f"{args.test_results_folder}/{mode}"
            cmd = [
                "python3", "test_llm.py",
                "--rootpath", rootpath,
                "--outcome", outcome,
                "--mode", mode
            ]
            if args.redo:
                cmd.append("--redo")
            
            result = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
            if result.returncode != 0:
                all_success = False
        return all_success
    else:
        # Single mode
        rootpath = f"{args.results_folder}/{args.mode}"
        outcome = f"{args.test_results_folder}/{args.mode}"
        cmd = [
            "python3", "test_llm.py",
            "--rootpath", rootpath,
            "--outcome", outcome,
            "--mode", args.mode
        ]
        
        if args.redo:
            cmd.append("--redo")
    
    print(f"Running: {' '.join(cmd)}")
    print()
    
    start_time = time.time()
    result = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
    elapsed = time.time() - start_time
    
    if result.returncode != 0:
        print(f"\n❌ Evaluation failed with exit code {result.returncode}")
        return False
    
    print(f"\n✅ Evaluation completed in {elapsed:.2f}s")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Complete pipeline for GrowingBugs automated program repair',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick Run full pipeline with GPT-4
  python3 main.py --mode all
  
  # Run with inference only
  python3 main.py --mode all --inference-only
  
  # Run with evaluation only
  python3 main.py --mode all --evaluation-only
  
  # Redo existing results
  python3 main.py --mode all --redo
        """
    )
    
    # Pipeline control
    parser.add_argument("--inference-only", action="store_true",
                        help="Run only inference (patch generation)")
    parser.add_argument("--evaluation-only", action="store_true",
                        help="Run only evaluation (patch testing)")
    
    # Inference arguments
    parser.add_argument("--model_name", type=str, default="gpt-4",
                        help="Model to use: gpt-4, gpt-3.5, starcoderbase, etc.")
    parser.add_argument("--batch_size", type=int, default=1,
                        help="Batch size for inference")
    parser.add_argument("--dataset", type=str, default="defects4j-v2.0",
                        help="Dataset: defects4j (GrowingBugs-57), defects4j-v1.2 (251), defects4j-v2.0 (232), defects4j-all (483)")
    parser.add_argument("--chances", type=int, default=3,
                        help="Number of patches to generate per bug")
    parser.add_argument("--skip_val", action="store_true", default=True,
                        help="Skip validation during inference")
    parser.add_argument("--results_folder", type=str, default="../results/test",
                        help="Folder to save inference results")
    parser.add_argument("--test_results_folder", type=str, default="../results/test_results",
                        help="Folder to save evaluation results")
    parser.add_argument("--mode", type=str, default="naive",
                        choices=["naive", "cot", "react", "pearl", "sr", "all"],
                        help="Prompt strategy mode: naive, cot, react, pearl, sr (specific strategy), or 'all' to run all modes")
    parser.add_argument("--seed", type=int, default=420,
                        help="Random seed")
    parser.add_argument("--weight", type=str, default=None,
                        help="Model weight path")
    
    # Shared arguments
    parser.add_argument("--redo", action="store_true",
                        help="Redo evaluation for bugs that already have results")
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.inference_only and args.evaluation_only:
        print("Error: Cannot specify both --inference-only and --evaluation-only", file=sys.stderr)
        sys.exit(1)
    
    # Print configuration
    print("\n" + "="*60)
    print("GROWINGBUGS AUTOMATED PROGRAM REPAIR PIPELINE")
    print("="*60)
    print(f"Model: {args.model_name}")
    print(f"Dataset: {args.dataset}")
    print(f"Prompt mode: {args.mode}")
    print(f"Patches per bug: {args.chances}")
    print(f"Results folder: {args.results_folder}")
    print(f"Test results folder: {args.test_results_folder}")
    print(f"Redo existing: {args.redo}")
    
    if args.inference_only:
        print(f"Mode: Inference only")
    elif args.evaluation_only:
        print(f"Mode: Evaluation only")
    else:
        print(f"Mode: Full pipeline (inference + evaluation)")
    print("="*60)
    
    overall_start = time.time()
    
    # Run inference
    if not args.evaluation_only:
        if not run_inference(args):
            print("\n❌ Pipeline failed at inference stage")
            sys.exit(1)
    
    # Run evaluation
    if not args.inference_only:
        if not run_evaluation(args):
            print("\n❌ Pipeline failed at evaluation stage")
            sys.exit(1)
    
    overall_elapsed = time.time() - overall_start
    
    # Final summary
    print("\n" + "="*60)
    print("PIPELINE COMPLETE")
    print("="*60)
    print(f"Total time: {overall_elapsed:.2f}s ({overall_elapsed/60:.2f} minutes)")
    if args.mode == "all":
        print(f"Results: {args.results_folder}/{{naive,cot,react,pearl,sr}}")
        print(f"Evaluation: {args.test_results_folder}/{{naive,cot,react,pearl,sr}}")
    else:
        print(f"Results: {args.results_folder}/{args.mode}")
        print(f"Evaluation: {args.test_results_folder}/{args.mode}")
    print("="*60)


if __name__ == "__main__":
    main()
