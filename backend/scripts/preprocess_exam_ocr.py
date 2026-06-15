"""Preprocess 11408 exam paper OCR for a single subject.
Usage: python scripts/preprocess_exam_ocr.py --subject data_structure
"""
import argparse, sys, os, time

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exam_paper_parser import (
    EXAM_SUBJECTS, parse_docx_questions, _ocr_year_questions, _static_image_dir, STATIC_DIR,
)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", default="data_structure", choices=list(EXAM_SUBJECTS.keys()))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--year", type=int, default=0)
    args = parser.parse_args()

    subject_key = args.subject
    subject_name = EXAM_SUBJECTS[subject_key]
    print(f"Preprocessing OCR for {subject_name} ({subject_key})")

    # Step 1: Parse docx & export images
    print("Step 1: Parsing docx and exporting images...")
    t0 = time.time()
    years_data = parse_docx_questions(subject_key, force=args.force)
    print(f"  Done in {time.time()-t0:.1f}s, years: {sorted(years_data.keys())}")

    # Step 2: OCR each year
    years_to_process = [args.year] if args.year > 0 else sorted([int(y) for y in years_data.keys()])
    for year in years_to_process:
        print(f"\nStep 2: OCR year {year}...")
        t1 = time.time()
        questions = _ocr_year_questions(subject_key, year, force=args.force)
        elapsed = time.time() - t1
        success = sum(1 for q in questions if q.get("ocr_quality") in ("high", "medium"))
        failed = sum(1 for q in questions if q.get("ocr_quality") == "failed")
        need_check = sum(1 for q in questions if q.get("need_manual_check"))
        print(f"  Done in {elapsed:.1f}s: {len(questions)} questions, {success} OCR ok, {failed} failed, {need_check} need check")

    print(f"\nAll OCR preprocessing complete. Total time: {time.time()-t0:.1f}s")

if __name__ == "__main__":
    main()
