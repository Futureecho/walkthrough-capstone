"""Execute the full evaluation suite."""
from tests.evaluation.eval_harness import print_results
from tests.evaluation.eval_quality_gate import eval_quality_gate
from tests.evaluation.eval_coverage import eval_coverage
from tests.evaluation.eval_comparison import eval_comparison
from tests.evaluation.eval_language import eval_language_policy

def main():
    all_results = []
    all_results.extend(eval_quality_gate())
    all_results.extend(eval_coverage())
    all_results.extend(eval_comparison())
    all_results.extend(eval_language_policy())
    print_results(all_results)

if __name__ == "__main__":
    main()
