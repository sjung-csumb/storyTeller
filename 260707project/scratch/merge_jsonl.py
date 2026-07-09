import os

output_file = 'data/formatted_train.jsonl'
input_files = ['data/formatted_kaggle.jsonl', 'data/formatted_human.jsonl']

print("Merging files...")
count = 0
with open(output_file, 'w', encoding='utf-8') as outfile:
    for fname in input_files:
        if os.path.exists(fname):
            with open(fname, 'r', encoding='utf-8') as infile:
                for line in infile:
                    outfile.write(line)
                    count += 1
            print(f"Added contents of {fname}")
        else:
            print(f"File not found: {fname}")

print(f"Merge complete! Total lines: {count}")
