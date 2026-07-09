import os
import json
import random

output_train = 'data/formatted_train.jsonl'
output_val = 'data/formatted_val.jsonl'
input_files = ['data/formatted_kaggle.jsonl', 'data/formatted_human.jsonl']
val_ratio = 0.1  # 10%를 검증 데이터로 분리

print("Reading and merging files...")
all_lines = []

for fname in input_files:
    if os.path.exists(fname):
        with open(fname, 'r', encoding='utf-8') as infile:
            lines = infile.readlines()
            all_lines.extend(lines)
            print(f"Read {len(lines)} lines from {fname}")
    else:
        print(f"File not found: {fname}")

if not all_lines:
    print("No data found to process.")
    exit()

print(f"Total lines loaded: {len(all_lines)}")

# 무작위로 섞기
random.seed(42)  # 재현성을 위한 시드 고정
random.shuffle(all_lines)

# 분리 계산
val_count = int(len(all_lines) * val_ratio)
val_lines = all_lines[:val_count]
train_lines = all_lines[val_count:]

print(f"Splitting data -> Train: {len(train_lines)}, Val: {len(val_lines)}")

# 저장
with open(output_train, 'w', encoding='utf-8') as f_train:
    for line in train_lines:
        f_train.write(line)

with open(output_val, 'w', encoding='utf-8') as f_val:
    for line in val_lines:
        f_val.write(line)

print("Split and save complete!")
