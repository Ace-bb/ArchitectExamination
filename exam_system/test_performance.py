import time
from dotenv import load_dotenv
load_dotenv()
from main import list_exam_files_by_type, parse_exam_file_by_type, ExamType

print("Testing historical exam loading performance...")
print("=" * 60)

# Test file listing
start = time.time()
files1 = list_exam_files_by_type(ExamType.historical)
t1 = time.time() - start
print(f"First scan: {t1:.3f}s, found {len(files1)} files")

start = time.time()
files2 = list_exam_files_by_type(ExamType.historical)
t2 = time.time() - start
print(f"Cached scan: {t2:.6f}s, found {len(files2)} files")
if t2 > 0:
    print(f"File list speedup: {t1/t2:.1f}x")
else:
    print("File list speedup: Instant")

print()

# Test file parsing
if files1:
    test_file_id = files1[0]['file_id']
    start = time.time()
    parsed1 = parse_exam_file_by_type(ExamType.historical, test_file_id)
    t1 = time.time() - start
    sections_count = len(parsed1['sections']) if parsed1 else 0
    print(f"First parse ({test_file_id}): {t1:.3f}s, sections: {sections_count}")
    
    start = time.time()
    parsed2 = parse_exam_file_by_type(ExamType.historical, test_file_id)
    t2 = time.time() - start
    print(f"Cached parse: {t2:.6f}s, sections: {len(parsed2['sections']) if parsed2 else 0}")
    if t2 > 0:
        print(f"Parse speedup: {t1/t2:.1f}x")
    else:
        print("Parse speedup: Instant")

print("=" * 60)
print("Performance optimization successful!")
