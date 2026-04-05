import os
import re

def preprocess_document(input_filepath: str, output_filepath: str):
    """
    Reads a text file, removes empty lines, strips excessive whitespace,
    and writes the cleaned text to a new file.
    """
    if not os.path.exists(input_filepath):
        print(f"⚠️ Warning: '{input_filepath}' not found. Skipping.")
        return

    print(f"⏳ Processing '{input_filepath}'...")
    
    with open(input_filepath, 'r', encoding='utf-8') as infile:
        lines = infile.readlines()

    cleaned_lines = []
    for line in lines:
        # Remove leading and trailing whitespace (including newlines)
        stripped_line = line.strip()
        
        # Optional: Collapse multiple spaces into a single space within the line itself
        # This makes the text even denser, though you can comment this out 
        # if you want to strictly preserve inline SQL formatting.
        stripped_line = re.sub(r'\s+', ' ', stripped_line)

        # Only add the line if it is not completely empty
        if stripped_line:
            cleaned_lines.append(stripped_line)

    # Write the cleaned lines back to the new file, separated by a single newline
    with open(output_filepath, 'w', encoding='utf-8') as outfile:
        outfile.write('\n'.join(cleaned_lines))
        
    print(f"✅ Successfully created '{output_filepath}' (Reduced from {len(lines)} to {len(cleaned_lines)} lines).")

if __name__ == "__main__":
    # Define the files you want to process
    documents_to_process = [
        ("./trino.txt", "preprocessed_trino.txt"),
        ("./spark.txt", "preprocessed_spark.txt")
    ]

    print("Starting document preprocessing...")
    print("-" * 30)
    
    for input_file, output_file in documents_to_process:
        preprocess_document(input_file, output_file)
        
    print("-" * 30)
    print("Preprocessing complete!")